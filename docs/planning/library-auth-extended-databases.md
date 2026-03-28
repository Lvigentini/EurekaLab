# Feature Plan: University Library Authentication & Extended Database Access

## Context

EurekaLab's literature search is currently limited to **arXiv** (the only source with automatic PDF download), **Semantic Scholar** (metadata + abstracts), **Gemini grounding** (web snippets), and **Brave/SerpAPI** (general web). Most researchers work at universities with browser-based authentication (EZproxy, Shibboleth, OpenAthens) that grants full-text access to IEEE, ACM, Springer, Elsevier, Wiley, and dozens more publishers. This feature bridges that gap by:

1. Adding free, high-value search sources (CrossRef, Unpaywall, OpenAlex) that require no authentication
2. Building a proxy-aware PDF download pipeline that routes through university library auth
3. Enhancing Zotero sync to include PDF attachments and bidirectional metadata

The result: papers that currently sit at `abstract` or `metadata` content tier can be upgraded to `full_text` automatically, dramatically improving the quality of theory extraction and proof development.

---

## Phase 1: Foundation — DOI Field + Free Sources (no auth needed)

### 1a. Add `doi` field to Paper model

**File:** `eurekalab/types/artifacts.py` (line 16-34)

The `Paper` model has no `doi` field. DOIs are the universal key for resolving paywalled content. Currently:
- Semantic Scholar returns DOIs (`externalIds.DOI`) but **drops them** (line 71 of `semantic_scholar.py`)
- Zotero adapter reads `data["DOI"]` but only uses it for URL construction
- CrossRef, Unpaywall, and OpenAlex all key on DOI

**Change:** Add `doi: str | None = None` after `semantic_scholar_id` (line 24).

**Propagation:** Update these consumers to populate/use `doi`:
- `eurekalab/tools/semantic_scholar.py` — add `"doi": (p.get("externalIds") or {}).get("DOI", "")` to the returned dict
- `eurekalab/agents/survey/agent.py` — parse `doi` from tool output when constructing Paper objects
- `eurekalab/integrations/zotero/adapter.py` — set `doi=data.get("DOI", "")` in `_item_to_paper()`
- `eurekalab/analyzers/bib_loader.py` — extract DOI from bib entries (`doi` field in BibTeX)

### 1b. CrossRef search tool

**New file:** `eurekalab/tools/crossref.py`

CrossRef is the canonical DOI registry (130M+ records). No API key required; a contact email gets polite-pool access (faster rate limits).

```python
class CrossRefTool(BaseTool):
    name = "crossref_search"
    # Two modes:
    #   query="search terms" → search across all DOIs
    #   doi="10.1234/..." → resolve specific DOI (returns publisher links)
    # Returns: title, authors, year, doi, venue, type, publisher_url, license
    # Critical: the "link" array in responses contains full-text PDF URLs
```

- **API:** `https://api.crossref.org/works?query=...` (search) or `https://api.crossref.org/works/{doi}` (lookup)
- **Rate limit:** Polite pool with `mailto:` header → ~50 req/s
- **Config:** `LIBRARY_CONTACT_EMAIL` in config.py (recommended but optional)

### 1c. Unpaywall tool

**New file:** `eurekalab/tools/unpaywall.py`

Unpaywall finds legal open-access copies for any DOI. Returns direct PDF URLs from repositories, preprint servers, and author pages.

```python
class UnpaywallTool(BaseTool):
    name = "unpaywall_lookup"
    # Input: doi (required)
    # Returns: is_oa, best_oa_url, oa_status (gold/green/hybrid/bronze),
    #          pdf_url (direct link if available), host_type (publisher/repository)
```

- **API:** `https://api.unpaywall.org/v2/{doi}?email=...`
- **Rate limit:** 100K/day with email
- **Config:** Reuses `LIBRARY_CONTACT_EMAIL`

### 1d. PDF cache + centralized downloader

**New file:** `eurekalab/services/pdf_downloader.py`

Currently, PDF download logic is scattered across:
- `paper_reader.py` (arXiv PDFs)
- `cli.py` (Zotero/bib local PDFs)
- `bib_loader.py` (local PDF matching)

