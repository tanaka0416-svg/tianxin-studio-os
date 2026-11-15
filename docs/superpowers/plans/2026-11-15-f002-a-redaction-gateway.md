# F002-A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Strengthen the existing task text redaction gate so uncertain candidates require an explicit CEO decision before task creation.

**Architecture:** Keep one redaction service. It will re-analyze submitted text, validate candidate decisions against exact field offsets, apply chosen placeholders on the server, and record only event metadata. The existing task form will display candidate type/location, collect a choice, and resubmit the retained draft; keeping original text requires a separate confirmation control.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest, React, TypeScript, Vitest.

**Spec:** `specs/F002-A-redaction-interception.md`

## Global Constraints

- Only `title` and `description` enter the gateway; blank descriptions remain `null`.
- Existing trusted automatic rules remain unchanged.
- Interception responses, logs, and events must not contain candidate source text.
- No schema changes, `task_id`, migrations, dependencies, service startup, or out-of-scope F002-B/F002-C work.
- CEO confirmation is required before keeping a candidate's original text.

## Review Focus

- Multiple candidates across both fields: every candidate needs exactly one decision and no overlapping replacement.
- Stale or forged field offsets/actions: reject safely without creating a task or echoing request text.
- A keep-original decision without explicit confirmation: reject and record no task.
- Candidate positions after automatic masking: offsets remain measured against the submitted source and output replacements are deterministic.
- Error/interception and success event records: contain only metadata and do not log source values.

---

### Task 1: Redaction decision model and gate behavior

**Files:**
- Modify: `src/backend/app/services/redaction_gate.py`
- Modify: `tests/backend/test_redaction_gate.py`

**Interfaces:**
- Produces candidate metadata with `field_name`, `start_position`, `end_position`, and `suspected_type`.
- Accepts validated decisions using exact field and source offsets; returns sanitized text plus metadata records or raises the existing fail-closed exception for unresolved candidates.

- [x] Add tests for non-sensitive no-op, empty input, candidate offsets, each supported replacement, preserved text only after confirmation, and overlap/stale decisions.
- [x] Run the focused redaction test and observe the expected failure.
- [x] Implement decision validation and replacement in the existing gateway module.
- [x] Run the focused redaction test to green.

### Task 2: API interception and event recording

**Files:**
- Modify: `src/backend/app/schemas/task.py`
- Modify: `src/backend/app/routes/tasks.py`
- Modify: `tests/backend/test_tasks_api.py`

**Interfaces:**
- `TaskCreate` accepts an optional list of decisions with field, offsets, selected action, and keep-confirmation flag.
- `POST /api/tasks` returns a structured `422` candidate detail without source values; complete valid choices create a task and save existing-schema event metadata.

- [x] Add API tests for structured interception, every masking choice, confirmed/unconfirmed keep-original, incomplete/stale decisions, no task on interception, and event metadata.
- [x] Run the focused API tests and observe the expected failures.
- [x] Implement request validation, safe response shape, and transactional task/event persistence without changing schema.
- [x] Run the focused API tests to green.

### Task 3: CEO decision UI

**Files:**
- Modify: `src/frontend/src/App.tsx`
- Modify: `src/frontend/src/App.test.tsx`

**Interfaces:**
- Form state retains the original title/description and candidate metadata only after structured `422`.
- Each candidate gets one fixed-option select; keep-original requires a separate explicit confirmation control. The next submit includes decisions, never candidate text in status messages.

- [x] Add UI tests for candidate location/type/options, all decisions required, explicit keep confirmation, cancellation/edit invalidation, and successful resubmission.
- [x] Run the focused frontend tests and observe the expected failures.
- [x] Implement accessible candidate controls and decision resubmission.
- [x] Run focused frontend tests to green.

### Task 4: Regression verification and closeout

**Files:**
- Modify: `docs/acceptance-record.md`
- Modify: `CHANGELOG.md`

- [x] Record that schema and migrations were unchanged; distinguish automated results from CEO local acceptance, which remains pending until CEO performs it.
- [x] Run `python -m pytest tests/backend/test_redaction_gate.py tests/backend/test_tasks_api.py` from repo root.
- [x] Run `python -m pytest` from repo root.
- [x] Run `npm test -- --run`, `npx tsc --noEmit`, and `npm run build` from `src/frontend`.
- [x] Run `git diff --check` from repo root and inspect the staged file list to ensure existing untracked evidence is excluded.
- [x] Commit the F002-A files locally; do not push.

## Completion Contract

All specified automated commands have fresh successful output, the implementation changes no database schema, no task is written before a valid decision, no source candidate appears in response/log/event metadata, and the commit excludes the existing untracked acceptance evidence and handoff README. CEO manual browser acceptance is reported separately and remains pending until supplied.
