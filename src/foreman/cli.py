"""Command line entry point.

Scenarios, traces and diagnostics arrive with later phases. For now this exists
so the console script resolves and the Phase 0 gate can be checked.
"""

from __future__ import annotations

import typer

from foreman import __version__
from foreman.core.config import get_settings

app = typer.Typer(
    name="foreman",
    help="An enterprise agent platform that shows its work.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(f"foreman {__version__}")


@app.command()
def config() -> None:
    """Show the resolved configuration. Secrets are never printed."""
    s = get_settings()
    rows: list[tuple[str, str]] = [
        ("environment", s.env),
        ("runtime", s.runtime),
        ("small tier", " -> ".join(s.tier_small)),
        ("large tier", " -> ".join(s.tier_large)),
        ("max steps", str(s.max_steps)),
        ("budget per run", f"{s.max_cost_per_run_cents}c"),
        ("kill switch", "on" if s.kill_switch else "off"),
    ]
    width = max(len(k) for k, _ in rows)
    for key, value in rows:
        typer.echo(f"{key.ljust(width)}  {value}")

    # Report whether a credential is present, never what it holds.
    configured = [
        n
        for n in ("openai", "anthropic", "google", "groq", "openrouter")
        if s.provider_configured(n)
    ]
    typer.echo(f"{'providers with keys'.ljust(width)}  {', '.join(configured) or 'none'}")


if __name__ == "__main__":  # pragma: no cover
    app()