Centralize into `PdfDownloader` with a cascading fallback strategy:

```
1. Local cache (~/.eurekalab/pdf_cache/{doi_hash}.pdf)
2. local_pdf_path (already set by bib_loader or Zotero)
3. arXiv (if paper.arxiv_id → https://arxiv.org/pdf/{id})
4. Unpaywall (if paper.doi → free OA PDF)
5. CrossRef links (if paper.doi → publisher full-text URLs)
6. University proxy (Phase 2 — if configured)
7. Direct URL (paper.url as last resort)
```

Each step returns on first success. All downloaded PDFs are cached locally.

**Config additions to `eurekalab/config.py`:**
```python
library_contact_email: str = Field(default="", alias="LIBRARY_CONTACT_EMAIL")
pdf_cache_dir: str = Field(default="", alias="PDF_CACHE_DIR")  # default: ~/.eurekalab/pdf_cache
pdf_download_timeout: int = Field(default=60, alias="PDF_DOWNLOAD_TIMEOUT")
```

### 1e. Register new tools

**File:** `eurekalab/tools/registry.py` — add `CrossRefTool()` and `UnpaywallTool()` to `build_default_registry()`

**File:** `eurekalab/agents/survey/agent.py` — add `"crossref_search"` and `"unpaywall_lookup"` to the survey agent's tool list

---

## Phase 2: University Library Proxy Authentication

### 2a. Proxy configuration

**New file:** `eurekalab/integrations/library/__init__.py`
**New file:** `eurekalab/integrations/library/proxy.py`

University proxy authentication comes in several flavours, all of which ultimately produce HTTP cookies:

| Method | How it works | Config needed |
|--------|-------------|---------------|
| **EZproxy prefix** | Prepend `https://ezproxy.lib.edu/login?url=` to any URL | `LIBRARY_PROXY_URL` |
| **EZproxy suffix** | Rewrite `doi.org` → `doi-org.ezproxy.lib.edu` | `LIBRARY_PROXY_URL` + `LIBRARY_PROXY_MODE=suffix` |
| **Shibboleth/SAML** | Browser SSO → session cookie | Cookie import |
| **OpenAthens** | Cloud SSO → session cookie | Cookie import |
| **VPN** | No URL rewriting needed; direct access | `LIBRARY_PROXY_MODE=vpn` |

```python
class ProxyRewriter:
    """Rewrites publisher URLs to route through university proxy."""
    def __init__(self, proxy_url: str, mode: str = "prefix"):
        # mode: "prefix", "suffix", "vpn" (no-op), "none" (disabled)

    def rewrite(self, url: str) -> str:
        # prefix: f"{proxy_url}{url}"
        # suffix: replace domain dots with hyphens, append proxy domain
        # vpn: return url unchanged (access is network-level)

class AuthenticatedSession:
    """HTTP client with university library session cookies."""
    def __init__(self, proxy: ProxyRewriter, cookies: dict[str, str] | None = None):
        # Wraps httpx.AsyncClient with proxy rewriting + session cookies

    async def get(self, url: str, **kwargs) -> httpx.Response:
        # Rewrite URL through proxy, attach cookies, follow redirects

    @classmethod
    def from_cookie_file(cls, proxy: ProxyRewriter) -> "AuthenticatedSession":
        # Load cookies from ~/.eurekalab/library_session.json
```

**Config additions:**
```python
library_proxy_url: str = Field(default="", alias="LIBRARY_PROXY_URL")
library_proxy_mode: Literal["prefix", "suffix", "vpn", "none"] = Field(
    default="none", alias="LIBRARY_PROXY_MODE"
)
```

### 2b. Cookie import CLI command

**File:** `eurekalab/cli.py` — new `library-auth` command group

```bash
# Set EZproxy URL (one-time setup)
eurekalab library-auth set-proxy "https://ezproxy.library.edu/login?url="

# Import cookies from browser (user copies from DevTools)
eurekalab library-auth set-cookie "ezproxy=ABC123; domain=.library.edu"

# Import cookies from a Netscape cookie file (exported by browser extensions)
eurekalab library-auth import-cookies cookies.txt

# Test: try downloading a known paywalled DOI
eurekalab library-auth test "10.1109/TIT.2023.1234567"

# Show current auth status
eurekalab library-auth status
```

