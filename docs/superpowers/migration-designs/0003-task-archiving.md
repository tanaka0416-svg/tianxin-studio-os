# Migration Design: `0003_task_archiving`

## Status and gate

Design only. This file does not authorize a formal migration. A fresh backup was reported complete and its path, size, and SHA-256 were independently verified in this preparation phase. A separate CEO approval is still required before running any migration against the formal database.

## Pre-migration backup evidence

- Source path: `D:\tianxin-studio-os\.task-center\tasks.sqlite3` (source contents were not read).
- Backup path: `D:\tianxin-studio-backups\F002-B-pre-migration\tasks-pre-f002-b-20261115-170832.sqlite3`.
- Size: `28,672` bytes; verified non-zero.
- SHA-256: `9EBEE02A40A84E27E8CBDF1053B4A9D5AC5A2543C218AAEC6F69F7B19AC110B5`.
- CEO reports the backend/frontend processes were stopped and ports 8000/5173 released before copy. This preparation phase verified the backup file metadata and hash only; it did not inspect database contents or independently re-check process state.

## Revision

- `revision = "0003_task_archiving"`
- `down_revision = "0002_task_metadata"`
- No branch labels or dependencies.

## Upgrade design

Add one column to `tasks`:

| Name | SQLAlchemy type | Nullable | Default | Index |
|---|---|---:|---|---|
| `archived_at` | `DateTime(timezone=True)` | Yes | `NULL` | None |

Existing rows remain active because the new nullable column reads as `NULL`. New tasks also default to `NULL`. The archive API writes a UTC timestamp; normal list queries include only rows where `archived_at IS NULL`.

No task data, existing status values, or `redaction_events` rows are transformed. No `task_archive_events` table is added.

## Downgrade and recovery

Do not execute downgrade. Match the repository migration policy: automatic downgrade is disabled. If rollback is approved after a formal upgrade, use the newly created and verified backup under an explicit recovery plan. Restoring a backup can discard writes made after that backup; stop and preserve the database until the impact is reviewed.

## Synthetic test design

Use only a pytest `tmp_path` SQLite file. Upgrade it through the normal explicit-path migration API and verify:

1. Existing synthetic tasks remain intact and get `archived_at IS NULL`.
2. The column is nullable and has no non-NULL default or index.
3. New ORM tasks default to `None`.
4. Existing task fields and `redaction_events` schema remain unchanged.
5. No test invokes the formal database path or executes downgrade.
