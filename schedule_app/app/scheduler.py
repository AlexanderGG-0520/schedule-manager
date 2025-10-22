"""Dedicated scheduler runner using APScheduler.

This process is intended to run separately from the WSGI workers (e.g. as a separate container or systemd service).
It uses APScheduler with SQLAlchemyJobStore so job definitions are persisted, and each job should acquire
an advisory lock in Postgres to ensure single execution across processes.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask import Flask
from . import create_app, db
from .config import Config

logger = logging.getLogger("scheduler")


def setup_logging():
    handler = RotatingFileHandler("/tmp/scheduler.log", maxBytes=10 * 1024 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def get_scheduler(app: Flask) -> BackgroundScheduler:
    # Use SQLAlchemyJobStore so jobs persist and can be inspected across restarts
    jobstore_url = app.config.get("SQLALCHEMY_DATABASE_URI")
    jobstores = {
        "default": SQLAlchemyJobStore(url=jobstore_url)
    }
    sched = BackgroundScheduler(jobstores=jobstores)
    return sched


def register_jobs(scheduler: BackgroundScheduler, app: Flask):
    """Import and register jobs here.

    Keep jobs idempotent and guarded with `single_instance` (Postgres advisory lock) decorator.
    Example:

    from .jobs import cleanup_old_events
    scheduler.add_job(cleanup_old_events, "interval", minutes=15, id="cleanup_old_events")
    """
    # Import jobs lazily so the app context and DB models are available
    try:
        with app.app_context():
            # Example job registration; if you have a jobs module, import it here
            from .jobs import cleanup_old_events  # type: ignore

            scheduler.add_job(cleanup_old_events, "interval", minutes=15, id="cleanup_old_events", replace_existing=True)
            logger.info("Registered job cleanup_old_events")
    except Exception as e:
        logger.exception("Failed to register jobs: %s", e)


def run():
    app = create_app()
    setup_logging()

    scheduler = get_scheduler(app)
    register_jobs(scheduler, app)

    # Start scheduler inside app context
    with app.app_context():
        scheduler.start()
        logger.info("Scheduler started")
        try:
            # Keep the process alive; APScheduler runs in background threads
            import time
            while True:
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down scheduler")
            scheduler.shutdown()