Cookies stored in `~/.eurekalab/library_session.json`:
```json
{
  "proxy_url": "https://ezproxy.library.edu/login?url=",
  "proxy_mode": "prefix",
  "cookies": {"ezproxy": "ABC123", "EZproxySID": "xyz"},
  "updated_at": "2026-03-28T10:00:00"
}
```

### 2c. Wire proxy into PdfDownloader

The `PdfDownloader` from Phase 1 already has step 6 reserved for proxy access. Wire in `AuthenticatedSession`:

```python
# In PdfDownloader._try_proxy_download():
if settings.library_proxy_url:
    session = AuthenticatedSession.from_cookie_file(proxy)
    # Resolve DOI → publisher URL → rewrite through proxy → download
```

### 2d. Publisher-specific PDF URL patterns

**New file:** `eurekalab/integrations/library/publishers.py`

Publishers have different URL patterns for direct PDF access. After resolving a DOI to a landing page, we need heuristics to find the actual PDF link:

```python
PUBLISHER_PDF_PATTERNS = {
    "ieee": {
        "domain": "ieeexplore.ieee.org",
        "pdf_path": "/stamp/stamp.jsp?tp=&arnumber={id}",
        "extract_id": r"/document/(\d+)",
    },
    "acm": {
        "domain": "dl.acm.org",
        "pdf_path": "/doi/pdf/{doi}",
    },
    "springer": {
        "domain": "link.springer.com",
        "pdf_path": "/content/pdf/{doi}.pdf",
    },
    "elsevier": {
        "domain": "sciencedirect.com",
        "pdf_path": "/science/article/pii/{pii}/pdf",  # or via API
    },
    "wiley": {
        "domain": "onlinelibrary.wiley.com",
        "pdf_path": "/doi/pdfdirect/{doi}",
    },
    "taylor_francis": {
        "domain": "tandfonline.com",
        "pdf_path": "/doi/pdf/{doi}",
    },
    "sage": {
        "domain": "journals.sagepub.com",
        "pdf_path": "/doi/pdf/{doi}",
    },
}
```

The `PdfDownloader` matches the publisher domain from the DOI redirect, applies the pattern, rewrites through proxy, and downloads.

---

## Phase 3: Pipeline Integration

### 3a. PaperReader refactor

**File:** `eurekalab/agents/theory/paper_reader.py`

Currently, PaperReader only downloads PDFs for papers with `arxiv_id` (line ~298). Refactor to use `PdfDownloader`:

```python
# Before (current):
if settings.paper_reader_use_pdf and pdf_successes < target and paper.arxiv_id:
    text = self._fetch_pdf_pdfplumber(paper.arxiv_id, paper.title)

# After:
if settings.paper_reader_use_pdf and pdf_successes < target:
    text = await pdf_downloader.download_and_extract(paper)
    # Works for any paper with arxiv_id, doi, or url
```

Remove `_fetch_pdf_pdfplumber()` and `_fetch_pdf_docling()` from PaperReader — they move into `PdfDownloader`.

### 3b. Content gap handler enhancement

**File:** `eurekalab/orchestrator/meta_orchestrator.py` — `_handle_content_gaps()`

Currently prompts user for a PDF directory. Add automatic download attempt before prompting:

```python
# After gap analysis, before prompting user:
if pdf_downloader.is_configured():
    for paper in gap_report.abstract_only + gap_report.metadata_only:
        if paper.doi or paper.arxiv_id:
            await pdf_downloader.download_and_extract(paper)
    # Re-run gap analysis
    gap_report = ContentGapAnalyzer.analyze(bib)
    if not gap_report.has_gaps:
        return  # All gaps filled automatically
```

### 3c. Survey agent — DOI enrichment pass

**File:** `eurekalab/agents/survey/agent.py`

