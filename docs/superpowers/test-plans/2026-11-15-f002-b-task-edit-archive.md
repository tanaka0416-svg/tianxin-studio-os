# F002-B Test Plan: Task Edit and Archive

## Test isolation

- API tests use `make_app(tmp_path)` and synthetic SQLite databases; never use `.task-center/tasks.sqlite3`.
- Migration tests use a separate `tmp_path` file and explicit database path.
- Frontend tests use React Testing Library, `userEvent`, and mocked `fetch`; do not start backend or Vite services.
- Do not run downgrade tests against any database. If testing the disabled downgrade function, call only the Python function and assert it raises before any schema operation.

## Schema and update API

1. Update only title; all omitted fields remain unchanged.
2. Update only description; other fields remain unchanged.
3. Explicit `description: null` stores SQL NULL; omitted description is unchanged; blank description follows existing normalization to NULL.
4. Each of department, assigned AI, priority, and due date updates independently.
5. Empty patch, title null/blank, unknown field, invalid enum, invalid date, and description over 5,000 return safe 422 and leave task values and `updated_at` unchanged.
6. Missing task returns 404 without creating redaction events.
7. `status` cannot be changed through general update; the dedicated endpoint remains the only status mutation route.

## F002-A gateway on edits

1. Recognized sensitive title and description values are automatically masked before persistence.
2. A suspected candidate returns the structured safe 422 contract and leaves every task field unchanged.
3. Complete choices for multiple candidates are server-revalidated against the submitted field and exact offsets; all eight markers work.
4. `KEEP_ORIGINAL` without confirmation is rejected; with explicit confirmation, update succeeds and writes `MANUAL_KEEP_CONFIRMED` metadata.
5. Stale, duplicated, wrong-field, or incomplete decisions cannot mutate the task.
6. Response, logs, persisted task text, and event metadata do not contain the raw candidate. Event fields contain only the existing metadata (length, type, field, positions, timestamp).
7. Non-sensitive or empty optional text remains unchanged/NULL; existing F002-A create behavior remains green.

## Migration

1. On a synthetic revision `0002_task_metadata` database, upgrade to `0003_task_archiving` and verify old rows persist with `archived_at=NULL`.
2. Verify column type/nullability/default and absence of index; verify no other table/column changes.
3. Verify new ORM Task defaults `archived_at` to `None`.
4. Never run upgrade against the formal path. Never execute downgrade.

## Archive API and list behavior

1. Archive existing task returns 204 and preserves the row and all its fields; `archived_at` is UTC and non-NULL.
2. Repeated archive is idempotent (204); unknown ID is 404.
3. Default list and every status/department/assigned-AI/priority combination exclude the archived task.
4. Every supported sort and direction excludes the archived task; active ordering and null due-date behavior remain unchanged.
5. Status update for an archived task returns 404 and does not change status or timestamps.
6. Existing six statuses, create/list, F002-A events, filters, and sorting remain covered.

## Frontend

1. Each task has edit and archive entry points; edit prepopulates all approved fields.
2. Cancel edit sends no mutation request and leaves displayed task unchanged.
3. Successful update sends only changed fields, then reloads current filters/sort; error keeps draft and does not claim success.
4. Sensitive edit follows F002-A candidate selection, masking, and keep confirmation; no update is sent until all decisions are complete.
5. Archive cancel sends no request; confirm calls archive and reloads current query; failure retains the task.
6. After successful archive, the task disappears and remains excluded after filter/sort changes and reload.
7. No restore, archive search, archive marker, or bulk action appears.

## Fresh verification commands after implementation

From repository root:

```text
python -m pytest tests/backend/test_redaction_gate.py tests/backend/test_tasks_api.py
python -m pytest
git diff --check
```

From `src/frontend`:

```text
npm test -- --run
npx tsc --noEmit
npm run build
```

These commands must be run fresh for the implementation; historical green runs do not substitute.
