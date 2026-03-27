"""Lightweight UI server for the EurekaLab control center."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import subprocess as _subprocess
import sys as _sys

from eurekalab.ccproxy_manager import maybe_start_ccproxy, stop_ccproxy, is_ccproxy_available, check_ccproxy_auth, _oauth_install_hint
from eurekalab.config import settings
from eurekalab.llm import create_client
from eurekalab.main import EurekaSession, save_artifacts, _compile_pdf
from eurekalab.skills.registry import SkillRegistry
from eurekalab.types.tasks import InputSpec, ResearchOutput, TaskStatus

logger = logging.getLogger(__name__)

_ROOT_DIR = Path(__file__).resolve().parents[2]
_FRONTEND_DIR = Path(__file__).resolve().parent / "static"
_DEV_FRONTEND_DIR = _ROOT_DIR / "frontend"
_ENV_PATH = _ROOT_DIR / ".env"

_CONFIG_FIELDS: dict[str, str] = {
    "llm_backend": "LLM_BACKEND",
    "anthropic_auth_mode": "ANTHROPIC_AUTH_MODE",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "eurekalab_model": "EUREKALAB_MODEL",
    "eurekalab_fast_model": "EUREKALAB_FAST_MODEL",
    "openai_compat_base_url": "OPENAI_COMPAT_BASE_URL",
    "openai_compat_api_key": "OPENAI_COMPAT_API_KEY",
    "openai_compat_model": "OPENAI_COMPAT_MODEL",
    "minimax_api_key": "MINIMAX_API_KEY",
    "minimax_model": "MINIMAX_MODEL",
    "eurekalab_mode": "EUREKALAB_MODE",
    "gate_mode": "GATE_MODE",
    "experiment_mode": "EXPERIMENT_MODE",
    "ccproxy_port": "CCPROXY_PORT",
    "theory_pipeline": "THEORY_PIPELINE",
    "theory_max_iterations": "THEORY_MAX_ITERATIONS",
    "auto_verify_confidence": "AUTO_VERIFY_CONFIDENCE",
    "verifier_pass_confidence": "VERIFIER_PASS_CONFIDENCE",
    "output_format": "OUTPUT_FORMAT",
    "paper_reader_use_pdf": "PAPER_READER_USE_PDF",
    "paper_reader_abstract_papers": "PAPER_READER_ABSTRACT_PAPERS",
    "paper_reader_pdf_papers": "PAPER_READER_PDF_PAPERS",
    "eurekalab_dir": "EUREKACLAW_DIR",
    # Token limits
    "max_tokens_agent": "MAX_TOKENS_AGENT",
    "max_tokens_prover": "MAX_TOKENS_PROVER",
    "max_tokens_planner": "MAX_TOKENS_PLANNER",
    "max_tokens_decomposer": "MAX_TOKENS_DECOMPOSER",
    "max_tokens_assembler": "MAX_TOKENS_ASSEMBLER",
    "max_tokens_formalizer": "MAX_TOKENS_FORMALIZER",
    "max_tokens_crystallizer": "MAX_TOKENS_CRYSTALLIZER",
    "max_tokens_architect": "MAX_TOKENS_ARCHITECT",
    "max_tokens_analyst": "MAX_TOKENS_ANALYST",
    "max_tokens_sketch": "MAX_TOKENS_SKETCH",
    "max_tokens_verifier": "MAX_TOKENS_VERIFIER",
    "max_tokens_compress": "MAX_TOKENS_COMPRESS",
    "max_tokens_crystallizer": "MAX_TOKENS_CRYSTALLIZER",
    "max_tokens_assembler": "MAX_TOKENS_ASSEMBLER",
    "max_tokens_architect": "MAX_TOKENS_ARCHITECT",
    "max_tokens_analyst": "MAX_TOKENS_ANALYST",
    "max_tokens_sketch": "MAX_TOKENS_SKETCH",
}


@dataclass
class SessionRun:
    """Tracks a running or completed session for UI polling."""

    run_id: str
    input_spec: InputSpec
    name: str = ""
    # Statuses: queued → running → pausing → paused → resuming → running → completed
    #           any of the above → failed
    status: str = "queued"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    pause_requested_at: datetime | None = None  # set when status → "pausing"
    paused_stage: str = ""                       # stage name where proof stopped
    theory_feedback: str = ""                    # user guidance injected on next theory resume
    error: str = ""
    result: ResearchOutput | None = None
    eureka_session: EurekaSession | None = None
    eureka_session_id: str = ""
    output_summary: dict[str, Any] = field(default_factory=dict)
    output_dir: str = ""


def _serialize_value(value: Any) -> Any:
    """Convert Pydantic models and datetimes into JSON-safe data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _capability_status(available: bool, detail: str, *, optional: bool = False) -> dict[str, str]:
    if available:
        return {"status": "available", "detail": detail}
    if optional:
        return {"status": "optional", "detail": detail}
    return {"status": "missing", "detail": detail}


def _infer_capabilities() -> dict[str, dict[str, str]]:
    """Inspect the local environment for the UI status surface."""
    python_detail = f"Python {os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
    model_ready = bool(
        settings.anthropic_api_key
        or settings.openai_compat_api_key
        or settings.anthropic_auth_mode == "oauth"
    )
    return {
        "python": _capability_status(True, python_detail),
        "package_install": _capability_status(True, "Repository checkout available"),
        "model_access": _capability_status(
            model_ready,
            "Model credentials configured" if model_ready else "No model credentials configured",
        ),
        "lean4": _capability_status(
            shutil.which(settings.lean4_bin) is not None,
            f"{settings.lean4_bin} found in PATH" if shutil.which(settings.lean4_bin) else "Lean4 binary not found",
            optional=True,
        ),
        "latex": _capability_status(
            shutil.which(settings.latex_bin) is not None,
            f"{settings.latex_bin} found in PATH" if shutil.which(settings.latex_bin) else "LaTeX binary not found",
            optional=True,
        ),
        "docker": _capability_status(
            shutil.which("docker") is not None,
            "Docker available" if shutil.which("docker") else "Docker not found",
            optional=True,
        ),
        "skills_dir": _capability_status(
            settings.skills_dir.exists(),
            str(settings.skills_dir),
            optional=True,
        ),
    }


def _load_env_lines(env_path: Path) -> list[str]:
    if not env_path.exists():
        return []
    return env_path.read_text().splitlines()


def _write_env_updates(env_path: Path, updates: dict[str, str]) -> None:
    """Update or append selected .env keys without dropping unrelated lines."""
    lines = _load_env_lines(env_path)
    index_map = {
        line.split("=", 1)[0]: idx
        for idx, line in enumerate(lines)
        if "=" in line and not line.lstrip().startswith("#")
    }

    for key, value in updates.items():
        rendered = f"{key}={value}"
        if key in index_map:
            lines[index_map[key]] = rendered
        else:
            lines.append(rendered)

    env_path.write_text("\n".join(lines) + ("\n" if lines else ""))