After the survey agent discovers papers, run a DOI enrichment pass:
1. For papers without `doi`, query CrossRef by title to resolve DOI
2. For papers with `doi`, query Unpaywall for OA status
3. Update `Paper.doi` and flag OA papers for priority download

---

## Phase 4: Enhanced Zotero Sync

### 4a. PDF attachment upload

**File:** `eurekalab/integrations/zotero/adapter.py`

Add method to upload PDFs as Zotero attachments:

```python
def upload_pdf_attachment(self, parent_key: str, pdf_path: str, title: str = "") -> str | None:
    """Upload a PDF file as a child attachment to a Zotero item."""
    # Uses pyzotero's Zotero.attachment_simple() or upload_attachment()
    # Returns attachment key or None
```

### 4b. Download Zotero cloud attachments

Currently, Zotero PDF access requires `ZOTERO_LOCAL_DATA_DIR` (a local Zotero data folder). Add cloud download:

```python
def download_attachment(self, item_key: str, save_dir: Path) -> str | None:
    """Download the first PDF attachment from Zotero cloud storage."""
    # Uses pyzotero's Zotero.file(item_key) to get the file content
    # Saves to save_dir/{item_key}.pdf
    # Returns path or None
```

### 4c. Bidirectional sync improvements

**File:** `eurekalab/cli.py` — enhance `push-to-zotero`

- Upload cached PDFs for newly discovered papers (not just metadata)
- Persist `zotero_item_key` back to bibliography after push (currently lost)
- Attach session notes to all source papers (not just the first one)

---

## Phase 5: OpenAlex Search Tool

**New file:** `eurekalab/tools/openalex.py`

OpenAlex is a free, comprehensive academic graph (250M+ works). Adds:
- Richer metadata (concepts, topics, related works, cited_by_count)
- `open_access.oa_url` — direct OA link for many papers
- Institution-level affiliation data
- No API key required (polite pool with email)

```python
class OpenAlexTool(BaseTool):
    name = "openalex_search"
    # Input: query, filter (by year, type, concept, etc.)
    # Returns: title, authors, year, doi, oa_url, cited_by_count, concepts, venue
```

- **API:** `https://api.openalex.org/works?search=...`
- **Config:** Reuses `LIBRARY_CONTACT_EMAIL` for polite pool

---

## File Change Summary

### New files
| File | Purpose |
|------|---------|
| `eurekalab/tools/crossref.py` | CrossRef search + DOI resolution |
| `eurekalab/tools/unpaywall.py` | Unpaywall OA PDF lookup |
| `eurekalab/tools/openalex.py` | OpenAlex academic search (Phase 5) |
| `eurekalab/services/pdf_downloader.py` | Centralized PDF download with cascading fallback |
| `eurekalab/integrations/library/__init__.py` | Library auth package |
| `eurekalab/integrations/library/proxy.py` | ProxyRewriter + AuthenticatedSession |
| `eurekalab/integrations/library/publishers.py` | Publisher-specific PDF URL patterns |
| `tests/test_crossref.py` | Unit tests for CrossRef tool |
| `tests/test_unpaywall.py` | Unit tests for Unpaywall tool |
| `tests/test_pdf_downloader.py` | Unit tests for PdfDownloader cascade |
| `tests/test_library_proxy.py` | Unit tests for proxy rewriting + auth |

### Modified files
| File | Change |
|------|--------|
| `eurekalab/types/artifacts.py` | Add `doi: str \| None = None` to Paper |
| `eurekalab/tools/semantic_scholar.py` | Propagate DOI from `externalIds` |
| `eurekalab/tools/registry.py` | Register CrossRefTool, UnpaywallTool, OpenAlexTool |
| `eurekalab/agents/survey/agent.py` | Add new tools to agent; DOI enrichment pass |
| `eurekalab/agents/theory/paper_reader.py` | Delegate PDF download to PdfDownloader |
| `eurekalab/integrations/zotero/adapter.py` | Add upload_pdf_attachment, download_attachment |
| `eurekalab/analyzers/bib_loader.py` | Extract DOI from bib entries |
| `eurekalab/orchestrator/meta_orchestrator.py` | Auto-download before gap prompt |
| `eurekalab/config.py` | Add library/proxy/cache config fields |
| `eurekalab/cli.py` | Add `library-auth` command group |

