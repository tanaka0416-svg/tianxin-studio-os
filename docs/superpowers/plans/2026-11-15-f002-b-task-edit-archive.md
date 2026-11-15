# F002-B Task Edit and Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe partial task editing and reversible soft archiving while keeping the active task list and F002-A redaction guarantees intact.

**Architecture:** Reuse the current task router, Pydantic schemas, and single `redact_text` service. Add an additive nullable `archived_at` column, filter active tasks at the query boundary, reject status updates for archived tasks, and keep edits/archive operations transactional. The React task card will host a prefilled edit flow and an explicit archive confirmation, then reload the current query after success.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite, pytest, React, TypeScript, Vitest.

**Spec:** `specs/F002-B-task-edit-archive.md`

## Global Constraints

- A fresh, verified backup of `D:\tianxin-studio-os\.task-center\tasks.sqlite3` must exist before implementation or any formal migration.
- F002-B implementation has not started. Migration may be authored and tested against synthetic databases only; a separate CEO approval is required before formal upgrade.
- No task hard deletion; no archive event table, restore API/UI, archive search/marker, new dependency, or `package.json` change.
- Any submitted `title` or `description` update must pass the existing redaction gateway; unresolved candidates must not update the task.
- Never log, return, or persist candidate source text in error responses or redaction metadata.
- Active list and status update operations must treat archived tasks as absent.
- Never read work-database contents, start services, or write test tasks to the work database.

## Review Focus

- Omitted fields versus explicit null: only fields in `model_fields_set` are applied; `description: null` clears only description; null title is rejected.
- Candidate decisions after trimming/normalization: offsets are measured against exactly the submitted normalized field value and revalidated server-side.
- Mixed valid and unresolved text fields: no task field may change unless the entire patch passes validation and all decisions.
- Archive repeated after a timeout: endpoint is idempotent for an existing archived task and must not create duplicate event records.
- Status update racing with archive: archived rows must fail the active-row lookup and return 404.

---

### Task 1: Partial update schema and service tests

**Files:**
- Modify: `src/backend/app/schemas/task.py`
- Modify: `tests/backend/test_tasks_api.py`

**Interfaces:**
- Add `TaskUpdate` with optional `title`, `description`, `department`, `assigned_ai`, `priority`, and `due_date`; preserve omitted-versus-null via `model_fields_set`.
- Empty update is rejected by route validation; `status` and unknown keys are forbidden.

- [ ] Write API tests for each single-field update, omitted-field preservation, explicit-null description clearing, empty patch, null/blank title, invalid enums/date/length, and 404.
- Suggested test names: `test_patch_updates_single_field_and_preserves_omitted_fields`, `test_patch_null_description_clears_only_description`, `test_patch_rejects_empty_body_without_mutation`, `test_patch_validation_failure_does_not_change_task`, and `test_patch_missing_task_returns_404`.
- [ ] Run the focused new tests and observe expected failures against the current API.
- [ ] Implement the request schema with creation-equivalent field validation and extra-field rejection.
- [ ] Run focused schema/API tests to green.

### Task 2: Update API and F002-A gateway integration

**Files:**
- Modify: `src/backend/app/routes/tasks.py`
- Modify: `tests/backend/test_tasks_api.py`
- Reuse: `src/backend/app/services/redaction_gate.py`

**Interfaces:**
- Add `PATCH /api/tasks/{task_id}` returning `TaskRead` with HTTP 200.
- Only apply fields present in the request. Re-run `redact_text(text, field_name, decisions=...)` for each submitted title/description before mutating the ORM task.
- On any validation/interception failure, do not change the task. Successful text/event writes share one database transaction.

- [ ] Add tests for automatic redaction on update, uncertain candidate 422 with no task change, all masking choices, confirmed/unconfirmed keep-original, stale decisions, and event records without raw values.
- Suggested test names: `test_update_redacts_supported_sensitive_text_before_persistence`, `test_uncertain_update_returns_safe_422_and_preserves_task`, `test_update_candidate_decisions_apply_each_approved_marker`, `test_update_keep_original_requires_confirmation_and_records_event`, and `test_stale_or_incomplete_update_decisions_do_not_mutate_task`.
- [ ] Run new update tests and observe expected failures.
- [ ] Implement transactional partial update and safe F002-A interception/re-submission contract.
- [ ] Run focused update and gateway tests to green.

### Task 3: Archive migration and synthetic migration tests

**Files:**
- Create: `src/backend/app/migrations/versions/0003_task_archiving.py`
- Modify: `src/backend/app/models/task.py`
- Modify: `src/backend/app/migrations/core.py`
- Modify: `tests/backend/test_migrations.py`

