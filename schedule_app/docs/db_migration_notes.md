# Database migration checklist

These are the steps we need to follow whenever a new Alembic revision is added (for example the attachments migration in `versions/0013_*.py`).

1. **Local sanity check**
   - Activate the virtualenv and run `flask db upgrade` (or `alembic upgrade head`).
   - Verify the table exists:

     ```sql
     SELECT to_regclass('public.attachments');
     ```

     The query should return `attachments`.

2. **Build and publish the container**
   - Rebuild the `schedule-manager` image so it contains the new migration file.
   - Push the image to GHCR so Kubernetes can pull it.

3. **Run the Kubernetes migration job**
   - Use `kubectl -n schedule-manager delete job schedule-manager-migrate --ignore-not-found`.
   - Apply the job manifest again and wait for `kubectl logs job/schedule-manager-migrate` to show a successful `flask db upgrade`.

4. **Deploy app pods**
   - Restart the deployment: `kubectl -n schedule-manager rollout restart deployment/schedule-manager`.
   - Confirm new pods come up cleanly and event deletions no longer throw `UndefinedTable` errors.

Keep this list updated as we add more schema changes so production stays in sync with the codebase.
