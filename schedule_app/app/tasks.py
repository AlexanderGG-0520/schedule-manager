"""Task runner invoked by CronJob or ad-hoc CLI.

Run with:
  python -m schedule_app.app.tasks run

This module will import `schedule_app.app.jobs` if present and attempt to run
`run_due_jobs()` or fallback known job functions. Each top-level invocation is
guarded by a Postgres advisory lock via `pg_lock` to avoid duplicate execution
across replicas/processes.
"""
from __future__ import annotations

import logging
import sys

from . import create_app


logger = logging.getLogger("tasks")


def _run_app_tasks():
    app = create_app()
    with app.app_context():
        logger.info("Starting tasks runner")
        # Prefer a consolidated runner function in schedule_app.app.jobs
        try:
            from .jobs import run_due_jobs  # type: ignore

            fn_name = "run_due_jobs"
            fn = run_due_jobs
        except Exception:
            # Fallbacks: known per-job functions
            try:
                from .jobs import cleanup_old_events  # type: ignore

                fn_name = "cleanup_old_events"
                fn = cleanup_old_events
            except Exception:
                logger.warning("No jobs found in schedule_app.app.jobs; nothing to run")
                return

        # Use Postgres advisory lock to ensure single execution across processes
        try:
            from .utils.pg_lock import pg_try_advisory_lock

            with pg_try_advisory_lock(fn_name) as locked:
                if not locked:
                    logger.info("Lock not acquired for %s, skipping", fn_name)
                    return
                logger.info("Lock acquired for %s, running job", fn_name)
                fn()
                logger.info("Job %s finished", fn_name)
        except Exception:
            # If pg_lock isn't available or Postgres not configured, run once and log
            logger.exception("pg_lock failed or not available; attempting to run job directly")
            try:
                fn()
            except Exception:
                logger.exception("Job %s failed", fn_name)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv or argv[0] != "run":
        print("Usage: python -m schedule_app.app.tasks run")
        return 2
    logging.basicConfig(level=logging.INFO)
    _run_app_tasks()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
