from __future__ import annotations

import click
from flask import current_app


@click.group()
def scheduler_cli():
    """Scheduler related commands."""
    pass


@scheduler_cli.command("run")
def run_scheduler():
    """Run the dedicated scheduler process. Use in production as separate container or systemd service."""
    # Import lazily to avoid importing APScheduler at Flask startup when not needed
    from .scheduler import run

    current_app.logger.info("Starting scheduler via CLI")
    run()
