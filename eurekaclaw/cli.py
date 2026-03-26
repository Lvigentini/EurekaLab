"""EurekaClaw CLI entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from eurekaclaw.config import settings

from eurekaclaw.agents.theory.checkpoint import ProofCheckpoint
from eurekaclaw.types.artifacts import TheoryState

console = Console()


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def main(verbose: bool) -> None:
    """EurekaClaw — Multi-agent system for theoretical research."""
    setup_logging(verbose)


@main.command()
@click.argument("conjecture")
@click.option("--domain", "-d", default="", help="Research domain (auto-inferred if omitted)")
@click.option("--mode", default="skills_only", type=click.Choice(["skills_only", "rl", "madmax"]))
@click.option("--skills", default=None, help="The skills to use for this session (default: all skills available in the skills bank)", multiple=True)
@click.option("--gate", default="none", type=click.Choice(["human", "auto", "none"]))
@click.option("--output", "-o", default="./results", help="Output directory for artifacts (default: ./results)")
def prove(conjecture: str, domain: str, mode: str, skills: list[str], gate: str, output: str) -> None:
    """Level 1: Prove a specific conjecture.

    Example: eurekaclaw prove "The sample complexity of transformers is O(L*d*log(d)/eps^2)"

    Press Ctrl+C at any time to pause.  The pipeline will stop before the
    next lemma and save a checkpoint.  Resume with:
        eurekaclaw resume <session-id>
    """
    _run_session(
        mode="detailed",
        query=conjecture,
        conjecture=conjecture,
        domain=domain,
        learn_mode=mode,
        gate=gate,
        output_dir=output,
        skills=skills,
    )


@main.command()
@click.argument("domain")
@click.option("--query", "-q", default="", help="Specific research question")
@click.option("--mode", default="skills_only", type=click.Choice(["skills_only", "rl", "madmax"]))
@click.option("--gate", default="none", type=click.Choice(["human", "auto", "none"]))
@click.option("--output", "-o", default="./results", help="Output directory for artifacts (default: ./results)")
def explore(domain: str, query: str, mode: str, gate: str, output: str) -> None:
    """Level 3: Open exploration of a research domain.

    Example: eurekaclaw explore "sample complexity of transformers"
    """
    _run_session(mode="exploration", query=query or domain, domain=domain, learn_mode=mode, gate=gate, output_dir=output)


@main.command()
@click.argument("paper_ids", nargs=-1)
@click.option("--query", "-q", default="", help="Specific research question")
@click.option("--domain", "-d", required=True, help="Research domain")
@click.option("--mode", default="skills_only")
@click.option("--skills", default=None, help="The skills to use for this session (default: all skills available in the skills bank)", multiple=True)
@click.option("--gate", default="none", type=click.Choice(["human", "auto", "none"]))
@click.option("--output", "-o", default="./results", help="Output directory for artifacts (default: ./results)")
def from_papers(paper_ids: tuple[str, ...], query: str, domain: str, mode: str, skills: list[str], gate: str, output: str) -> None:
    """Level 2: Generate hypotheses from reference papers.

    Example: eurekaclaw from-papers 2301.12345 2302.67890 --domain "ML theory"
    """
    if not query:
        ids_hint = (
            f" (papers: {', '.join(list(paper_ids)[:3])}{'…' if len(paper_ids) > 3 else ''})"
            if paper_ids else ""
        )
        query = (
            f"Analyze the provided reference papers{ids_hint} in {domain}. "
            f"Identify open problems, under-explored directions, and research gaps "
            f"relative to the current frontier of {domain}. "
            f"Propose concrete novel hypotheses that extend or challenge the findings "
            f"in these papers."
        )
    _run_session(
        mode="reference",
        query=query,
        domain=domain,
        paper_ids=list(paper_ids),
        learn_mode=mode,
        gate=gate,
        output_dir=output,
        skills=skills,
    )


@main.command("from-bib")
@click.argument("bib_file", type=click.Path(exists=True))
@click.option("--pdfs", "-p", default=None, type=click.Path(exists=True),
              help="Directory containing local PDF files to match")
@click.option("--domain", "-d", required=True, help="Research domain")
@click.option("--query", "-q", default="", help="Specific research question")
@click.option("--mode", default="skills_only", type=click.Choice(["skills_only", "rl", "madmax"]))
@click.option("--gate", default="none", type=click.Choice(["human", "auto", "none"]))
@click.option("--output", "-o", default="./results", help="Output directory")
def from_bib(bib_file: str, pdfs: str | None, domain: str, query: str, mode: str, gate: str, output: str) -> None:
    """Start research from a .bib file and optional local PDFs.

    Example: eurekaclaw from-bib refs.bib --pdfs ./papers/ --domain "ML theory"
    """
    from pathlib import Path
    from eurekaclaw.analyzers.bib_loader import BibLoader

    # Parse .bib file
    papers = BibLoader.load_bib(Path(bib_file))
    if not papers:
        console.print("[red]No papers found in .bib file.[/red]")
        sys.exit(1)

    console.print(f"[green]Loaded {len(papers)} papers from {bib_file}[/green]")

    # Match local PDFs if directory provided
    if pdfs:
        pdf_dir = Path(pdfs)
        papers = BibLoader.match_pdfs(papers, pdf_dir)
        matched = sum(1 for p in papers if p.local_pdf_path)
        console.print(f"[green]Matched {matched}/{len(papers)} papers to local PDFs[/green]")

        # Extract text from matched PDFs
        for paper in papers:
            if paper.local_pdf_path:
                try:
                    import pdfplumber
                    with pdfplumber.open(paper.local_pdf_path) as pdf:
                        pages = [page.extract_text() or "" for page in pdf.pages]
                        paper.full_text = "\n\n".join(pages)
                        paper.content_tier = "full_text"
                except Exception as e:
                    console.print(f"[yellow]PDF extraction failed for '{paper.title[:50]}': {e}[/yellow]")

    if not query:
        n = len(papers)
        query = (
            f"You have been provided with {n} papers from the user's bibliography in {domain}. "
            f"These papers are already loaded — do NOT search for them again. "
            f"Instead, identify gaps in coverage: what related work is missing? "
            f"What recent advances are not represented? What foundational work should be added? "
            f"Search for papers that complement this existing collection."
        )

    paper_ids = [p.paper_id for p in papers if p.paper_id]

    _run_session(
        mode="reference",
        query=query,
        domain=domain,
        paper_ids=paper_ids,
        learn_mode=mode,
        gate=gate,
        output_dir=output,
        _preloaded_papers=papers,
    )


@main.command("from-zotero")
@click.argument("collection_id")
@click.option("--domain", "-d", required=True, help="Research domain")
@click.option("--query", "-q", default="", help="Specific research question")
@click.option("--mode", default="skills_only", type=click.Choice(["skills_only", "rl", "madmax"]))
@click.option("--gate", default="none", type=click.Choice(["human", "auto", "none"]))
@click.option("--output", "-o", default="./results", help="Output directory")
def from_zotero(collection_id: str, domain: str, query: str, mode: str, gate: str, output: str) -> None:
    """Start research from a Zotero collection.

    Requires ZOTERO_API_KEY and ZOTERO_LIBRARY_ID environment variables.

    Example: eurekaclaw from-zotero ABC123 --domain "ML theory"
    """
    if not settings.zotero_api_key or not settings.zotero_library_id:
        console.print(
            "[red]Zotero credentials not configured.[/red]\n"
            "Set ZOTERO_API_KEY and ZOTERO_LIBRARY_ID environment variables.\n"
            "Get your API key at: https://www.zotero.org/settings/keys"
        )
        sys.exit(1)

    try:
        from eurekaclaw.integrations.zotero.adapter import ZoteroAdapter
    except ImportError:
        console.print(
            "[red]pyzotero not installed.[/red]\n"
            "Install with: pip install 'eurekaclaw[zotero]'"
        )
        sys.exit(1)

    adapter = ZoteroAdapter(
        library_id=settings.zotero_library_id,
        api_key=settings.zotero_api_key,
        library_type=settings.zotero_library_type,
        local_data_dir=settings.zotero_local_data_dir or None,
    )

    console.print(f"[blue]Importing from Zotero collection {collection_id}...[/blue]")
    papers = adapter.import_collection(collection_id)
    if not papers:
        console.print("[red]No papers found in Zotero collection.[/red]")
        sys.exit(1)

    console.print(f"[green]Imported {len(papers)} papers from Zotero[/green]")

    # Extract text from local PDFs if available
    for paper in papers:
        if paper.local_pdf_path:
            try:
                import pdfplumber
                with pdfplumber.open(paper.local_pdf_path) as pdf:
                    pages = [page.extract_text() or "" for page in pdf.pages]
                    paper.full_text = "\n\n".join(pages)
                    paper.content_tier = "full_text"
            except Exception as e:
                console.print(f"[yellow]PDF extraction failed for '{paper.title[:50]}': {e}[/yellow]")

    if not query:
        n = len(papers)
        query = (
            f"You have been provided with {n} papers from the user's Zotero library in {domain}. "
            f"These papers are already loaded — do NOT search for them again. "
            f"Instead, identify gaps: what related work is missing? "
            f"What recent advances or foundational work should be added?"
        )

    paper_ids = [p.paper_id for p in papers if p.paper_id]

    _run_session(
        mode="reference",
        query=query,
        domain=domain,
        paper_ids=paper_ids,
        learn_mode=mode,
        gate=gate,
        output_dir=output,
        _preloaded_papers=papers,
    )


@main.command("from-draft")
@click.argument("draft_file", type=click.Path(exists=True))
@click.argument("instruction", default="")
@click.option("--domain", "-d", default="", help="Research domain (auto-inferred if omitted)")
@click.option("--query", "-q", default="", help="Specific research question")
@click.option("--mode", default="skills_only", type=click.Choice(["skills_only", "rl", "madmax"]))
@click.option("--gate", default="none", type=click.Choice(["human", "auto", "none"]))
@click.option("--output", "-o", default="./results", help="Output directory")
def from_draft(draft_file: str, instruction: str, domain: str, query: str, mode: str, gate: str, output: str) -> None:
    """Start research from a draft paper with optional instruction.

    Examples:
        eurekaclaw from-draft paper.tex "This is my WIP, strengthen the theory"
        eurekaclaw from-draft paper.tex --domain "ML theory"
    """
    from pathlib import Path
    from eurekaclaw.analyzers.draft_analyzer import DraftAnalyzer

    draft_path = Path(draft_file)
    console.print(f"[blue]Analyzing draft: {draft_path.name}...[/blue]")
    analysis = DraftAnalyzer.analyze(draft_path)

    if not analysis.full_text:
        console.print("[red]Could not extract text from draft file.[/red]")
        sys.exit(1)

    console.print(f"[green]Draft analyzed:[/green]")
    if analysis.title:
        console.print(f"  Title: {analysis.title[:80]}")
    console.print(f"  Sections: {len(analysis.sections)}")
    console.print(f"  Claims: {len(analysis.claims)}")
    console.print(f"  Citations: {len(analysis.citation_keys)}")
    if analysis.gaps:
        console.print(f"  [yellow]Gaps/TODOs: {len(analysis.gaps)}[/yellow]")

    # Infer domain from title/abstract if not provided
    if not domain:
        domain = analysis.title or "research"

    # Build context from draft analysis
    draft_context_parts = []
    if instruction:
        draft_context_parts.append(f"User instruction: {instruction}")
    draft_context_parts.append(f"Draft title: {analysis.title}")
    if analysis.abstract:
        draft_context_parts.append(f"Draft abstract: {analysis.abstract[:500]}")
    if analysis.claims:
        draft_context_parts.append("Draft claims:\n" + "\n".join(f"  - {c[:150]}" for c in analysis.claims))
    if analysis.gaps:
        draft_context_parts.append("Identified gaps/TODOs:\n" + "\n".join(f"  - {g}" for g in analysis.gaps))
    draft_context = "\n\n".join(draft_context_parts)

    if not query:
        query = (
            f"The user has a draft paper titled '{analysis.title[:80]}'. "
            f"{'User says: ' + instruction + '. ' if instruction else ''}"
            f"Survey related work that complements this draft. "
            f"The draft cites {len(analysis.citation_keys)} papers — find what's missing."
        )

    _run_session(
        mode="exploration",
        query=query,
        domain=domain,
        learn_mode=mode,
        gate=gate,
        output_dir=output,
        _additional_context=draft_context,
        _draft_path=str(draft_path),
    )


@main.command()
@click.argument("session_id")
def pause(session_id: str) -> None:
    """Request pause for a running proof session.

    Example: eurekaclaw pause abc12345-...
    """
    from eurekaclaw.agents.theory.checkpoint import ProofCheckpoint
    cp = ProofCheckpoint(session_id)
    cp.request_pause()
    console.print(
        f"\n[yellow]Pause requested for session [cyan]{session_id[:8]}[/cyan].[/yellow]"
        "\nThe proof will stop at the next stage boundary."
        f"\nResume with:  [bold]eurekaclaw resume {session_id}[/bold]\n"
    )


@main.command()
@click.argument("session_id")
def resume(session_id: str) -> None:
    """Resume a paused proof session.

    Example: eurekaclaw resume abc12345-...
    """
    from eurekaclaw.agents.theory.checkpoint import ProofCheckpoint, ProofPausedException
    from eurekaclaw.agents.theory.inner_loop_yaml import TheoryInnerLoopYaml
    from eurekaclaw.knowledge_bus.bus import KnowledgeBus
    from eurekaclaw.memory.manager import MemoryManager
    from eurekaclaw.skills.injector import SkillInjector
    from eurekaclaw.types.artifacts import ResearchBrief

    cp = ProofCheckpoint(session_id)
    if not cp.exists():
        console.print(f"[red]No checkpoint found for session '{session_id}'.[/red]")
        console.print(
            f"[dim]Expected location: {cp.checkpoint_path}[/dim]"
        )

        # Fallback: check for pipeline-level checkpoint from incremental persistence
        from eurekaclaw.orchestrator.session_checkpoint import SessionCheckpoint
        scp = SessionCheckpoint(session_id)
        last_stage, completed = scp.detect_progress()

        if last_stage:
            next_stage = scp.next_stage_after(last_stage)
            console.print(f"\n[green]Found pipeline progress: completed stages = {completed}[/green]")
            if next_stage:
                console.print(f"[blue]To resume, re-run with the same parameters. The completed stages' results are preserved in:[/blue]")
                console.print(f"  {settings.runs_dir / session_id}/")
            else:
                console.print("[green]Session was fully complete. Results at:[/green]")
                console.print(f"  {settings.runs_dir / session_id}/")
            return

        sys.exit(1)

    state, meta = cp.load()
    domain = meta.get("domain", "")
    brief_raw = json.loads(meta.get("research_brief_json", "{}") or "{}")
    next_stage = meta.get("next_stage", "?")

    console.print(
        f"\n[bold green]Resuming session[/bold green] [cyan]{session_id[:8]}[/cyan]"
        f"  stage=[yellow]{next_stage}[/yellow]"
        f"  proven={len(state.proven_lemmas)}"
        f"  open={len(state.open_goals)}\n"
    )

    bus = KnowledgeBus(session_id)
    bus.put_theory_state(state)
    if brief_raw:
        try:
            bus.put_research_brief(ResearchBrief.model_validate(brief_raw))
        except Exception:
            pass  # Non-fatal: brief is used only for KG tagging

    from eurekaclaw.skills.registry import SkillRegistry
    memory = MemoryManager(session_id=session_id)
    skill_injector = SkillInjector(SkillRegistry())
    inner_loop = TheoryInnerLoopYaml(
        bus=bus, skill_injector=skill_injector, memory=memory
    )

    try:
        final_state = _run_with_pause_support(inner_loop.run(session_id, domain=domain), cp)
        _print_proof_result(final_state)
    except ProofPausedException as exc:
        console.print(
            f"\n[yellow]Paused again before stage '{exc.stage_name}'.[/yellow]"
            f"\nResume with:  [bold]eurekaclaw resume {session_id}[/bold]\n"
        )


@main.command()
@click.argument("session_id")
def history(session_id: str) -> None:
    """Show version history for a session.

    Example: eurekaclaw history abc12345-...
    """
    from datetime import datetime, timezone
    from rich.table import Table
    from eurekaclaw.versioning.store import VersionStore

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    store = VersionStore(session_id, session_dir)
    versions = store.log()
    if not versions:
        console.print("[yellow]No versions found for this session.[/yellow]")
        return

    table = Table(title=f"Version History — {session_id[:8]}")
    table.add_column("Version", style="cyan", width=8)
    table.add_column("Time", style="dim", width=20)
    table.add_column("Trigger", style="green")
    table.add_column("Stages", style="yellow")

    now = datetime.now(timezone.utc)
    for v in reversed(versions):
        age = now - v.timestamp
        if age.total_seconds() < 3600:
            time_str = f"{int(age.total_seconds() / 60)}m ago"
        elif age.total_seconds() < 86400:
            time_str = f"{int(age.total_seconds() / 3600)}h ago"
        else:
            time_str = v.timestamp.strftime("%Y-%m-%d %H:%M")

        head_marker = " *" if v == store.head else ""
        table.add_row(
            f"v{v.version_number:03d}{head_marker}",
            time_str,
            v.trigger,
            ", ".join(v.completed_stages[-3:]) if v.completed_stages else "—",
        )

    console.print(table)


@main.command("diff")
@click.argument("session_id")
@click.argument("v1", type=int)
@click.argument("v2", type=int)
def version_diff(session_id: str, v1: int, v2: int) -> None:
    """Show changes between two versions.

    Example: eurekaclaw diff abc12345-... 1 3
    """
    from eurekaclaw.versioning.store import VersionStore
    from eurekaclaw.versioning.diff import diff_versions

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    store = VersionStore(session_id, session_dir)
    try:
        changes = diff_versions(store, v1, v2)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    if not changes:
        console.print(f"[dim]No changes between v{v1:03d} and v{v2:03d}[/dim]")
        return

    console.print(f"\n[bold]Changes v{v1:03d} → v{v2:03d}:[/bold]")
    for change in changes:
        if "+paper" in change or "+proven" in change or "+direction" in change or "+injected" in change:
            console.print(f"  [green]{change}[/green]")
        elif "removed" in change.lower() or change.startswith("Removed"):
            console.print(f"  [red]{change}[/red]")
        else:
            console.print(f"  [yellow]{change}[/yellow]")


@main.command()
@click.argument("session_id")
@click.argument("version_number", type=int)
def checkout(session_id: str, version_number: int) -> None:
    """Restore session state to a specific version.

    Example: eurekaclaw checkout abc12345-... 3
    """
    from eurekaclaw.versioning.store import VersionStore

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    store = VersionStore(session_id, session_dir)
    target = store.get(version_number)
    if target is None:
        console.print(f"[red]Version {version_number} not found.[/red]")
        sys.exit(1)

    from rich.prompt import Confirm
    console.print(f"\n[bold]Checkout v{version_number:03d}[/bold]: {target.trigger}")
    console.print(f"  Stages: {', '.join(target.completed_stages) or '(none)'}")
    if not Confirm.ask("Restore this version? (current HEAD will be preserved as a version)", default=True):
        return

    bus = store.checkout(version_number)
    store.commit(
        bus,
        trigger=f"checkout:v{version_number:03d}",
        completed_stages=target.completed_stages,
        changes=[f"Restored state from v{version_number:03d}"],
    )
    bus._session_dir = session_dir
    bus.persist(session_dir)

    head = store.head
    console.print(f"\n[green]Restored to v{version_number:03d}. New HEAD is v{head.version_number:03d}.[/green]")
    console.print(f"  Completed stages: {', '.join(target.completed_stages) or '(none)'}")
    console.print(f"  Resume with: [bold]eurekaclaw resume {session_id}[/bold]")


@main.command()
def skills() -> None:
    """List all available skills in the skills bank."""
    from eurekaclaw.skills.registry import SkillRegistry
    registry = SkillRegistry()
    all_skills = registry.load_all()

    console.print(Panel(
        f"[bold]{len(all_skills)} skills loaded[/bold]\n\n" +
        "\n".join(
            f"• [cyan]{s.meta.name}[/cyan] ({', '.join(s.meta.tags[:3])}) — {s.meta.description[:60]}"
            for s in sorted(all_skills, key=lambda x: x.meta.name)
        ),
        title="[green]EurekaClaw Skills Bank[/green]",
    ))


@main.command()
@click.argument("session_id")
def eval_session(session_id: str) -> None:
    """Evaluate a completed research session."""
    from eurekaclaw.evaluation.evaluator import ScientistBenchEvaluator
    from eurekaclaw.knowledge_bus.bus import KnowledgeBus

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    bus = KnowledgeBus.load(session_id, session_dir)
    evaluator = ScientistBenchEvaluator()

    async def run_eval():
        return await evaluator.evaluate(bus)

    report = asyncio.run(run_eval())
    console.print(Panel(
        json.dumps(report.to_dict(), indent=2),
        title=f"[green]Evaluation Report: {session_id[:8]}[/green]",
    ))


@main.command("replay-theory-tail")
@click.argument("session_id")
@click.option(
    "--from",
    "from_stage",
    default="consistency_checker",
    type=click.Choice(["assembler", "theorem_crystallizer", "consistency_checker"]),
    show_default=True,
    help="Replay theory tail stages starting from this stage.",
)
def replay_theory_tail(session_id: str, from_stage: str) -> None:
    """Replay theory tail stages from a completed run.

    This is useful when you want to quickly retest:
    - assembler
    - theorem crystallization
    - consistency checking

    without rerunning survey, planning, or lemma proving.
    """
    import atexit

    from eurekaclaw.agents.theory.assembler import Assembler
    from eurekaclaw.agents.theory.consistency_checker import ConsistencyChecker
    from eurekaclaw.agents.theory.theorem_crystallizer import TheoremCrystallizer
    from eurekaclaw.ccproxy_manager import maybe_start_ccproxy
    from eurekaclaw.knowledge_bus.bus import KnowledgeBus
    from eurekaclaw.types.artifacts import TheoryState

    # Match the main session runner: when Anthropic OAuth is enabled,
    # ensure ccproxy is running and the Anthropic client env is wired up.
    if settings.anthropic_auth_mode == "oauth":
        try:
            _ccproxy_proc, _ccproxy_monitor = maybe_start_ccproxy()
            if _ccproxy_monitor:
                atexit.register(_ccproxy_monitor.stop)
        except (RuntimeError, ValueError) as exc:
            console.print(f"[red]ccproxy error: {exc}[/red]")
            sys.exit(1)

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    theory_path = session_dir / "theory_state.json"
    if not theory_path.exists():
        console.print(f"[red]No theory_state.json found in {session_dir}[/red]")
        sys.exit(1)

    state = TheoryState.model_validate_json(theory_path.read_text())
    bus = KnowledgeBus.load(session_id, session_dir)
    bus.put_theory_state(state)

    console.print(
        f"\n[bold green]Replaying theory tail[/bold green] [cyan]{session_id[:8]}[/cyan]"
        f"  from=[yellow]{from_stage}[/yellow]\n"
    )

    async def _run() -> TheoryState:
        current = state
        domain = ""
        stage_order = {
            "assembler": [
                ("assembler", Assembler()),
                ("theorem_crystallizer", TheoremCrystallizer()),
                ("consistency_checker", ConsistencyChecker()),
            ],
            "theorem_crystallizer": [
                ("theorem_crystallizer", TheoremCrystallizer()),
                ("consistency_checker", ConsistencyChecker()),
            ],
            "consistency_checker": [
                ("consistency_checker", ConsistencyChecker()),
            ],
        }[from_stage]

        for stage_name, stage in stage_order:
            console.print(f"[cyan]Running {stage_name}...[/cyan]")
            current = await stage.run(current, domain=domain)
            bus.put_theory_state(current)
        return current

    final_state = asyncio.run(_run())
    theory_path.write_text(final_state.model_dump_json(indent=2))
    bus.persist(session_dir)

    _print_proof_result(final_state)
    console.print(f"\n[green]Updated theory_state saved to[/green] {theory_path}\n")


@main.command("test-paper-reader")
@click.argument("session_id")
@click.argument("paper_ref")
@click.option(
    "--mode",
    default="both",
    type=click.Choice(["abstract", "pdf", "both"]),
    show_default=True,
    help="Which PaperReader extraction path to test.",
)
@click.option(
    "--direction",
    default="",
    help="Optional research direction override used in extraction prompts.",
)
def test_paper_reader(session_id: str, paper_ref: str, mode: str, direction: str) -> None:
    """Test PaperReader on a single bibliography entry from an existing run.

    PAPER_REF can be either:
    - the exact paper_id / arxiv_id, or
    - a case-insensitive substring of the paper title

    This bypasses survey/planning and directly exercises PaperReader's
    abstract and/or PDF extraction paths.
    """
    import atexit

    from eurekaclaw.agents.theory.paper_reader import PaperReader
    from eurekaclaw.ccproxy_manager import maybe_start_ccproxy
    from eurekaclaw.knowledge_bus.bus import KnowledgeBus
    from eurekaclaw.types.artifacts import TheoryState

    if settings.anthropic_auth_mode == "oauth":
        try:
            _ccproxy_proc, _ccproxy_monitor = maybe_start_ccproxy()
            if _ccproxy_monitor:
                atexit.register(_ccproxy_monitor.stop)
        except (RuntimeError, ValueError) as exc:
            console.print(f"[red]ccproxy error: {exc}[/red]")
            sys.exit(1)

    session_dir = settings.runs_dir / session_id
    if not session_dir.exists():
        console.print(f"[red]Session not found: {session_dir}[/red]")
        sys.exit(1)

    bus = KnowledgeBus.load(session_id, session_dir)
    bib = bus.get_bibliography()
    if not bib or not bib.papers:
        console.print(f"[red]No bibliography found in {session_dir}[/red]")
        sys.exit(1)

    ref_lower = paper_ref.strip().lower()
    matches = [
        p for p in bib.papers
        if p.paper_id.lower() == ref_lower
        or (p.arxiv_id or "").lower() == ref_lower
        or ref_lower in p.title.lower()
    ]
    if not matches:
        console.print(f"[red]No paper matched '{paper_ref}' in session {session_id}.[/red]")
        sys.exit(1)
    if len(matches) > 1:
        console.print("[yellow]Multiple papers matched; using the most relevant one:[/yellow]")
        matches = sorted(matches, key=lambda p: p.relevance_score, reverse=True)
    paper = matches[0]

    brief = bus.get_research_brief()
    test_direction = (
        direction
        or (brief.selected_direction.hypothesis if brief and brief.selected_direction else "")
        or paper.title
    )
    reader = PaperReader(bus)
    state = TheoryState(session_id=session_id, theorem_id="paper_reader_test", informal_statement=test_direction)

    console.print(
        f"\n[bold green]Testing PaperReader[/bold green] [cyan]{session_id[:8]}[/cyan]"
        f"\nPaper: [bold]{paper.title}[/bold]"
        f"\nPaper ID: [cyan]{paper.paper_id}[/cyan]"
        f"\nArXiv ID: [cyan]{paper.arxiv_id or '(none)'}[/cyan]"
        f"\nMode: [yellow]{mode}[/yellow]\n"
    )

    async def _run_test() -> tuple[list, list]:
        abstract_results = []
        pdf_results = []
        if mode in ("abstract", "both"):
            console.print("[cyan]Running abstract extraction...[/cyan]")
            abstract_results = await reader._extract_from_paper(
                paper.paper_id,
                paper.title,
                paper.abstract,
                test_direction,
            )
        if mode in ("pdf", "both"):
            console.print("[cyan]Running PDF extraction...[/cyan]")
            pdf_results = await reader._extract_from_paper_pdf(
                paper.paper_id,
                paper.title,
                paper.arxiv_id or "",
                test_direction,
            )
        return abstract_results, pdf_results

    abstract_results, pdf_results = asyncio.run(_run_test())

    def _print_results(label: str, results: list) -> None:
        console.print(f"\n[bold]{label}[/bold]: {len(results)} result(s)")
        for idx, item in enumerate(results[:8], 1):
            console.print(
                f"{idx}. [{item.result_type}] source={item.extraction_source} "
                f"technique={item.proof_technique or 'unspecified'}"
            )
            console.print(f"   {item.statement[:220]}")

    if mode in ("abstract", "both"):
        _print_results("Abstract extraction", abstract_results)
    if mode in ("pdf", "both"):
        _print_results("PDF extraction", pdf_results)

    if mode == "both":
        console.print(
            f"\n[green]Summary:[/green] abstract={len(abstract_results)} result(s), "
            f"pdf={len(pdf_results)} result(s)"
        )


@main.command()
@click.option("--non-interactive", is_flag=True, help="Write defaults without prompting.")
@click.option("--reset", is_flag=True, help="Overwrite existing .env without merging.")
@click.option("--env-file", default=".env", show_default=True, help="Path to the .env file to write.")
def onboard(non_interactive: bool, reset: bool, env_file: str) -> None:
    """Interactive wizard to configure EurekaClaw options in .env.

    Walks you through LLM backend, API keys, search tools, and system
    behaviour, then writes (or updates) the .env file.

    Example:
        eurekaclaw onboard
        eurekaclaw onboard --env-file ~/.eurekaclaw/.env
    """
    from eurekaclaw.onboard import run_onboard
    run_onboard(non_interactive=non_interactive, reset=reset, env_file=env_file)


@main.command()
@click.argument("skillname", default="")
@click.option("--force", "-f", is_flag=True, help="Overwrite skills that are already installed.")
def install_skills(force: bool, skillname: str = "") -> None:
    """Copy seed skills to ~/.eurekaclaw/skills/.

    Skips files that already exist unless --force is given.
    If skillname is provided, install only that skill from clawhub.
    """
    from eurekaclaw.skills.registry import _SEED_DIR
    import shutil
    from eurekaclaw.utils import copy_file
    from eurekaclaw.skills.install import install_from_hub, install_seed_skills

    settings.ensure_dirs()
    dest = settings.skills_dir
    
    if skillname:
        success = install_from_hub(skillname, dest)
        if not success:
            console.print(f"[red]Failed to install skill '{skillname}' from clawhub.[/red]")
            sys.exit(1)
        console.print(f"[green]Installed skill from clawhub: {skillname} to {dest}[/green]")
    else:
        install_seed_skills(dest)
        console.print(f"[green]Installed seed skills to {dest}[/green]")
    


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind the UI server to.")
@click.option("--port", default=8080, type=int, help="Port to bind the UI server to.")
@click.option("--open-browser/--no-open-browser", default=False, help="Open the UI in the default browser.")
def ui(host: str, port: int, open_browser: bool) -> None:
    """Launch the EurekaClaw browser UI."""
    import threading
    import time
    import webbrowser

    import os
    os.environ["EUREKACLAW_UI_MODE"] = "1"

    from eurekaclaw.ui.server import bind_ui_server

    try:
        server = bind_ui_server(host=host, port=port)
    except OSError as exc:
        console.print(f"[red]Failed to start UI server: {exc}[/red]")
        raise SystemExit(1) from exc

    actual_host, actual_port = server.server_address
    url = f"http://{actual_host}:{actual_port}/"
    if actual_port != port:
        console.print(
            f"[yellow]Port {port} unavailable — using {url} instead.[/yellow]\n"
            f"  Run [bold]eurekaclaw ui --port {actual_port}[/bold] to avoid this message."
        )
    else:
        console.print(f"[green]Starting EurekaClaw UI on {url}[/green]")

    if open_browser:
        def _open() -> None:
            time.sleep(1.0)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _run_with_pause_support(
    coro: Any,
    cp: ProofCheckpoint,
) -> Any:
    """Run *coro* in a new event loop with Ctrl+C wired to immediate cancellation.

    When SIGINT fires:
    1. The pause flag is written.
    2. The running asyncio task is cancelled — the current LLM await is
       interrupted immediately.
    3. inner_loop_yaml.run() catches CancelledError, saves a checkpoint
       with all lemmas proved so far, and raises ProofPausedException.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _task_ref: list[asyncio.Task[Any]] = []

    def _pause_now() -> None:
        cp.request_pause()
        console.print(
            "\n[yellow]Pause requested — stopping immediately and saving checkpoint...[/yellow]"
        )
        if _task_ref:
            _task_ref[0].cancel()

    import sys as _sys

    try:
        if _sys.platform == "win32":
            signal.signal(signal.SIGINT, lambda *_: _pause_now())
        else:
            loop.add_signal_handler(signal.SIGINT, _pause_now)

        async def _wrap() -> "Any":
            task = asyncio.current_task()
            assert task is not None
            _task_ref.append(task)

            # Background poller: cancel the task when pause flag is written
            # by an external `eurekaclaw pause <session_id>` command.
            async def _poll_pause_flag() -> None:
                while True:
                    await asyncio.sleep(1)
                    if cp.is_pause_requested() and not task.cancelled():
                        console.print(
                            "\n[yellow]Pause flag detected — stopping immediately and saving checkpoint...[/yellow]"
                        )
                        task.cancel()
                        return

            poll_task = asyncio.create_task(_poll_pause_flag())
            try:
                return await coro
            finally:
                poll_task.cancel()

        return loop.run_until_complete(_wrap())
    finally:
        try:
            if _sys.platform == "win32":
                signal.signal(signal.SIGINT, signal.SIG_DFL)
            else:
                loop.remove_signal_handler(signal.SIGINT)
        except Exception:
            pass
        loop.close()
        asyncio.set_event_loop(None)


