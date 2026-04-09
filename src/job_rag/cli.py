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
) -> None:
    """List all ingested job postings."""
    from job_rag.db.engine import SessionLocal
    from job_rag.db.models import JobPostingDB

    session = SessionLocal()
    try:
        query = session.query(JobPostingDB).order_by(JobPostingDB.company)
        if company:
            query = query.filter(JobPostingDB.company.ilike(f"%{company}%"))
        postings = query.all()

        if not postings:
            typer.echo("No postings found.")
            return

        typer.echo(f"\n{'Company':<25} {'Title':<40} {'Location':<20} {'Remote':<10}")
        typer.echo("-" * 95)
        for p in postings:
            typer.echo(f"{p.company:<25} {p.title:<40} {p.location:<20} {p.remote_policy:<10}")
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
            category_counts[req.category] += 1
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

        # Seniority distribution
        seniority_counts: Counter[str] = Counter()
        for p in session.query(JobPostingDB).all():
            seniority_counts[p.seniority] += 1

        typer.echo("\n--- Seniority Distribution ---")
        for level, count in seniority_counts.most_common():
            typer.echo(f"  {level:<20} {count:>3}")

        # Remote policy distribution
        remote_counts: Counter[str] = Counter()
        for p in session.query(JobPostingDB).all():
            remote_counts[p.remote_policy] += 1

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
