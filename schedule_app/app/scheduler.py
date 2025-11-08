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


def run_job_in_app_context(module_name: str, func_name: str, *a, **kw):
    """Import and run a function inside a fresh Flask app context.

    This function is importable by textual reference (module:function) so it can be
    stored by APScheduler as a string reference. The dispatcher will import the
    target function by module/name and execute it inside a newly created
    application context (calls `create_app()` each time).
    """
    try:
        # Create an app for the scheduler execution context
        app = create_app()
        # Import the target module and fetch the callable
        import importlib

        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name)
        with app.app_context():
            return fn(*a, **kw)
    except Exception:
        logger.exception("Failed to run job %s.%s in app context", module_name, func_name)
        raise


def register_jobs(scheduler: BackgroundScheduler, app: Flask):
    """Import and register jobs here.

    Keep jobs idempotent and guarded with `single_instance` (Postgres advisory lock) decorator.
    Example:

    from .jobs import cleanup_old_events
    scheduler.add_job(cleanup_old_events, "interval", minutes=15, id="cleanup_old_events")
    """
    # Import jobs lazily so the app context and DB models are available
    try:
        # Remove any previously persisted jobs to avoid executing stale
        # callables that were stored with non-importable references.
        try:
            scheduler.remove_all_jobs()
            logger.info("Cleared existing jobs from jobstore before (re)registering")
        except Exception:
            logger.exception("Failed to clear existing jobs from jobstore; continuing to register")

        # Import jobs (no app_context required for import). When APScheduler executes
        # the job functions they run in worker threads without a Flask application
        # context — wrap them so each execution runs inside `app.app_context()`.
        from . import jobs as jobs_module  # type: ignore

        # We avoid scheduling local/wrapped callables (which APScheduler cannot
        # serialize to a textual reference). Instead we schedule a top-level
        # dispatcher `run_job_in_app_context` (defined in this module) and pass
        # the target function's module and name as args. APScheduler will store
        # the dispatcher as a textual reference which is importable on restart.

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
                # textual reference to the dispatcher in this module
                dispatcher_ref = f"{__name__}:run_job_in_app_context"
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
                    # Pass the target function's module and name as the first
                    # two positional args to the dispatcher.
                    scheduler.add_job(
                        dispatcher_ref,
                        "interval",
                        args=[fn.__module__, fn.__name__],
                        **interval_kwargs,
                        **kwargs,
                    )
                else:
                    logger.info("Unsupported schedule type %s for job %s", schedule_type, name)
                    continue
                registered += 1
                logger.info("Registered job %s (via dispatcher) schedule=%s meta=%s", job_id, schedule_type, meta)
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
