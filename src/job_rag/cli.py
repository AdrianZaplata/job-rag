from pathlib import Path

import typer

app = typer.Typer(name="job-rag", help="RAG system for AI Engineer job postings")


@app.command()
def init_db() -> None:
    """Create database tables and enable pgvector extension."""
    from job_rag.db.engine import init_db as _init_db

    _init_db()
    typer.echo("Database initialized successfully.")


@app.command()
def ingest(
    directory: Path = typer.Option(None, "--dir", "-d", help="Directory containing markdown files"),
    show_cost: bool = typer.Option(False, "--show-cost", help="Print total extraction cost"),
) -> None:
    """Ingest job posting markdown files into the database."""
    from job_rag.db.engine import SessionLocal
    from job_rag.services.ingestion import ingest_directory

    session = SessionLocal()
    try:
        summary = ingest_directory(session, directory)
        typer.echo("\nIngestion complete:")
        typer.echo(f"  Total files:  {summary['total_files']}")
        typer.echo(f"  Ingested:     {summary['ingested']}")
        typer.echo(f"  Skipped:      {summary['skipped']}")
        typer.echo(f"  Errors:       {summary['errors']}")
        if show_cost:
            typer.echo(f"  Total cost:   ${summary['total_cost_usd']:.4f}")
        if summary["error_details"]:
            typer.echo("\nErrors:")
            for filename, error in summary["error_details"]:
                typer.echo(f"  {filename}: {error}")
    finally:
        session.close()


@app.command()
def embed(
    show_cost: bool = typer.Option(False, "--show-cost", help="Print total embedding cost"),
) -> None:
    """Generate embeddings for all postings that don't have them yet."""
    from job_rag.db.engine import SessionLocal
    from job_rag.services.embedding import embed_all_postings

    session = SessionLocal()
    try:
        summary = embed_all_postings(session)
        typer.echo("\nEmbedding complete:")
        typer.echo(f"  Total unembedded: {summary['total']}")
        typer.echo(f"  Embedded:         {summary['embedded']}")
        if show_cost:
            typer.echo(f"  Total cost:       ${summary['total_cost_usd']:.6f}")
    finally:
        session.close()


@app.command(name="list")
def list_postings(
    company: str = typer.Option(None, "--company", "-c", help="Filter by company name"),
    stats: bool = typer.Option(
        False,
        "--stats",
        help="Print prompt_version distribution instead of the posting table.",
    ),
) -> None:
    """List all ingested job postings, or print prompt_version distribution
    when --stats is passed (CORP-04 / D-17 drift surface)."""
    from collections import Counter

    from job_rag.db.engine import SessionLocal
    from job_rag.db.models import JobPostingDB
    from job_rag.extraction.prompt import PROMPT_VERSION

    session = SessionLocal()
    try:
        if stats:
            # CORP-04 surface: prompt_version distribution.
            counts: Counter[str] = Counter()
            for p in session.query(JobPostingDB).all():
                counts[p.prompt_version] += 1
            if not counts:
                typer.echo("No postings ingested yet.")
                return
            typer.echo(
                f"\n=== Prompt version distribution (current: {PROMPT_VERSION}) ==="
            )
            total = sum(counts.values())
            for ver, count in sorted(counts.items(), reverse=True):
                marker = "" if ver == PROMPT_VERSION else " STALE"
                typer.echo(f"  prompt_version={ver}: {count}{marker}")
            typer.echo(f"\nTotal: {total} postings")
            stale = total - counts.get(PROMPT_VERSION, 0)
            if stale:
                typer.echo(
                    f"Stale: {stale} - run `job-rag reextract` to refresh."
                )
            return

        query = session.query(JobPostingDB).order_by(JobPostingDB.company)
        if company:
            query = query.filter(JobPostingDB.company.ilike(f"%{company}%"))
        postings = query.all()

        if not postings:
            typer.echo("No postings found.")
            return

        # NOTE: free-text `location` column was DROPPED in 0004 (D-11).
        # Display location_country (or "-" if NULL) -- Phase 5 dashboard
        # consumes the structured location_country/city/region columns.
        typer.echo(
            f"\n{'Company':<25} {'Title':<40} {'Country':<8} {'Remote':<10}"
        )
        typer.echo("-" * 83)
        for p in postings:
            country = p.location_country or "-"
            typer.echo(
                f"{p.company:<25} {p.title:<40} {country:<8} {p.remote_policy:<10}"
            )
        typer.echo(f"\nTotal: {len(postings)} postings")
    finally:
        session.close()