class UIServerState:
    """In-memory state for UI sessions and configuration."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.runs: dict[str, SessionRun] = {}
        self._load_persisted_runs()

    # ── Persistence helpers ──────────────────────────────────────────────────

    def _sessions_dir(self) -> Path:
        d = settings.eurekalab_dir / "ui_sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _persist_run(self, run: SessionRun) -> None:
        """Write run metadata to disk so sessions survive server restarts."""
        try:
            data: dict[str, Any] = {
                "run_id": run.run_id,
                "name": run.name,
                "status": run.status,
                "error": run.error,
                "eureka_session_id": run.eureka_session_id,
                "created_at": run.created_at.isoformat(),
                "updated_at": run.updated_at.isoformat(),
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "paused_at": run.paused_at.isoformat() if run.paused_at else None,
                "pause_requested_at": run.pause_requested_at.isoformat() if run.pause_requested_at else None,
                "paused_stage": run.paused_stage,
                "theory_feedback": run.theory_feedback,
                "input_spec": _serialize_value(run.input_spec),
                "output_dir": run.output_dir,
                "output_summary": _serialize_value(run.output_summary),
            }
            path = self._sessions_dir() / f"{run.run_id}.json"
            path.write_text(json.dumps(data, indent=2))
        except Exception:
            logger.warning("Failed to persist run %s", run.run_id, exc_info=True)

    def _load_persisted_runs(self) -> None:
        """Load previously persisted sessions from disk on startup.

        Sources (merged, UI sessions take priority):
        1. UI session files (~/.eurekalab/ui_sessions/*.json)
        2. CLI sessions discovered from runs/ directory artifacts
        3. SQLite DB sessions (for metadata like domain/query)
        """
        # 1. UI sessions (existing behavior)
        sessions_dir = settings.eurekalab_dir / "ui_sessions"
        if sessions_dir.exists():
            for path in sorted(sessions_dir.glob("*.json")):
                try:
                    data = json.loads(path.read_text())
                    input_spec = InputSpec.model_validate(data.get("input_spec", {}))
                    run = SessionRun(
                        run_id=data["run_id"],
                        input_spec=input_spec,
                        name=data.get("name", ""),
                        status=data.get("status", "failed"),
                        error=data.get("error", ""),
                        eureka_session_id=data.get("eureka_session_id", ""),
                        paused_stage=data.get("paused_stage", ""),
                        theory_feedback=data.get("theory_feedback", ""),
                        output_dir=data.get("output_dir", ""),
                        output_summary=data.get("output_summary", {}),
                    )
                    for ts_field in ("created_at", "updated_at", "started_at", "completed_at",
                                     "paused_at", "pause_requested_at"):
                        raw = data.get(ts_field)
                        if raw:
                            try:
                                setattr(run, ts_field, datetime.fromisoformat(raw))
                            except ValueError:
                                pass
                    if run.status in ("running", "queued", "pausing", "resuming"):
                        run.status = "failed"
                        run.error = "Session interrupted by a server restart."
                    self.runs[run.run_id] = run
                except Exception:
                    logger.warning("Failed to load persisted run from %s", path, exc_info=True)

        # 2. CLI sessions from runs/ directory (not already loaded from UI sessions)
        runs_dir = settings.runs_dir
        if runs_dir.exists():
            for run_dir in sorted(runs_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                session_id = run_dir.name
                # Skip if already loaded from UI sessions
                if any(r.eureka_session_id == session_id or r.run_id == session_id for r in self.runs.values()):
                    continue
                # Must have at least a research_brief or stage progress to be a valid session
                brief_path = run_dir / "research_brief.json"
                progress_path = run_dir / "_stage_progress.json"
                if not brief_path.exists() and not progress_path.exists():
                    continue
                try:
                    # Read brief for metadata
                    domain = ""
                    query = ""
                    mode = "exploration"
                    if brief_path.exists():
                        brief_data = json.loads(brief_path.read_text())
                        domain = brief_data.get("domain", "")
                        query = brief_data.get("query", "")
                        mode = brief_data.get("input_mode", "exploration")

                    # Read stage progress for status
                    status = "completed"
                    completed_stages: list[str] = []
                    if progress_path.exists():
                        prog_data = json.loads(progress_path.read_text())
                        completed_stages = prog_data.get("completed_stages", [])
                        if any("FAILED" in s for s in completed_stages):
                            status = "failed"
                        elif "writer" not in completed_stages:
                            status = "paused"

                    input_spec = InputSpec(mode=mode, domain=domain, query=query)
                    run = SessionRun(
                        run_id=session_id,
                        input_spec=input_spec,
                        name=domain[:40] if domain else session_id[:12],
                        status=status,
                        eureka_session_id=session_id,
                        output_dir=str(run_dir),
                    )
                    # Use directory mtime as created_at
                    run.created_at = datetime.fromtimestamp(run_dir.stat().st_mtime)
                    self.runs[session_id] = run
                    logger.info("Discovered CLI session: %s (%s) — %s", session_id[:12], domain[:30], status)
                except Exception:
                    logger.warning("Failed to load CLI session from %s", run_dir, exc_info=True)

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create_run(self, input_spec: InputSpec) -> SessionRun:
        run = SessionRun(run_id=str(uuid.uuid4()), input_spec=input_spec)
        with self._lock:
            self.runs[run.run_id] = run
        self._persist_run(run)
        return run

    def delete_run(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            return {"error": "Run not found"}
        if run.status in ("running", "queued"):
            return {"error": "Cannot delete a running session — pause or wait for it to finish first"}
        with self._lock:
            self.runs.pop(run_id, None)
        path = self._sessions_dir() / f"{run_id}.json"
        try:
            path.unlink(missing_ok=True)
        except Exception:
            logger.warning("Failed to remove persisted run file %s", path)
        return {"ok": True, "run_id": run_id}

    def rename_run(self, run_id: str, name: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            return {"error": "Run not found"}
        run.name = name.strip()[:80]
        run.updated_at = datetime.utcnow()
        self._persist_run(run)
        return {"ok": True, "run_id": run_id, "name": run.name}

    def restart_run(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            return {"error": "Run not found"}
        if run.status in ("running", "queued"):
            return {"error": f"Cannot restart a {run.status} session"}
        new_run = self.create_run(run.input_spec)
        new_run.name = run.name  # carry the custom name if any
        self._persist_run(new_run)
        self.start_run(new_run)
        return self.snapshot_run(new_run)

    def rerun_run(self, run_id: str, *, updated_skills: list[str] | None = None) -> dict[str, Any]:
        """Reset the same run in-place and re-execute with the original input_spec.

        If *updated_skills* is provided, the input_spec.selected_skills list
        is replaced so the user can add/remove skills between re-runs.
        """
        run = self.get_run(run_id)
        if run is None:
            return {"error": "Run not found"}
        if run.status in ("running", "queued"):
            return {"error": f"Cannot re-run a {run.status} session"}
        # Update skills if the frontend sent a new list
        if updated_skills is not None:
            run.input_spec.selected_skills = updated_skills
        # Reset all mutable state, keep run_id, input_spec, name
        run.status = "queued"
        run.created_at = datetime.utcnow()
        run.updated_at = datetime.utcnow()
        run.started_at = None
        run.completed_at = None
        run.paused_at = None
        run.pause_requested_at = None
        run.paused_stage = ""
        run.theory_feedback = ""
        run.error = ""
        run.result = None
        run.eureka_session = None
        run.eureka_session_id = ""
        run.output_summary = {}
        run.output_dir = ""
        self._persist_run(run)
        self.start_run(run)
        return self.snapshot_run(run)

    def get_run(self, run_id: str) -> SessionRun | None:
        with self._lock:
            return self.runs.get(run_id)

    def list_runs(self) -> list[SessionRun]:
        with self._lock:
            return sorted(self.runs.values(), key=lambda run: run.created_at, reverse=True)

    def start_run(self, run: SessionRun) -> None:
        thread = threading.Thread(target=self._execute_run, args=(run.run_id,), daemon=True)
        thread.start()

    def pause_run(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            return {"error": "Run not found"}
        if run.status not in ("running",):
            return {"error": f"Run is not running (status: {run.status})"}
        if not run.eureka_session_id:
            return {"error": "No active theory session to pause"}
        from eurekalab.agents.theory.checkpoint import ProofCheckpoint
        cp = ProofCheckpoint(run.eureka_session_id)
        cp.request_pause()
        # Immediately reflect the intermediate state so the frontend can poll it
        run.status = "pausing"
        run.pause_requested_at = datetime.utcnow()
        run.updated_at = datetime.utcnow()
        self._persist_run(run)
        return {"ok": True, "session_id": run.eureka_session_id, "status": "pausing"}

    def resume_run(self, run_id: str, feedback: str = "") -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            return {"error": "Run not found"}
        if run.status != "paused":
            return {"error": f"Run is not paused (status: {run.status})"}
        if not run.eureka_session_id:
            return {"error": "No checkpoint session ID found"}
        from eurekalab.agents.theory.checkpoint import ProofCheckpoint
        cp = ProofCheckpoint(run.eureka_session_id)
        if not cp.exists():
            return {"error": f"No checkpoint found for session '{run.eureka_session_id}'"}
        # Store user guidance to be injected into the theory context on resume
        if feedback:
            run.theory_feedback = feedback.strip()[:2000]
        # Transition to intermediate "resuming" state before the thread starts
        run.status = "resuming"
        run.updated_at = datetime.utcnow()
        self._persist_run(run)
        thread = threading.Thread(target=self._execute_resume, args=(run_id,), daemon=True)
        thread.start()
        return {"ok": True, "session_id": run.eureka_session_id, "status": "resuming"}

    def _execute_resume(self, run_id: str) -> None:
        from eurekalab.agents.theory.checkpoint import ProofCheckpoint, ProofPausedException
        from eurekalab.agents.theory.inner_loop_yaml import TheoryInnerLoopYaml
        from eurekalab.memory.manager import MemoryManager
        from eurekalab.skills.injector import SkillInjector
        from eurekalab.skills.registry import SkillRegistry

        run = self.get_run(run_id)
        if run is None:
            return

        run.status = "running"
        run.paused_at = None
        run.pause_requested_at = None
        run.paused_stage = ""
        run.updated_at = datetime.utcnow()
        self._persist_run(run)

        try:
            session = run.eureka_session
            if session is None:
                raise ValueError("Session object not available for resume")

            session_id = run.eureka_session_id
            cp = ProofCheckpoint(session_id)
            state, meta = cp.load()
            cp.clear_pause_flag()

            # Restore checkpoint theory state into the existing bus (which still has
            # survey / ideation / planning data from the original run).
            session.bus.put_theory_state(state)

            domain = meta.get("domain", "")

            # Inject user guidance if provided via the UI feedback dialog
            if run.theory_feedback:
                domain = domain + f"\n\n[Human guidance for this proof attempt]: {run.theory_feedback}"
                run.theory_feedback = ""   # consume — clear after use
                self._persist_run(run)

            memory = MemoryManager(session_id=session_id)
            skill_injector = SkillInjector(SkillRegistry())
            inner_loop = TheoryInnerLoopYaml(
                bus=session.bus,
                skill_injector=skill_injector,
                memory=memory,
            )

            config = _config_payload()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                with _temporary_auth_env(config):
                    final_state = loop.run_until_complete(
                        inner_loop.run(session_id, domain=domain)
                    )
                    session.bus.put_theory_state(final_state)
            finally:
                loop.close()
                asyncio.set_event_loop(None)

            run.status = "completed"
            run.output_summary = {"resumed": True, "session_id": session_id}

        except Exception as exc:
            from eurekalab.agents.theory.checkpoint import ProofPausedException  # noqa: F811
            if isinstance(exc, ProofPausedException):
                logger.info("Session %s paused again at stage '%s'", run_id, exc.stage_name)
                run.status = "paused"
                run.paused_at = datetime.utcnow()
                run.paused_stage = exc.stage_name
                run.pause_requested_at = None
                run.error = ""
            else:
                logger.exception("UI session resume failed")
                run.status = "failed"
                run.error = str(exc)
        finally:
            run.completed_at = datetime.utcnow()
            run.updated_at = datetime.utcnow()
            self._persist_run(run)

    @staticmethod
    def _preprocess_input_mode(session: EurekaSession, spec: InputSpec) -> None:
        """Pre-populate the session bus for alternative entry modes (from_bib, from_draft, from_zotero)."""
        from eurekalab.types.artifacts import Bibliography

        mode = spec.mode

        if mode == "from_bib" and spec.bib_content:
            import tempfile
            from eurekalab.analyzers.bib_loader import BibLoader
            # Parse bib content from the UI textarea
            with tempfile.NamedTemporaryFile(mode="w", suffix=".bib", delete=False) as f:
                f.write(spec.bib_content)
                bib_path = Path(f.name)
            try:
                papers = BibLoader.load_bib(bib_path)
            finally:
                bib_path.unlink(missing_ok=True)
            if spec.pdf_dir:
                papers = BibLoader.match_pdfs(papers, Path(spec.pdf_dir).expanduser())
                for p in papers:
                    if p.local_pdf_path:
                        try:
                            import pdfplumber
                            with pdfplumber.open(p.local_pdf_path) as pdf:
                                pages = [page.extract_text() or "" for page in pdf.pages]
                                p.full_text = "\n\n".join(pages)
                                p.content_tier = "full_text"
                        except Exception:
                            pass
            if papers:
                bib = Bibliography(session_id=session.session_id, papers=papers)
                session.bus.put_bibliography(bib)
                spec.paper_ids = [p.paper_id for p in papers]
            if not spec.query:
                n = len(papers) if papers else 0
                spec.query = (
                    f"You have {n} papers from the user's bibliography in {spec.domain}. "
                    f"Do NOT re-search for them. Identify gaps in coverage and find complementary work."
                )
            # Route through reference mode for the pipeline
            spec.mode = "reference"

        elif mode == "from_draft" and spec.draft_content:
            from eurekalab.analyzers.draft_analyzer import DraftAnalyzer, DraftAnalysis
            import tempfile
            # Write draft content to temp file for analyzer
            suffix = ".tex" if "\\documentclass" in spec.draft_content else ".md"
            with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
                f.write(spec.draft_content)
                draft_path = Path(f.name)
            try:
                analysis = DraftAnalyzer.analyze(draft_path)
            finally:
                draft_path.unlink(missing_ok=True)
            # Build context from analysis
            parts = []
            if spec.draft_instruction:
                parts.append(f"User instruction: {spec.draft_instruction}")
            if analysis.title:
                parts.append(f"Draft title: {analysis.title}")
            if analysis.abstract:
                parts.append(f"Draft abstract: {analysis.abstract[:500]}")
            if analysis.claims:
                parts.append("Draft claims:\n" + "\n".join(f"  - {c[:150]}" for c in analysis.claims))
            if analysis.gaps:
                parts.append("Gaps/TODOs:\n" + "\n".join(f"  - {g}" for g in analysis.gaps))
            spec.additional_context = "\n\n".join(parts)
            if not spec.domain:
                spec.domain = analysis.title or "research"
            if not spec.query:
                spec.query = (
                    f"The user has a draft paper titled '{analysis.title[:80]}'. "
                    f"Survey related work and identify what's missing."
                )
            spec.mode = "exploration"

        elif mode == "from_zotero" and spec.zotero_collection_id:
            if not settings.zotero_api_key or not settings.zotero_library_id:
                raise ValueError("Zotero not configured. Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID.")
            from eurekalab.integrations.zotero.adapter import ZoteroAdapter
            adapter = ZoteroAdapter(
                library_id=settings.zotero_library_id,
                api_key=settings.zotero_api_key,
                library_type=settings.zotero_library_type,
                local_data_dir=settings.zotero_local_data_dir or None,
            )
            papers = adapter.import_collection(spec.zotero_collection_id)
            if papers:
                bib = Bibliography(session_id=session.session_id, papers=papers)
                session.bus.put_bibliography(bib)
                spec.paper_ids = [p.paper_id for p in papers]
            if not spec.query:
                n = len(papers) if papers else 0
                spec.query = (
                    f"You have {n} papers from the user's Zotero library in {spec.domain}. "
                    f"Do NOT re-search for them. Identify gaps and find complementary work."
                )
            spec.mode = "reference"

    def _execute_run(self, run_id: str) -> None:
        run = self.get_run(run_id)
        if run is None:
            return

        run.status = "running"
        run.started_at = datetime.utcnow()
        run.updated_at = datetime.utcnow()

        try:
            # Pre-flight: verify credentials before spending time initialising agents
            config = _config_payload()
            _preflight_check(config)

            session = EurekaSession()
            run.eureka_session = session
            run.eureka_session_id = session.session_id

            # Pre-process alternative entry modes before pipeline runs
            self._preprocess_input_mode(session, run.input_spec)

            from eurekalab.ui import review_gate as _rg
            _rg.register_survey(session.session_id)
            _rg.register_direction(session.session_id)
            _rg.register_theory(session.session_id)

            with _temporary_auth_env(config):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(session.run(run.input_spec))
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)

            run.result = result

            # Save artifacts to results/<run_id>/ so files are always on disk.
            out_dir = save_artifacts(result, _ROOT_DIR / "results" / run.run_id)
            run.output_dir = str(out_dir)

            run.status = "completed"
            run.output_summary = {
                "latex_paper_length": len(result.latex_paper),
                "has_experiment_result": bool(result.experiment_result_json),
                "has_theory_state": bool(result.theory_state_json),
                "output_dir": str(out_dir),
            }
        except Exception as exc:
            from eurekalab.agents.theory.checkpoint import ProofPausedException
            if isinstance(exc, ProofPausedException):
                logger.info("Session %s paused at stage '%s'", run_id, exc.stage_name)
                run.status = "paused"
                run.paused_at = datetime.utcnow()
                run.paused_stage = exc.stage_name
                run.pause_requested_at = None
                run.error = ""
            else:
                logger.exception("UI session run failed")
                run.status = "failed"
                run.error = str(exc)
        finally:
            if run.eureka_session_id:
                from eurekalab.ui import review_gate as _rg
                _rg.unregister_all(run.eureka_session_id)
            run.completed_at = datetime.utcnow()
            run.updated_at = datetime.utcnow()
            self._persist_run(run)

    def snapshot_run(self, run: SessionRun) -> dict[str, Any]:
        bus = run.eureka_session.bus if run.eureka_session else None
        pipeline = bus.get_pipeline() if bus else None
        tasks: list[dict[str, Any]] = []
        if pipeline:
            for task in pipeline.tasks:
                tasks.append(
                    {
                        "task_id": task.task_id,
                        "name": task.name,
                        "agent_role": task.agent_role,
                        "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
                        "description": task.description,
                        "started_at": task.started_at.isoformat() if task.started_at else None,
                        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                        "error_message": task.error_message,
                        "outputs": _serialize_value(task.outputs),
                    }
                )

        brief = bus.get_research_brief() if bus else None
        bibliography = bus.get_bibliography() if bus else None
        theory_state = bus.get_theory_state() if bus else None
        experiment_result = bus.get_experiment_result() if bus else None
        resource_analysis = bus.get("resource_analysis") if bus else None

        return {
            "run_id": run.run_id,
            "name": run.name,
            "session_id": run.eureka_session_id,
            "status": run.status,
            "error": run.error,
            "created_at": run.created_at.isoformat(),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "paused_at": run.paused_at.isoformat() if run.paused_at else None,
            "pause_requested_at": run.pause_requested_at.isoformat() if run.pause_requested_at else None,
            "paused_stage": run.paused_stage,
            "input_spec": _serialize_value(run.input_spec),
            "pipeline": tasks,
            "artifacts": {
                "research_brief": _serialize_value(brief) if brief else None,
                "bibliography": _serialize_value(bibliography) if bibliography else None,
                "theory_state": _serialize_value(theory_state) if theory_state else None,
                "experiment_result": _serialize_value(experiment_result) if experiment_result else None,
                "resource_analysis": _serialize_value(resource_analysis) if resource_analysis else None,
            },
            "result": _serialize_value(run.result) if run.result else None,
            "output_summary": _serialize_value(run.output_summary),
            "output_dir": run.output_dir,
            "theory_feedback": run.theory_feedback,
        }


def _config_payload() -> dict[str, Any]:
    return {
        field_name: str(getattr(settings, field_name))
        if isinstance(getattr(settings, field_name), Path)
        else getattr(settings, field_name)
        for field_name in _CONFIG_FIELDS
    }


def _preflight_check(config: dict[str, Any]) -> None:
    """Raise a descriptive ValueError if credentials are not configured.

    Called before the session thread spins up the LLM client so that failures
    surface as a clear ``run.error`` message rather than a cryptic traceback
    deep inside the agent loop.
    """
    from eurekalab.llm.factory import _BACKEND_ALIASES

    backend = str(config.get("llm_backend", "anthropic"))
    auth_mode = str(config.get("anthropic_auth_mode", "api_key"))

    # Resolve shortcut backends (openrouter, local) → (openai_compat, default_base_url)
    _canonical, _default_base = _BACKEND_ALIASES.get(backend, (backend, ""))
    if _canonical != backend:
        backend = _canonical

    if backend == "openai_compat":
        base_url = str(config.get("openai_compat_base_url", "") or "") or _default_base
        if not base_url:
            raise ValueError(
                "OPENAI_COMPAT_BASE_URL is not set. "
                "Configure it in the UI settings or .env before starting a session."
            )
        api_key = str(config.get("openai_compat_api_key", "") or "")
        if not api_key:
            raise ValueError(
                "OPENAI_COMPAT_API_KEY is not set. "
                "Configure it in the UI settings or .env before starting a session."
            )
    else:
        # Anthropic backend
        if auth_mode == "oauth":
            return  # ccproxy handles auth; no key needed here

        import os as _os
        from pathlib import Path as _Path
        import json as _json

        api_key = (
            str(config.get("anthropic_api_key", "") or "")
            or _os.environ.get("ANTHROPIC_API_KEY", "")
        )
        if not api_key:
            # Last resort: check for Claude Code OAuth token
            creds = _Path.home() / ".claude" / ".credentials.json"
            if creds.exists():
                try:
                    token = _json.loads(creds.read_text()).get("claudeAiOauth", {}).get("accessToken", "")
                    if token:
                        return
                except Exception:
                    pass
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it in the UI Settings panel or your .env file, "
                "or use ANTHROPIC_AUTH_MODE=oauth with Claude Code."
            )


def _skills_payload() -> list[dict[str, Any]]:
    registry = SkillRegistry()
    skills = registry.load_all()
    skills.sort(key=lambda skill: (skill.meta.source != "seed", skill.meta.name))
    return [
        {
            "name": skill.meta.name,
            "description": skill.meta.description,
            "tags": skill.meta.tags,
            "agent_roles": skill.meta.agent_roles,
            "pipeline_stages": skill.meta.pipeline_stages,
            "source": skill.meta.source,
            "usage_count": skill.meta.usage_count,
            "success_rate": skill.meta.success_rate,
            "file_path": skill.file_path,
        }
        for skill in skills
    ]


def _install_skill(skillname: str) -> dict[str, Any]:
    """Install a skill from ClawHub or copy seed skills.  Runs synchronously."""
    from eurekalab.skills.install import install_from_hub, install_seed_skills

    dest = settings.skills_dir
    try:
        if skillname:
            ok = install_from_hub(skillname, dest)
            if ok:
                return {"ok": True, "message": f"Installed '{skillname}' from ClawHub → {dest}"}
            return {"ok": False, "error": f"Could not install '{skillname}'. Check that the `clawhub` CLI is installed and the skill slug is correct."}
        else:
            install_seed_skills(dest)
            return {"ok": True, "message": f"Seed skills installed → {dest}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _merged_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = _config_payload()
    if overrides:
        for key, value in overrides.items():
            config[key] = value
    return config


@contextmanager
def _temporary_auth_env(config: dict[str, Any]):
    """Temporarily align settings/env for auth checks, then restore them."""
    env_keys = ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"]
    old_env = {key: os.environ.get(key) for key in env_keys}
    old_settings = {
        "anthropic_auth_mode": settings.anthropic_auth_mode,
        "ccproxy_port": settings.ccproxy_port,
    }
    proc = None

    try:
        settings.anthropic_auth_mode = str(config.get("anthropic_auth_mode", settings.anthropic_auth_mode))
        settings.ccproxy_port = int(config.get("ccproxy_port", settings.ccproxy_port))

        api_key = str(config.get("anthropic_api_key", "") or "")
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

        if config.get("llm_backend") == "anthropic" and config.get("anthropic_auth_mode") == "oauth":
            proc = maybe_start_ccproxy()

        yield
    finally:
        stop_ccproxy(proc)
        settings.anthropic_auth_mode = old_settings["anthropic_auth_mode"]
        settings.ccproxy_port = old_settings["ccproxy_port"]
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def _test_llm_auth(config: dict[str, Any]) -> dict[str, Any]:
    """Initialize the configured client and perform a minimal text-generation check."""
    backend = str(config.get("llm_backend", "anthropic"))
    auth_mode = str(config.get("anthropic_auth_mode", "api_key"))
    model = str(
        config.get("eurekalab_fast_model")
        or config.get("openai_compat_model")
        or config.get("eurekalab_model")
        or ""
    )

    try:
        with _temporary_auth_env(config):
            client = create_client(
                backend=backend,
                anthropic_api_key=str(config.get("anthropic_api_key", "") or ""),
                openai_base_url=str(config.get("openai_compat_base_url", "") or ""),
                openai_api_key=str(config.get("openai_compat_api_key", "") or ""),
                openai_model=str(config.get("openai_compat_model", "") or ""),
            )
            response = await client.messages.create(
                model=model,
                max_tokens=16,
                system="Reply with exactly OK.",
                messages=[{"role": "user", "content": "Return OK."}],
            )
    except Exception as exc:
        return {
            "ok": False,
            "provider": backend,
            "auth_mode": auth_mode,
            "message": str(exc),
        }

    text_parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
    reply = " ".join(text_parts).strip()
    return {
        "ok": True,
        "provider": backend,
        "auth_mode": auth_mode,
        "message": "Connection verified with a live model response.",
        "reply_preview": reply[:120],
        "model": model,
    }


class UIRequestHandler(SimpleHTTPRequestHandler):
    """Serve frontend assets and JSON API routes."""

    def __init__(self, *args: Any, state: UIServerState, directory: str, **kwargs: Any) -> None:
        self.state = state
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/config":
            self._send_json({"config": _config_payload()})
            return
        if parsed.path == "/api/capabilities":
            self._send_json({"capabilities": _infer_capabilities()})
            return
        if parsed.path == "/api/skills":
            self._send_json({"skills": _skills_payload()})
            return
        if parsed.path == "/api/runs":
            runs = [self.state.snapshot_run(run) for run in self.state.list_runs()]
            self._send_json({"runs": runs})
            return
        # Serve artifact files: /api/runs/<run_id>/artifacts/<filename>
        _art_parts = parsed.path.strip("/").split("/")
        if (len(_art_parts) == 5 and _art_parts[0] == "api" and _art_parts[1] == "runs"
                and _art_parts[3] == "artifacts"):
            _art_run_id = _art_parts[2]
            _art_filename = _art_parts[4]
            _art_run = self.state.get_run(_art_run_id)
            if _art_run is None:
                self._send_json({"error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
                return
            if not _art_run.output_dir:
                self._send_json({"error": "No output directory"}, status=HTTPStatus.NOT_FOUND)
                return
            _art_path = Path(_art_run.output_dir) / _art_filename
            # Security: only allow known artifact filenames
            _allowed = {"paper.tex", "paper.pdf", "paper.md", "references.bib",
                        "theory_state.json", "experiment_result.json", "research_brief.json"}
            if _art_filename not in _allowed or not _art_path.is_file():
                self._send_json({"error": "File not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_file(_art_path)
            return

        # Version history: /api/runs/<run_id>/versions
        if parsed.path.endswith("/versions") and parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[3]
            try:
                from eurekalab.versioning.store import VersionStore
                session_dir = settings.runs_dir / run_id
                if not session_dir.exists():
                    self._send_json({"error": "Session not found"}, status=HTTPStatus.NOT_FOUND)
                    return
                store = VersionStore(run_id, session_dir)
                versions = [
                    {
                        "version_number": v.version_number,
                        "trigger": v.trigger,
                        "timestamp": v.timestamp.isoformat(),
                        "completed_stages": v.completed_stages,
                        "changes": v.changes,
                    }
                    for v in store.log()
                ]
                self._send_json({"versions": versions})
            except Exception as exc:
                self._send_json({"versions": [], "error": str(exc)})
            return

        # Content gap analysis: /api/runs/<run_id>/content-gap
        if parsed.path.endswith("/content-gap") and parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[3]
            bib_path = settings.runs_dir / run_id / "bibliography.json"
            if not bib_path.exists():
                self._send_json({"error": "No bibliography found"}, status=HTTPStatus.NOT_FOUND)
                return
            try:
                from eurekalab.types.artifacts import Bibliography
                from eurekalab.analyzers.content_gap import ContentGapAnalyzer
                bib = Bibliography.model_validate_json(bib_path.read_text())
                report = ContentGapAnalyzer.analyze(bib)
                degraded = report.abstract_only + report.metadata_only + report.missing
                self._send_json({
                    "full_text": len(report.full_text),
                    "abstract_only": len(report.abstract_only),
                    "metadata_only": len(report.metadata_only),
                    "missing": len(report.missing),
                    "has_gaps": report.has_gaps,
                    "degraded_papers": [
                        {"paper_id": p.paper_id, "title": p.title, "content_tier": p.content_tier, "arxiv_id": p.arxiv_id}
                        for p in degraded[:10]
                    ],
                })
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        # Ideation pool: /api/runs/<run_id>/ideation-pool
        if parsed.path.endswith("/ideation-pool") and parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[3]
            pool_path = settings.runs_dir / run_id / "ideation_pool.json"
            if not pool_path.exists():
                self._send_json({"directions": [], "injected_ideas": [], "emerged_insights": [], "has_new_input": False, "version": 0})
                return
            try:
                from eurekalab.orchestrator.ideation_pool import IdeationPool
                pool = IdeationPool.model_validate_json(pool_path.read_text())
                self._send_json({
                    "directions": [d.model_dump(mode="json") for d in pool.directions],
                    "selected_direction": pool.selected_direction.model_dump(mode="json") if pool.selected_direction else None,
                    "injected_ideas": [i.model_dump(mode="json") for i in pool.injected_ideas],
                    "emerged_insights": pool.emerged_insights,
                    "has_new_input": pool.has_new_input,
                    "version": pool.version,
                })
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[-1]
            run = self.state.get_run(run_id)
            if run is None:
                self._send_json({"error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json(self.state.snapshot_run(run))
            return

        if parsed.path == "/api/zotero/status":
            self._send_json({
                "configured": bool(settings.zotero_api_key and settings.zotero_library_id),
                "api_key_set": bool(settings.zotero_api_key),
                "library_id": settings.zotero_library_id,
            })
            return

        if parsed.path == "/api/zotero/collections":
            if not settings.zotero_api_key or not settings.zotero_library_id:
                self._send_json({"error": "Zotero not configured"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                from eurekalab.integrations.zotero.adapter import ZoteroAdapter
                adapter = ZoteroAdapter(
                    library_id=settings.zotero_library_id,
                    api_key=settings.zotero_api_key,
                    library_type=settings.zotero_library_type,
                )
                collections = adapter._zot.collections()
                result = [
                    {"key": c["key"], "name": c["data"].get("name", ""), "num_items": c["meta"].get("numItems", 0)}
                    for c in collections
                ]
                self._send_json({"collections": result})
            except ImportError:
                self._send_json({"error": "pyzotero not installed"}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if parsed.path == "/api/sessions":
            try:
                from eurekalab.storage.db import SessionDB
                db = SessionDB(settings.eurekalab_dir / "eurekalab.db")
                sessions = db.list_sessions()
                self._send_json({
                    "sessions": [
                        {
                            "session_id": s.session_id,
                            "domain": s.domain,
                            "query": s.query,
                            "mode": s.mode,
                            "status": s.status,
                            "created_at": s.created_at,
                            "updated_at": s.updated_at,
                            "completed_stages": s.completed_stages,
                        }
                        for s in sessions
                    ]
                })
            except Exception as exc:
                self._send_json({"sessions": [], "error": str(exc)})
            return

        if parsed.path == "/api/oauth/status":
            available = is_ccproxy_available()
            if not available:
                self._send_json({"installed": False, "authenticated": False, "message": f"ccproxy not found. Install with: {_oauth_install_hint()}"})
                return
            authed, msg = check_ccproxy_auth("claude_api")
            self._send_json({"installed": True, "authenticated": authed, "message": msg})
            return
        if parsed.path == "/api/health":
            self._send_json({"ok": True, "time": datetime.utcnow().isoformat()})
            return

        if parsed.path in ("/", ""):
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/runs":
            payload = self._read_json()
            try:
                input_spec = InputSpec.model_validate(payload)
            except Exception as exc:
                self._send_json(
                    {"error": f"Invalid request: {exc}"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            run = self.state.create_run(input_spec)
            self.state.start_run(run)
            self._send_json(self.state.snapshot_run(run), status=HTTPStatus.CREATED)
            return
        if parsed.path == "/api/auth/test":
            payload = self._read_json()
            result = asyncio.run(_test_llm_auth(_merged_config(payload)))
            self._send_json(result)
            return
        if parsed.path == "/api/config":
            payload = self._read_json()
            config_updates: dict[str, str] = {}
            for field_name, env_name in _CONFIG_FIELDS.items():
                if field_name not in payload:
                    continue
                value = payload[field_name]
                if isinstance(value, bool):
                    rendered = "true" if value else "false"
                else:
                    rendered = str(value)
                config_updates[env_name] = rendered
                current = getattr(settings, field_name)
                if isinstance(current, Path):
                    setattr(settings, field_name, Path(rendered))
                elif isinstance(current, bool):
                    setattr(settings, field_name, rendered.lower() == "true")
                elif isinstance(current, int):
                    setattr(settings, field_name, int(rendered))
                elif isinstance(current, float):
                    setattr(settings, field_name, float(rendered))
                else:
                    setattr(settings, field_name, rendered)

            _write_env_updates(_ENV_PATH, config_updates)
            self._send_json({"config": _config_payload(), "saved": True})
            return

        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/pause"):
            run_id = parsed.path.removeprefix("/api/runs/").removesuffix("/pause")
            result = self.state.pause_run(run_id)
            if "error" in result:
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
            else:
                self._send_json(result)
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/resume"):
            run_id = parsed.path.removeprefix("/api/runs/").removesuffix("/resume")
            payload = self._read_json()
            feedback = str(payload.get("feedback", "")).strip()
            result = self.state.resume_run(run_id, feedback=feedback)
            if "error" in result:
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
            else:
                self._send_json(result)
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/rename"):
            run_id = parsed.path.removeprefix("/api/runs/").removesuffix("/rename")
            payload = self._read_json()
            result = self.state.rename_run(run_id, str(payload.get("name", "")))
            if "error" in result:
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
            else:
                self._send_json(result)
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/restart"):
            run_id = parsed.path.removeprefix("/api/runs/").removesuffix("/restart")
            result = self.state.restart_run(run_id)
            if result.get("error"):  # snapshot always has "error" key; check truthiness
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
            else:
                self._send_json(result, status=HTTPStatus.CREATED)
            return

        # Re-run in place: /api/runs/<run_id>/rerun
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/rerun"):
            run_id = parsed.path.removeprefix("/api/runs/").removesuffix("/rerun")
            payload = self._read_json()
            updated_skills = payload.get("selected_skills") if payload else None
            result = self.state.rerun_run(run_id, updated_skills=updated_skills)
            if result.get("error"):
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
            else:
                self._send_json(result)
            return

        # Compile PDF: /api/runs/<run_id>/compile-pdf
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/compile-pdf"):
            run_id = parsed.path.removeprefix("/api/runs/").removesuffix("/compile-pdf")
            run = self.state.get_run(run_id)
            if run is None:
                self._send_json({"error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
                return
            if not run.output_dir:
                self._send_json({"error": "No output directory"}, status=HTTPStatus.BAD_REQUEST)
                return
            tex_path = Path(run.output_dir) / "paper.tex"
            if not tex_path.is_file():
                self._send_json({"error": "No paper.tex found"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                _compile_pdf(tex_path, settings.latex_bin)
                pdf_path = Path(run.output_dir) / "paper.pdf"
                if pdf_path.is_file():
                    self._send_json({"ok": True, "pdf_path": str(pdf_path)})
                else:
                    self._send_json({"error": "pdflatex ran but produced no PDF — check paper.log"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            except FileNotFoundError:
                self._send_json({"error": "pdflatex binary not found. Install TeX (e.g. brew install --cask basictex)"}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": f"PDF compilation failed: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if parsed.path == "/api/oauth/install":
            try:
                repo_root = str(Path(__file__).resolve().parents[2])
                # Prefer uv pip (uv-managed venvs don't bundle pip)
                uv_exe = shutil.which("uv")
                if uv_exe:
                    cmd = [uv_exe, "pip", "install", "-e", ".[oauth]"]
                else:
                    cmd = [_sys.executable, "-m", "pip", "install", "-e", ".[oauth]"]
                result = _subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=120,
                    cwd=repo_root,
                )
                if result.returncode == 0:
                    self._send_json({"ok": True, "message": "OAuth dependencies installed successfully."})
                else:
                    self._send_json({"ok": False, "message": result.stderr.strip() or result.stdout.strip()})
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)})
            return

        if parsed.path == "/api/oauth/login":
            from eurekalab.ccproxy_manager import _ccproxy_exe
            exe = _ccproxy_exe()
            if not exe:
                self._send_json({"ok": False, "message": f"ccproxy not found. Install first with: {_oauth_install_hint()}"})
                return
            try:
                # Launch login in background — it opens a browser and waits
                # for the user to complete auth, so we can't block the HTTP response.
                _subprocess.Popen(
                    [exe, "auth", "login", "claude_api"],
                    stdout=_subprocess.DEVNULL,
                    stderr=_subprocess.DEVNULL,
                )
                self._send_json({"ok": True, "message": "OAuth login opened in your browser. Complete authorization, then click 'Save & test'."})
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)})
            return

        if parsed.path == "/api/skills/install":
            payload = self._read_json()
            skillname = str(payload.get("skillname", "")).strip()
            result = _install_skill(skillname)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            self._send_json(result, status=status)
            return

        # Version diff: /api/runs/<run_id>/versions/diff
        if "/versions/diff" in parsed.path and parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[3]
            payload = self._read_json()
            v1 = payload.get("v1")
            v2 = payload.get("v2")
            if v1 is None or v2 is None:
                self._send_json({"error": "v1 and v2 are required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                from eurekalab.versioning.store import VersionStore
                from eurekalab.versioning.diff import diff_versions
                session_dir = settings.runs_dir / run_id
                store = VersionStore(run_id, session_dir)
                changes = diff_versions(store, int(v1), int(v2))
                self._send_json({"changes": changes})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.NOT_FOUND)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        # Version checkout: /api/runs/<run_id>/versions/checkout
        if "/versions/checkout" in parsed.path and parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[3]
            payload = self._read_json()
            version_number = payload.get("version_number")
            if version_number is None:
                self._send_json({"error": "version_number is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                from eurekalab.versioning.store import VersionStore
                session_dir = settings.runs_dir / run_id
                store = VersionStore(run_id, session_dir)
                target = store.get(int(version_number))
                if target is None:
                    self._send_json({"error": f"Version {version_number} not found"}, status=HTTPStatus.NOT_FOUND)
                    return
                bus = store.checkout(int(version_number))
                store.commit(
                    bus,
                    trigger=f"checkout:v{int(version_number):03d}",
                    completed_stages=target.completed_stages,
                    changes=[f"Restored state from v{int(version_number):03d}"],
                )
                bus._session_dir = session_dir
                bus.persist(session_dir)
                head = store.head
                self._send_json({
                    "ok": True,
                    "new_head": head.version_number if head else 0,
                    "completed_stages": target.completed_stages,
                })
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        # Ideation pool injection: /api/runs/<run_id>/ideation-pool/inject
        if "/ideation-pool/inject" in parsed.path and parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[3]
            payload = self._read_json()
            inject_type = payload.get("type", "idea")  # "idea", "paper", "draft"
            text = payload.get("text", "").strip()
            source = payload.get("source", "ui")
            if not text:
                self._send_json({"error": "text is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                from eurekalab.knowledge_bus.bus import KnowledgeBus
                from eurekalab.orchestrator.ideation_pool import IdeationPool
                from eurekalab.types.artifacts import Paper, Bibliography
                session_dir = settings.runs_dir / run_id
                bus = KnowledgeBus.load(run_id, session_dir)
                pool = bus.get_ideation_pool() or IdeationPool()

                if inject_type == "paper":
                    # Add to bibliography
                    bib = bus.get_bibliography() or Bibliography(session_id=run_id)
                    paper = Paper(paper_id=text, title=f"Paper {text}", authors=[], arxiv_id=text if text[0].isdigit() else None, source="user_provided", content_tier="metadata")
                    bib.papers.append(paper)
                    bus.put_bibliography(bib)
                    pool.inject_idea(f"New paper added: {text}", source=f"inject:paper:{text}")
                elif inject_type == "draft":
                    pool.inject_idea(f"Draft content injected: {text[:100]}", source="inject:draft")
                    brief = bus.get_research_brief()
                    if brief:
                        brief.draft_summary = text[:500]
                        bus.put_research_brief(brief)
                else:
                    pool.inject_idea(text, source=source)

                bus.put_ideation_pool(pool)
                bus._session_dir = session_dir
                bus.persist_incremental()
                version_num = bus.version_store.head.version_number if bus.version_store and bus.version_store.head else 0
                self._send_json({"ok": True, "pool_version": pool.version, "session_version": version_num})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        # Push to Zotero: /api/runs/<run_id>/push-to-zotero
        if "/push-to-zotero" in parsed.path and parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.split("/")[3]
            payload = self._read_json()
            collection_name = payload.get("collection_name", "EurekaLab Results")
            if not settings.zotero_api_key or not settings.zotero_library_id:
                self._send_json({"error": "Zotero not configured"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                from eurekalab.integrations.zotero.adapter import ZoteroAdapter
                from eurekalab.types.artifacts import Bibliography
                adapter = ZoteroAdapter(
                    library_id=settings.zotero_library_id,
                    api_key=settings.zotero_api_key,
                    library_type=settings.zotero_library_type,
                )
                col_key = adapter.create_collection(collection_name)
                bib_path = settings.runs_dir / run_id / "bibliography.json"
                papers_pushed = 0
                if bib_path.exists():
                    bib = Bibliography.model_validate_json(bib_path.read_text())
                    unfiled = [p for p in bib.papers if not p.zotero_item_key]
                    if unfiled:
                        keys = adapter.push_papers(unfiled, col_key)
                        papers_pushed = len(keys)
                self._send_json({"ok": True, "papers_pushed": papers_pushed, "collection_key": col_key})
            except ImportError:
                self._send_json({"error": "pyzotero not installed"}, status=HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if parsed.path == "/api/sessions/clean":
            payload = self._read_json()
            older_than_days = int(payload.get("older_than_days", 30))
            status_filter = payload.get("status_filter")
            try:
                from eurekalab.storage.db import SessionDB
                import shutil as _shutil
                db = SessionDB(settings.eurekalab_dir / "eurekalab.db")
                candidates = db.list_sessions_older_than(older_than_days)
                if status_filter and status_filter != "all":
                    candidates = [s for s in candidates if s.status == status_filter]
                removed = 0
                freed_bytes = 0
                for s in candidates:
                    run_dir = settings.runs_dir / s.session_id
                    if run_dir.exists():
                        freed_bytes += sum(f.stat().st_size for f in run_dir.rglob("*") if f.is_file())
                        _shutil.rmtree(run_dir)
                    db.delete_session(s.session_id)
                    removed += 1
                self._send_json({"removed": removed, "freed_kb": round(freed_bytes / 1024, 1)})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        # Gate submission endpoints: /api/runs/<run_id>/gate/{survey|direction|theory}
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "runs" and parts[3] == "gate":
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if len(parts) == 5 and parts[0] == "api" and parts[1] == "runs" and parts[3] == "gate":
            run_id = parts[2]
            gate_type = parts[4]
            run = self.state.get_run(run_id)
            if run is None:
                self._send_json({"error": "Run not found"}, status=HTTPStatus.NOT_FOUND)
                return
            session_id = run.eureka_session_id
            if not session_id:
                self._send_json({"error": "No active session"}, status=HTTPStatus.BAD_REQUEST)
                return
            from eurekalab.ui import review_gate as _rg
            payload = self._read_json()
            if gate_type == "survey":
                raw_ids = payload.get("paper_ids", [])
                paper_ids = [str(x).strip() for x in raw_ids if str(x).strip()]
                ok = _rg.submit_survey(session_id, paper_ids)
            elif gate_type == "direction":
                direction = str(payload.get("direction", "")).strip()
                ok = _rg.submit_direction(session_id, direction)
            elif gate_type == "theory":
                from eurekalab.ui.review_gate import TheoryDecision
                approved = bool(payload.get("approved", True))
                lemma_id = str(payload.get("lemma_id", "")).strip()
                reason = str(payload.get("reason", "")).strip()
                ok = _rg.submit_theory(session_id, TheoryDecision(approved=approved, lemma_id=lemma_id, reason=reason))
            else:
                self._send_json({"error": f"Unknown gate type: {gate_type}"}, status=HTTPStatus.BAD_REQUEST)
                return
            if ok:
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Gate not active for this session"}, status=HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/skills/"):
            skill_name = parsed.path.removeprefix("/api/skills/").strip("/")
            skill_file = settings.skills_dir / f"{skill_name}.md"
            if not skill_file.exists():
                self._send_json({"error": f"Skill '{skill_name}' not found in user skills dir."}, status=HTTPStatus.NOT_FOUND)
                return
            skill_file.unlink()
            self._send_json({"ok": True, "message": f"Deleted '{skill_name}'"})
            return
        if parsed.path.startswith("/api/runs/"):
            run_id = parsed.path.removeprefix("/api/runs/").strip("/")
            result = self.state.delete_run(run_id)
            if "error" in result:
                self._send_json(result, status=HTTPStatus.BAD_REQUEST)
            else:
                self._send_json(result)
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        # Silence noisy polling GETs to /api/runs and /api/runs/<id>
        msg = format % args
        if '"GET /api/runs' in msg and '" 200 -' in msg:
            logger.debug("UI %s", msg)
            return
        logger.info("UI %s", msg)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, file_path: Path) -> None:
        """Serve a file for download with appropriate Content-Type."""
        import mimetypes
        content_type, _ = mimetypes.guess_type(str(file_path))
        if content_type is None:
            content_type = "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
        self.end_headers()
        self.wfile.write(data)


def bind_ui_server(host: str = "127.0.0.1", port: int = 8080) -> "ThreadingHTTPServer":
    """Create and bind the UI server, trying alternative ports if needed.

    Tries up to 10 ports (port, port+1, ...) to work around Windows
    WinError 10013 (port blocked by Hyper-V / WSL exclusion ranges or firewall).

    Returns the bound server; caller is responsible for calling serve_forever()
    and server_close().
    """
    frontend_dir = _FRONTEND_DIR if _FRONTEND_DIR.exists() else _DEV_FRONTEND_DIR
    if not frontend_dir.exists():
        raise FileNotFoundError(f"Frontend directory not found: {frontend_dir}")

    state = UIServerState()
    handler = partial(UIRequestHandler, state=state, directory=str(frontend_dir))

    last_error: Exception | None = None
    for candidate in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((host, candidate), handler)
            return server
        except OSError as exc:
            last_error = exc
            logger.debug("Could not bind port %d: %s", candidate, exc)

    raise OSError(
        f"Could not bind to any port in range {port}–{port + 9}. "
        f"Last error: {last_error}\n"
        f"On Windows, check excluded ports with: "
        f"netsh int ipv4 show excludedportrange protocol=tcp"
    ) from last_error


def serve_ui(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Bind and serve the EurekaLab UI, blocking until KeyboardInterrupt."""
    os.environ["EUREKALAB_UI_MODE"] = "1"
    server = bind_ui_server(host, port)
    actual_port = server.server_address[1]
    logger.info("Serving EurekaLab UI at http://%s:%d", host, actual_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down UI server")
    finally:
        server.server_close()
