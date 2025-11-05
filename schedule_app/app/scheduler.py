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
        # Import jobs (no app_context required for import). When APScheduler executes
        # the job functions they run in worker threads without a Flask application
        # context — wrap them so each execution runs inside `app.app_context()`.
        from . import jobs as jobs_module  # type: ignore

        def _wrap(fn):
            # preserve function identity where possible
            def _wrapped(*a, **kw):
                with app.app_context():
                    return fn(*a, **kw)

            try:
                _wrapped.__name__ = fn.__name__
            except Exception:
                pass
            return _wrapped

        # Auto-discover functions in the jobs module that are annotated with
        # the @job(...) decorator (they will have a .job_meta attribute).
        registered = 0
        for name in dir(jobs_module):
            try:
                fn = getattr(jobs_module, name)
            except Exception:
                continue
            if not callable(fn):
                continue
            meta = getattr(fn, "job_meta", None)
            if not meta:
                continue
            schedule_type = meta.get("schedule", "interval")
            job_id = meta.get("id", name)
            try:
                wrapped = _wrap(fn)
                kwargs = {"id": job_id, "replace_existing": True}
                if schedule_type == "interval":
                    interval_kwargs = {}
                    # copy supported interval args if provided
                    for k in ("weeks", "days", "hours", "minutes", "seconds"):
                        if k in meta:
                            interval_kwargs[k] = meta[k]
                    if not interval_kwargs:
                        # sensible default if none provided
                        interval_kwargs["minutes"] = 15
                    scheduler.add_job(wrapped, "interval", **interval_kwargs, **kwargs)
                else:
                    logger.info("Unsupported schedule type %s for job %s", schedule_type, name)
                    continue
                registered += 1
                logger.info("Registered job %s (wrapped) schedule=%s meta=%s", job_id, schedule_type, meta)
            except Exception:
                logger.exception("Failed to register job %s", name)
        if registered == 0:
            logger.info("No decorated jobs found in jobs module to register")
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