@app.command()
def stats() -> None:
    """Show skill frequency and category breakdown."""
    from collections import Counter

    from job_rag.db.engine import SessionLocal
    from job_rag.db.models import JobPostingDB, JobRequirementDB

    session = SessionLocal()
    try:
        posting_count = session.query(JobPostingDB).count()
        if posting_count == 0:
            typer.echo("No postings ingested yet. Run 'job-rag ingest' first.")
            return

        requirements = session.query(JobRequirementDB).all()

        # Skill frequency
        skill_counts: Counter[str] = Counter()
        category_counts: Counter[str] = Counter()
        must_have_counts: Counter[str] = Counter()

        for req in requirements:
            skill_counts[req.skill] += 1
            category_counts[req.skill_type] += 1
            if req.required:
                must_have_counts[req.skill] += 1

        typer.echo("\n=== Job Posting Stats ===")
        typer.echo(f"Total postings: {posting_count}")
        typer.echo(f"Total requirements extracted: {len(requirements)}")

        typer.echo("\n--- Top 20 Skills (by frequency) ---")
        for skill, count in skill_counts.most_common(20):
            must_have = must_have_counts.get(skill, 0)
            typer.echo(f"  {skill:<35} {count:>3}x  (must-have: {must_have})")

        typer.echo("\n--- Category Breakdown ---")
        for cat, count in category_counts.most_common():
            typer.echo(f"  {cat:<20} {count:>3}")

        # Seniority and remote policy distributions (single query)
        seniority_counts: Counter[str] = Counter()
        remote_counts: Counter[str] = Counter()
        for p in session.query(JobPostingDB).all():
            seniority_counts[p.seniority] += 1
            remote_counts[p.remote_policy] += 1

        typer.echo("\n--- Seniority Distribution ---")
        for level, count in seniority_counts.most_common():
            typer.echo(f"  {level:<20} {count:>3}")

        typer.echo("\n--- Remote Policy Distribution ---")
        for policy, count in remote_counts.most_common():
            typer.echo(f"  {policy:<20} {count:>3}")

    finally:
        session.close()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("job_rag.api.app:app", host=host, port=port, reload=reload)


@app.command()
def reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete all postings, requirements, and chunks — forces full re-extraction.

    Useful after bumping PROMPT_VERSION or updating the extraction prompt.
    """
    from job_rag.db.engine import SessionLocal
    from job_rag.db.models import JobPostingDB

    session = SessionLocal()
    try:
        count = session.query(JobPostingDB).count()
        if count == 0:
            typer.echo("Database is already empty.")
            return

        if not yes:
            confirm = typer.confirm(
                f"Delete all {count} postings (and their requirements + chunks)?"
            )
            if not confirm:
                typer.echo("Aborted.")
                return

        session.query(JobPostingDB).delete()
        session.commit()
        typer.echo(f"Deleted {count} postings.")
    finally:
        session.close()


@app.command()
def mcp() -> None:
    """Start the MCP server over stdio (for Claude Code and other MCP clients)."""
    from job_rag.mcp_server.server import run

    run()


@app.command()
def agent(
    query: str = typer.Argument(..., help="Question to ask the agent"),
    stream: bool = typer.Option(False, "--stream", help="Stream tool calls and tokens"),
) -> None:
    """Run the LangGraph agent on a single query."""
    import asyncio

    from job_rag.observability import flush

    async def _run() -> None:
        if stream:
            from job_rag.agent.stream import stream_agent

            async for event in stream_agent(query):
                # Plan 04: stream_agent now yields Pydantic AgentEvent
                # instances; use attribute access on the discriminator + payload
                # fields. Wire shape (model_dump_json) remains identical to the
                # legacy dict form so any downstream output stays equivalent.
                etype = event.type
                if etype == "token":
                    typer.echo(event.content, nl=False)  # type: ignore[union-attr]
                elif etype == "tool_start":
                    typer.echo(f"\n[tool→ {event.name}({event.args})]")  # type: ignore[union-attr]
                elif etype == "tool_end":
                    pass  # tool result already shown via token stream from next LLM call
                elif etype == "final":
                    typer.echo("")  # newline after final
        else:
            from job_rag.agent.graph import run_agent

            result = await run_agent(query)
            typer.echo(result["answer"])
            if result["tool_calls"]:
                typer.echo(
                    f"\n[{len(result['tool_calls'])} tool calls: "
                    f"{', '.join(c['name'] for c in result['tool_calls'])}]"
                )

    try:
        asyncio.run(_run())
    finally:
        flush()


@app.command()
def reextract(
    all: bool = typer.Option(
        False, "--all",
        help="Re-extract every row regardless of prompt_version (escape hatch).",
    ),
    posting_id: str = typer.Option(
        None, "--posting-id",
        help="Re-extract a single posting by UUID.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Count what would be re-extracted; do not UPDATE.",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Skip the --all confirmation prompt (T-CLI-01 mitigation).",
    ),
) -> None:
    """Re-extract postings whose prompt_version is stale (D-12, D-14, D-16).

    Default selection (no flags): rows WHERE prompt_version != PROMPT_VERSION.
    Per-posting commit; failures are logged + reported, never abort the loop.
    Embeddings + raw_text are PRESERVED (D-15).
    """
    import asyncio
    from uuid import UUID

    from job_rag.extraction.prompt import PROMPT_VERSION
    from job_rag.services.extraction import reextract_stale

    # T-CLI-01: --all guard rail. typer.confirm returns False on stdin EOF.
    if all and not yes:
        confirm = typer.confirm(
            "Re-extract EVERY posting regardless of prompt_version? "
            "(~3-5 minutes, ~€0.20)",
            default=False,
        )
        if not confirm:
            typer.echo("Aborted.")
            raise typer.Exit(code=1)
        yes = True

    async def _run():
        pid = UUID(posting_id) if posting_id else None
        return await reextract_stale(
            all=all, posting_id=pid, dry_run=dry_run, yes=yes,
        )

    report = asyncio.run(_run())

    typer.echo(f"\nRe-extraction complete (PROMPT_VERSION={PROMPT_VERSION}):")
    typer.echo(f"  Selected:    {report.selected}")
    typer.echo(f"  Succeeded:   {report.succeeded}")
    typer.echo(f"  Failed:      {report.failed}")
    typer.echo(f"  Skipped:     {report.skipped}")
    typer.echo(f"  Total cost:  ${report.total_cost_usd:.4f}")
    if report.failures:
        typer.echo("\nFailures:")
        for pid, err in report.failures:
            typer.echo(f"  {pid}: {err}")