def _print_proof_result(state: TheoryState) -> None:
    from rich.table import Table
    tbl = Table(show_header=True)
    tbl.add_column("Field", style="bold")
    tbl.add_column("Value")
    tbl.add_row("Status", state.status)
    tbl.add_row("Proven lemmas", str(len(state.proven_lemmas)))
    tbl.add_row("Open goals", str(len(state.open_goals)))
    console.print(tbl)


def _compile_pdf(tex_path: Path) -> None:
    """Compile LaTeX to PDF: pdflatex → bibtex (if .bib exists) → pdflatex → pdflatex."""
    import subprocess

    latex_bin = settings.latex_bin
    out_dir = tex_path.parent.resolve()
    tex_abs = tex_path.resolve()
    pdf_path = out_dir / tex_path.with_suffix(".pdf").name
    bib_path = out_dir / "references.bib"

    latex_cmd = [
        latex_bin, "-interaction=nonstopmode",
        "-output-directory", str(out_dir),
        str(tex_abs),
    ]

    try:
        subprocess.run(latex_cmd, capture_output=True, check=False, cwd=out_dir)

        if bib_path.exists():
            bibtex_result = subprocess.run(
                ["bibtex", tex_path.stem],
                capture_output=True, check=False, cwd=out_dir,
            )
            if bibtex_result.returncode != 0:
                console.print("[yellow]bibtex warnings — bibliography may be incomplete[/yellow]")

        subprocess.run(latex_cmd, capture_output=True, check=False, cwd=out_dir)
        subprocess.run(latex_cmd, capture_output=True, check=False, cwd=out_dir)

        if pdf_path.exists():
            console.print(f"[green]PDF generated: {pdf_path}[/green]")
        else:
            console.print(f"[yellow]pdflatex produced no PDF — check {out_dir}/paper.log[/yellow]")
            _show_latex_errors(out_dir / tex_path.with_suffix(".log").name)
    except FileNotFoundError:
        console.print(
            f"[yellow]PDF generation skipped: '{latex_bin}' not found. "
            "Install TeX Live or set LATEX_BIN in .env.[/yellow]"
        )


