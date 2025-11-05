# schedule-manager

## Scheduler jobs (how to add a job)

This project runs background scheduled jobs using APScheduler. Jobs live in `schedule_app/app/jobs.py`.

To make a function auto-registered by the scheduler, add the `@job(...)` decorator and provide scheduling metadata. Example:

```python
from schedule_app.app.jobs import job

@job(schedule="interval", minutes=15, id="cleanup_old_events")
def cleanup_old_events():
# cleanup code here
pass
```

Supported interval kwargs: `weeks`, `days`, `hours`, `minutes`, `seconds`.

The scheduler will automatically discover functions in `schedule_app.app.jobs` that have been decorated with `@job` and register them. Each job is executed inside a Flask `app.app_context()` so it's safe to use `current_app`, the database session, and other Flask extensions.

Local testing

Run the scheduler locally (blocking process) to verify job registration and logs:

```powershell
& .venv\Scripts\Activate.ps1
python -c "from schedule_app.app.scheduler import run; run()"
```

Check logs (scheduler logs to `/tmp/scheduler.log` by default inside container) or the terminal output.

Kubernetes / deployment

The CronJob/runner executes the scheduler runner function directly. If you change job definitions, redeploy the image and apply the k8s manifests (see `k8s/schedule-manager`).

When adding new jobs, prefer small, idempotent functions and include error handling; long-running or blocking jobs should be moved to separate workers or run in their own process.