**Interfaces:**
- Migration revision is `0003_task_archiving`, parent `0002_task_metadata`.
- Add nullable `archived_at: DateTime(timezone=True)` with implicit SQL NULL default; no index.
- Downgrade raises the existing no-automatic-downgrade error; no downgrade operation is run.

- [ ] Add synthetic migration tests proving existing rows receive NULL, new model rows default to NULL, and existing columns/data are preserved.
- Suggested test names: `test_0003_upgrade_adds_nullable_archived_at_to_existing_synthetic_tasks` and `test_task_archived_at_defaults_to_none`.
- [ ] Run only the focused synthetic migration test; never pass the work database path.
- [ ] Implement migration and model mapping; do not run upgrade on the formal database.
- [ ] Run the synthetic migration test to green and inspect its explicit temp path.

### Task 4: Active-task API behavior

**Files:**
- Modify: `src/backend/app/routes/tasks.py`
- Modify: `tests/backend/test_tasks_api.py`

**Interfaces:**
- Every `GET /api/tasks` query begins with `Task.archived_at IS NULL`, before filters and ordering.
- Add `PATCH /api/tasks/{task_id}/archive`: no body, set UTC archive time, return 204; missing ID returns 404; repeating for an already archived row returns 204.
- `PATCH /api/tasks/{task_id}/status` returns 404 for archived rows.

- [ ] Add API tests for archive/no hard delete, idempotency, active-list exclusion across each filter and sort, status-update rejection, and missing IDs.
- Suggested test names: `test_archive_sets_timestamp_without_deleting_task`, `test_archive_endpoint_is_idempotent`, `test_list_excludes_archived_tasks_before_filters_and_sorts`, and `test_status_update_rejects_archived_task`.
- [ ] Run new archive tests and observe expected failures.
- [ ] Implement archive endpoint and shared active-row lookup/filter.
- [ ] Run focused API tests to green.

### Task 5: Edit and archive UI

**Files:**
- Modify: `src/frontend/src/App.tsx`
- Modify: `src/frontend/src/styles.css`
- Modify: `src/frontend/src/App.test.tsx`

**Interfaces:**
- Each active task card exposes edit and archive controls.
- Edit state is tied to a task ID; form is prefilled and supports save/cancel. Update errors preserve the draft.
- Text interception uses the F002-A candidate/decision model; archive confirmation has explicit confirm/cancel actions and no new dependency.

- [ ] Add UI tests for edit entry/prefill, each editable field, cancel/no request, success/reload, validation and network errors.
- Suggested test names: `it opens a prefilled editor for the selected task`, `it cancels editing without sending a request`, `it saves changed fields and reloads the current query`, and `it preserves the edit draft after an update error`.
- [ ] Add UI tests for redaction interception and resubmission during edit, including confirmed keep-original.
- Suggested test names: `it holds an edit when the gateway returns uncertain candidates`, `it resubmits edit decisions with the unchanged source draft`, and `it requires keep-original confirmation during edit`.
- [ ] Add UI tests for archive confirm/cancel, success removal under current query, and failure preserving the row.
- Suggested test names: `it cancels archive without calling the API`, `it archives only after confirmation and reloads the current query`, and `it retains the task row when archive fails`.
- [ ] Run new UI tests and observe expected failures.
- [ ] Implement the focused card/editor/confirmation flow without a broad app refactor.
- [ ] Run focused UI tests to green.

### Task 6: Regression verification and CEO acceptance handoff

**Files:**
- Modify: `docs/acceptance-record.md`
- Modify: `CHANGELOG.md`

- [ ] Run from repository root: `python -m pytest tests/backend/test_redaction_gate.py tests/backend/test_tasks_api.py`.
- [ ] Run from repository root: `python -m pytest`.
- [ ] Run from repository root: `git diff --check`.
- [ ] Run from `src/frontend`: `npm test -- --run`, `npx tsc --noEmit`, and `npm run build`.
- [ ] Record whether migration was formally approved/run; distinguish synthetic tests, Codex automation, and CEO manual acceptance.
- [ ] CEO manually verifies edit, redaction review, archive confirmation, active-list exclusion, and no loading/version errors.

## Completion Contract

No formal migration occurs until a separate CEO authorization. Completion requires the verified pre-implementation backup, all fresh automated commands green, schema migration tested only against synthetic data until separately authorized, and CEO manual acceptance recorded separately. F002-B work remains local unless separately authorized for commit/merge/push.