def _show_latex_errors(log_path: Path) -> None:
    """Extract and print error lines from a pdflatex .log file."""
    if not log_path.exists():
        console.print(f"[yellow]  No log file found at {log_path}[/yellow]")
        return
    errors = []
    try:
        lines = log_path.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines):
            if line.startswith("!") or (line.startswith("l.") and errors):
                errors.append(line)
                # include the next two context lines pdflatex prints after "!"
                errors.extend(lines[i + 1 : i + 3])
        if errors:
            console.print("[yellow]  LaTeX errors:[/yellow]")
            for err in errors[:20]:  # cap at 20 lines
                console.print(f"[red]  {err}[/red]")
        else:
            console.print(f"[yellow]  No explicit errors found in log. Full log: {log_path}[/yellow]")
    except Exception as exc:
        console.print(f"[yellow]  Could not read log file: {exc}[/yellow]")


def _slugify(text: str, max_len: int = 60) -> str:
    """Convert free-form text to a filesystem-safe kebab-case slug."""
    import re
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:max_len].rstrip("-")


def _prompt_artifact_name(query: str, domain: str) -> str:
    """Prompt the user for an output file base name.

    Suggests a slug derived from the query/domain.  The user can accept
    it (Enter), type a custom name, or leave blank for generic defaults.
    """
    from rich.prompt import Prompt

    source = query or domain or ""
    # Take first ~8 meaningful words for the suggestion
    words = source.split()[:8]
    default = _slugify(" ".join(words)) if words else ""

    try:
        hint = f" [dim](default: [cyan]{default}[/cyan])[/dim]" if default else ""
        name = Prompt.ask(
            f"\n[bold]Output file base name[/bold]{hint}\n"
            "[dim]Enter a name, press Enter for default, or type 'skip' for generic names[/dim]",
            default=default,
        )
    except (KeyboardInterrupt, EOFError):
        return default

    name = name.strip()
    if name.lower() == "skip" or not name:
        return ""
    return _slugify(name)


