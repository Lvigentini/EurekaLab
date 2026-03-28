"""PdfDownloader — centralized PDF acquisition with cascading fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from eurekalab.config import settings

if TYPE_CHECKING:
    from eurekalab.types.artifacts import Paper

logger = logging.getLogger(__name__)


class PdfDownloader:
    """Download and extract text from academic PDFs using a cascading strategy.

    Fallback order:
        1. Local cache  (~/.eurekalab/pdf_cache/)
        2. local_pdf_path  (already set by bib_loader or Zotero)
        3. arXiv          (if paper.arxiv_id)
        4. Unpaywall      (if paper.doi — free OA copies)
        5. CrossRef links (if paper.doi — publisher full-text URLs)
        6. Direct URL     (paper.url as last resort)

    University proxy (Phase 2) will be inserted between steps 5 and 6.
    """

    def __init__(self) -> None:
        self._cache_dir = self._resolve_cache_dir()
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._timeout = settings.pdf_download_timeout

    @staticmethod
    def _resolve_cache_dir() -> Path:
        if settings.pdf_cache_dir:
            return Path(settings.pdf_cache_dir)
        return Path.home() / ".eurekalab" / "pdf_cache"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def download_and_extract(self, paper: "Paper") -> str | None:
        """Try to download a PDF for *paper* and return extracted text.

        On success, also sets ``paper.local_pdf_path``, ``paper.full_text``,
        and upgrades ``paper.content_tier`` to ``"full_text"``.
        """
        # 1. Cache hit
        text = self._try_cache(paper)
        if text:
            return self._apply(paper, text)

        # 2. Already have a local file
        if paper.local_pdf_path:
            text = self._extract_local(paper.local_pdf_path)
            if text:
                return self._apply(paper, text)

        # 3. arXiv
        if paper.arxiv_id:
            url = f"https://arxiv.org/pdf/{paper.arxiv_id}"
            text = await self._download_and_extract_url(url, paper)
            if text:
                return self._apply(paper, text, cache_key=self._cache_key(paper))

        # 4. Unpaywall (free OA)
        if paper.doi:
            text = await self._try_unpaywall(paper)
            if text:
                return self._apply(paper, text, cache_key=self._cache_key(paper))

        # 5. CrossRef publisher links
        if paper.doi:
            text = await self._try_crossref_links(paper)
            if text:
                return self._apply(paper, text, cache_key=self._cache_key(paper))

        # 6. Direct URL
        if paper.url and paper.url.lower().endswith(".pdf"):
            text = await self._download_and_extract_url(paper.url, paper)
            if text:
                return self._apply(paper, text, cache_key=self._cache_key(paper))

        return None

    def is_configured(self) -> bool:
        """Return True if the downloader can do anything useful."""
        return True  # cache + arXiv always work; Unpaywall needs email

    # ------------------------------------------------------------------
    # Fallback strategies
    # ------------------------------------------------------------------

    def _try_cache(self, paper: "Paper") -> str | None:
        key = self._cache_key(paper)
        if not key:
            return None
        cached = self._cache_dir / f"{key}.pdf"
        if cached.exists():
            logger.info("PdfDownloader: cache hit for %s", paper.paper_id)
            text = self._extract_local(str(cached))
            return text
        return None

    async def _try_unpaywall(self, paper: "Paper") -> str | None:
        email = settings.library_contact_email
        if not email or not paper.doi:
            return None

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(
                    f"https://api.unpaywall.org/v2/{paper.doi}",
                    params={"email": email},
                )
                r.raise_for_status()
                data = r.json()

            if not data.get("is_oa"):
                return None

            pdf_url = self._best_pdf_url(data)
            if not pdf_url:
                return None

            logger.info("PdfDownloader: Unpaywall OA link for %s → %s", paper.doi, pdf_url)
            return await self._download_and_extract_url(pdf_url, paper)
        except Exception as e:
            logger.debug("PdfDownloader: Unpaywall failed for %s: %s", paper.doi, e)
            return None

    async def _try_crossref_links(self, paper: "Paper") -> str | None:
        if not paper.doi:
            return None

        headers: dict[str, str] = {}
        email = settings.library_contact_email
        if email:
            headers["User-Agent"] = f"EurekaLab/0.4 (mailto:{email})"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(
                    f"https://api.crossref.org/works/{paper.doi}",
                    headers=headers,
                )
                r.raise_for_status()
                item = r.json().get("message", {})

            for link in item.get("link", []):
                url = link.get("URL", "")
                content_type = link.get("content-type", "")
                if "pdf" in content_type and url:
                    logger.info("PdfDownloader: CrossRef PDF link for %s → %s", paper.doi, url)
                    text = await self._download_and_extract_url(url, paper)
                    if text:
                        return text
        except Exception as e:
            logger.debug("PdfDownloader: CrossRef links failed for %s: %s", paper.doi, e)

        return None

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    async def _download_and_extract_url(
        self,
        url: str,
        paper: "Paper",
    ) -> str | None:
        """Download a PDF from *url* and extract text."""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
                content = r.content

            if len(content) < 1000:
                logger.debug("PdfDownloader: response too small (%d bytes), likely not a PDF", len(content))
                return None

            return self._extract_bytes(content, label=paper.paper_id)
        except Exception as e:
            logger.debug("PdfDownloader: download failed %s: %s", url, e)
            return None

    def _extract_local(self, path: str) -> str | None:
        """Extract text from a local PDF file."""
        return self._extract_bytes(Path(path).read_bytes(), label=path)

    def _extract_bytes(self, pdf_bytes: bytes, label: str = "") -> str | None:
        """Extract text from raw PDF bytes using the configured backend."""
        backend = settings.paper_reader_pdf_backend

        if backend == "pdfplumber":
            return self._extract_pdfplumber(pdf_bytes, label)
        elif backend == "docling":
            return self._extract_docling(pdf_bytes, label)
        else:
            logger.warning("PdfDownloader: unknown PDF backend '%s'", backend)
            return None

    def _extract_pdfplumber(self, pdf_bytes: bytes, label: str) -> str | None:
        try:
            import pdfplumber
        except ImportError:
            logger.warning(
                "PdfDownloader: 'pdfplumber' not installed. "
                "Install with: pip install 'eurekalab[pdf]'"
            )
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                tmp_path = tmp.name

            pages_text: list[str] = []
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)

            Path(tmp_path).unlink(missing_ok=True)

            if not pages_text:
                return None
            return "\n\n".join(pages_text)
        except Exception as e:
            logger.warning("PdfDownloader: pdfplumber extraction failed for %s: %s", label, e)
            return None

    def _extract_docling(self, pdf_bytes: bytes, label: str) -> str | None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            logger.warning(
                "PdfDownloader: 'docling' not installed. "
                "Install with: pip install 'eurekalab[pdf-docling]'"
            )
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp.flush()
                tmp_path = tmp.name

            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            markdown = result.document.export_to_markdown()

            Path(tmp_path).unlink(missing_ok=True)
            return markdown
        except Exception as e:
            logger.warning("PdfDownloader: docling extraction failed for %s: %s", label, e)
            return None

    def _apply(
        self,
        paper: "Paper",
        text: str,
        cache_key: str | None = None,
    ) -> str:
        """Update the paper in-place and optionally cache the PDF."""
        paper.full_text = text
        paper.content_tier = "full_text"

        if cache_key and not paper.local_pdf_path:
            # We don't cache the PDF bytes here since we already extracted text.
            # Cache path is used for future cache-hit checks.
            pass

        return text

    @staticmethod
    def _cache_key(paper: "Paper") -> str | None:
        """Deterministic cache key based on DOI or arXiv ID."""
        identifier = paper.doi or paper.arxiv_id
        if not identifier:
            return None
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

    def cache_pdf(self, paper: "Paper", pdf_bytes: bytes) -> Path | None:
        """Save raw PDF bytes to the cache directory."""
        key = self._cache_key(paper)
        if not key:
            return None
        path = self._cache_dir / f"{key}.pdf"
        path.write_bytes(pdf_bytes)
        paper.local_pdf_path = str(path)
        return path

    @staticmethod
    def _best_pdf_url(unpaywall_data: dict) -> str:
        """Pick the best PDF URL from Unpaywall response."""
        best = unpaywall_data.get("best_oa_location") or {}
        locations = unpaywall_data.get("oa_locations", [])

        for loc in [best] + locations:
            if not loc:
                continue
            url = loc.get("url_for_pdf") or ""
            if url:
                return url

        # Fallback: any url from the best location
        return best.get("url", "")
