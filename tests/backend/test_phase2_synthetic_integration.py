import sqlite3

from fastapi.testclient import TestClient

from app.main import create_app
from app.migrations import backup_database
from app.migrations.cli import main as migration_main
from app.migrations import restore_database


STATUSES = ("TODO", "IN_PROGRESS", "REVIEW", "BLOCKED", "RETURNED", "DONE")


def _create_phase_one_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE tasks (
                id VARCHAR(36) NOT NULL,
                title VARCHAR NOT NULL,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CONSTRAINT ck_tasks_status CHECK (
                    status IN ('TODO', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'RETURNED', 'DONE')
                ),
                PRIMARY KEY (id)
            );
            CREATE TABLE redaction_events (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                field_name VARCHAR(32) NOT NULL,
                original_length INTEGER NOT NULL,
                redaction_type VARCHAR(32) NOT NULL,
                start_position INTEGER NOT NULL,
                end_position INTEGER NOT NULL,
                created_at DATETIME NOT NULL
            );
            """
        )
        for index, status in enumerate(STATUSES):
            timestamp = f"2026-11-14T0{index}:00:00+00:00"
            connection.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (f"legacy-{index}", f"合成舊任務-{index}", status, timestamp, timestamp),
            )
        connection.execute(
            "INSERT INTO redaction_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "legacy-event",
                "title",
                20,
                "EMAIL",
                4,
                20,
                "2026-11-14T00:00:00+00:00",
            ),
        )


def _rows(path, query):
    with sqlite3.connect(path) as connection:
        return connection.execute(query).fetchall()


def test_phase_two_synthetic_backup_upgrade_api_and_restore(tmp_path, caplog):
    database = (tmp_path / "phase-one-synthetic.sqlite3").resolve()
    backup = (tmp_path / "verified-phase-one-backup.sqlite3").resolve()
    _create_phase_one_database(database)
    original_tasks = _rows(
        database,
        "SELECT id, title, status, created_at, updated_at FROM tasks ORDER BY id",
    )
    original_events = _rows(database, "SELECT * FROM redaction_events ORDER BY id")

    backup_database(database, backup)
    assert _rows(backup, "PRAGMA integrity_check") == [("ok",)]
    assert {row[0] for row in _rows(backup, "SELECT status FROM tasks")} == set(STATUSES)

    assert migration_main(["upgrade", "--database-path", str(database)]) == 0
    assert _rows(database, "PRAGMA integrity_check") == [("ok",)]
    assert _rows(
        database,
        "SELECT id, title, status, created_at, updated_at FROM tasks ORDER BY id",
    ) == original_tasks
    assert _rows(database, "SELECT * FROM redaction_events ORDER BY id") == original_events
    assert _rows(
        database,
        "SELECT COUNT(*) FROM tasks WHERE priority <> 'MEDIUM' OR description IS NOT NULL "
        "OR department IS NOT NULL OR assigned_ai IS NOT NULL OR due_date IS NOT NULL",
    ) == [(0,)]

    app = create_app(f"sqlite:///{database.as_posix()}")
    sensitive_email = "synthetic@example.invalid"
    sensitive_phone = "0912345678"
    with TestClient(app) as client, caplog.at_level("DEBUG", logger="app"):
        legacy_response = client.get("/api/tasks")
        assert legacy_response.status_code == 200
        legacy_tasks = legacy_response.json()
        assert {task["status"] for task in legacy_tasks} == set(STATUSES)
        assert all(
            task["priority"] == "MEDIUM" and task["description"] is None
            for task in legacy_tasks
        )

        default_response = client.post(
            "/api/tasks", json={"title": "整合預設值合成任務"}
        )
        assert default_response.status_code == 201
        default_task = default_response.json()
        assert default_task["status"] == "TODO"
        assert default_task["priority"] == "MEDIUM"
        assert default_task["department"] is None
        assert default_task["assigned_ai"] is None
        assert default_task["due_date"] is None

        create_response = client.post(
            "/api/tasks",
            json={
                "title": f"整合聯絡 {sensitive_email}",
                "description": f"合成電話 {sensitive_phone}",
                "department": "DEVELOPMENT",
                "assigned_ai": "CODEX",
                "priority": "HIGH",
                "due_date": "2026-12-20",
            },
        )
        assert create_response.status_code == 201
        task = create_response.json()
        assert task["title"] == "整合聯絡 [REDACTED_EMAIL]"
        assert task["description"] == "合成電話 [REDACTED_PHONE]"
        assert task["status"] == "TODO"
        assert task["priority"] == "HIGH"
        assert task["due_date"] == "2026-12-20"

        filtered = client.get(
            "/api/tasks",
            params={
                "department": "DEVELOPMENT",
                "assigned_ai": "CODEX",
                "priority": "HIGH",
            },
        )
        assert filtered.status_code == 200
        assert [item["id"] for item in filtered.json()] == [task["id"]]

        changed = client.patch(
            f"/api/tasks/{task['id']}/status", json={"status": "IN_PROGRESS"}
        )
        assert changed.status_code == 200
        assert changed.json()["status"] == "IN_PROGRESS"
        status_filtered = client.get(
            "/api/tasks",
            params={"status": "IN_PROGRESS", "sort_by": "due_date", "order": "asc"},
        )
        assert task["id"] in [item["id"] for item in status_filtered.json()]

        sorted_tasks = client.get(
            "/api/tasks", params={"sort_by": "due_date", "order": "asc"}
        ).json()
        assert sorted_tasks[-1]["due_date"] is None
        assert any(item["due_date"] == "2026-12-20" for item in sorted_tasks)

    assert sensitive_email not in caplog.text
    assert sensitive_phone not in caplog.text
    task_text = str(_rows(database, "SELECT title, description FROM tasks"))
    event_metadata = str(
        _rows(
            database,
            "SELECT field_name, original_length, redaction_type, start_position, end_position "
            "FROM redaction_events",
        )
    )
    assert sensitive_email not in task_text + event_metadata
    assert sensitive_phone not in task_text + event_metadata

    restore_database(backup, database)
    assert _rows(database, "PRAGMA integrity_check") == [("ok",)]
    tables = {
        row[0]
        for row in _rows(
            database,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        )
    }
    assert tables == {"tasks", "redaction_events"}
    assert _rows(
        database,
        "SELECT id, title, status, created_at, updated_at FROM tasks ORDER BY id",
    ) == original_tasks
    assert _rows(database, "SELECT * FROM redaction_events ORDER BY id") == original_events