def _run_session(
    mode: str,
    query: str,
    domain: str,
    conjecture: str | None = None,
    paper_ids: list[str] | None = None,
    learn_mode: str = "skills_only",
    gate: str = "human",
    skills: list[str] | None = None,
    output_dir: str = "",
    _preloaded_papers: list | None = None,
    _additional_context: str = "",
    _draft_path: str = "",
) -> None:
    """Common session runner."""
    import os
    from eurekaclaw.main import EurekaSession, save_artifacts
    from eurekaclaw.types.tasks import InputSpec

    # Override the settings singleton in-place so all already-imported modules
    # see the new values (importlib.reload would create a new object that old
    # references wouldn't see).
    os.environ["EUREKACLAW_MODE"] = learn_mode
    os.environ["GATE_MODE"] = gate
    settings.eurekaclaw_mode = learn_mode  # type: ignore[misc]
    settings.gate_mode = gate  # type: ignore[misc]

    # --- ccproxy: start if ANTHROPIC_AUTH_MODE=oauth -------------------------
    _ccproxy_proc = None
    if settings.anthropic_auth_mode == "oauth":
        try:
            from eurekaclaw.ccproxy_manager import maybe_start_ccproxy
            _ccproxy_proc, _ccproxy_monitor = maybe_start_ccproxy()
            if _ccproxy_monitor:
                import atexit
                atexit.register(_ccproxy_monitor.stop)
        except (RuntimeError, ValueError) as exc:
            console.print(f"[red]ccproxy error: {exc}[/red]")
            sys.exit(1)

    spec = InputSpec(
        mode=mode,  # type: ignore[arg-type]
        query=query,
        conjecture=conjecture,
        domain=domain,
        paper_ids=paper_ids or [],
        selected_skills=list(skills or []),
    )

    session = EurekaSession()

    # Pre-populate bibliography if papers were loaded externally (e.g. from-bib)
    if _preloaded_papers:
        from eurekaclaw.types.artifacts import Bibliography
        bib = Bibliography(session_id=session.session_id, papers=_preloaded_papers)
        session.bus.put_bibliography(bib)

    from eurekaclaw.agents.theory.checkpoint import ProofCheckpoint, ProofPausedException
    _cp = ProofCheckpoint(session.session_id)

    console.print(
        f"[dim]Session ID: [cyan]{session.session_id}[/cyan]"
        "  (use this to resume if paused)[/dim]"
    )

    # Inject draft/additional context into the InputSpec
    if _additional_context:
        spec.additional_context = _additional_context
    if _draft_path:
        spec.draft_path = _draft_path

    try:
        result = _run_with_pause_support(session.run(spec), _cp)
    except ProofPausedException as exc:
        console.print(
            f"\n[yellow]Proof paused before stage '{exc.stage_name}'.[/yellow]"
            f"\nResume with:  [bold]eurekaclaw resume {exc.session_id}[/bold]\n"
        )
        return
    except asyncio.CancelledError:
        # Pause fired during a non-theory stage (survey, ideation, etc.)
        # No theory checkpoint exists yet, but session state is written to disk.
        console.print(
            f"\n[yellow]Session interrupted during early pipeline stage.[/yellow]"
            f"\nNo checkpoint available — restart with the same command to try again.\n"
        )
        return

    artifact_name = _prompt_artifact_name(query, domain)
    out = save_artifacts(result, output_dir or "./results", artifact_name=artifact_name)
    console.print(f"[green]Artifacts saved to {out}[/green]")


if __name__ == "__main__":
    main()