### Configuration (all new env vars)
| Variable | Default | Purpose |
|----------|---------|---------|
| `LIBRARY_CONTACT_EMAIL` | `""` | Email for CrossRef/Unpaywall/OpenAlex polite pool |
| `LIBRARY_PROXY_URL` | `""` | University proxy URL (e.g., `https://ezproxy.lib.edu/login?url=`) |
| `LIBRARY_PROXY_MODE` | `"none"` | Proxy mode: `prefix`, `suffix`, `vpn`, `none` |
| `PDF_CACHE_DIR` | `""` | PDF cache directory (default: `~/.eurekalab/pdf_cache`) |
| `PDF_DOWNLOAD_TIMEOUT` | `60` | HTTP timeout for PDF downloads (seconds) |
| `PDF_AUTO_DOWNLOAD` | `true` | Auto-download PDFs during content gap analysis |

---

## Verification

### Phase 1 verification
```bash
# Unit tests
pytest tests/test_crossref.py tests/test_unpaywall.py tests/test_pdf_downloader.py -v

# Integration test (requires network)
LIBRARY_CONTACT_EMAIL=user@university.edu eurekalab explore "attention mechanisms" --domain "deep learning"
# → Check bibliography for papers with doi field populated
# → Check ~/.eurekalab/pdf_cache/ for cached OA PDFs
# → Check content_gap report shows more full_text papers than before
```

### Phase 2 verification
```bash
# Configure proxy
eurekalab library-auth set-proxy "https://ezproxy.library.edu/login?url="
eurekalab library-auth set-cookie "ezproxy=YOUR_SESSION_COOKIE"

# Test download of a known paywalled paper
eurekalab library-auth test "10.1109/TIT.2023.1234567"

# Full pipeline test
eurekalab from-papers 2401.12345 --domain "information theory"
# → Check that paywalled references get full_text tier via proxy
```

### Phase 3 verification
```bash
# Run a session and verify PaperReader uses PdfDownloader
eurekalab prove "conjecture about X" --domain "algebra"
# → Check logs for "Downloaded PDF via unpaywall" / "Downloaded PDF via proxy"
# → Verify KnownResult extraction_source includes "pdf_result_sections" for non-arXiv papers
```

### Phase 4 verification
```bash
# Zotero bidirectional sync
eurekalab from-zotero COLLECTION_ID --domain "ML theory"
# → Run session → discover new papers
eurekalab push-to-zotero SESSION_ID --collection "Results"
# → Check Zotero: new papers should have PDF attachments
# → Check bibliography.json: zotero_item_key persisted for pushed papers
```

---

## Risk & Mitigations

| Risk | Mitigation |
|------|------------|
| University cookies expire (typically 1-24h) | `library-auth status` warns when cookies are stale; clear error messages prompting re-auth |
| Publisher rate limiting / IP blocking | Respectful delays (1-2s between publisher requests), configurable concurrency |
| Publisher ToS concerns | Only download for personal research use; respect robots.txt; rate limit |
| Cookie security (stored in plaintext) | Store in `~/.eurekalab/` with 600 permissions; warn user in docs |
| Proxy URL varies wildly across universities | Support prefix/suffix/vpn modes; test command validates setup |
| PDF extraction quality varies by publisher | Existing pdfplumber/docling backends handle this; no change needed |

---

## Implementation Priority

**Phase 1** (immediate value, no auth): DOI field + CrossRef + Unpaywall + PdfDownloader + cache
- Many papers get free full-text via Unpaywall OA without any university credentials
- Estimated: ~40-60% of recent CS papers have OA copies

**Phase 2** (core ask): University proxy auth
- Unlocks the remaining paywalled content
- EZproxy prefix mode covers ~80% of university setups

**Phase 3** (pipeline wiring): PaperReader + content gap auto-download
- Makes everything work automatically within the existing pipeline

**Phase 4** (sync quality): Zotero PDF attachments + bidirectional improvements

**Phase 5** (discovery breadth): OpenAlex for richer metadata and discovery
