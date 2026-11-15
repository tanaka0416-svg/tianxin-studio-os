import hashlib
import sqlite3

import pytest

STATUSES = ("TODO", "IN_PROGRESS", "REVIEW", "BLOCKED", "RETURNED", "DONE")
LEGACY_TASK_COLUMNS = ("id", "title", "status", "created_at", "updated_at")
LEGACY_REDACTION_COLUMNS = (
    "id",
    "field_name",
    "original_length",
    "redaction_type",
    "start_position",
    "end_position",
    "created_at",
)


def migration_api():
    try:
        from app.migrations import (
            MigrationError,
            backup_database,
            restore_database,
            upgrade_database,
        )
        from app.migrations.cli import main
    except ModuleNotFoundError:
        pytest.fail("the explicit-path migration tool has not been implemented")
    return MigrationError, backup_database, restore_database, upgrade_database, main


def create_legacy_database(path):
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
                (f"synthetic-{index}", f"synthetic task {index}", status, timestamp, timestamp),
            )
        connection.execute(
            "INSERT INTO redaction_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "synthetic-event",
                "title",
                18,
                "EMAIL",
                10,
                28,
                "2026-11-14T00:00:00+00:00",
            ),
        )


def rows(path, table):
    with sqlite3.connect(path) as connection:
        return connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()


def columns(path, table):
    with sqlite3.connect(path) as connection:
        return tuple(row[1] for row in connection.execute(f"PRAGMA table_info({table})"))


def integrity(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("PRAGMA integrity_check").fetchone()[0]


def test_upgrade_preserves_all_legacy_tasks_and_redaction_records(tmp_path):
    _, _, _, upgrade_database, _ = migration_api()
    database = tmp_path / "legacy.sqlite3"
    create_legacy_database(database)
    before_tasks = rows(database, "tasks")
    before_events = rows(database, "redaction_events")

    upgrade_database(database)

    assert columns(database, "tasks") == LEGACY_TASK_COLUMNS + (
        "description",
        "department",
        "assigned_ai",
        "priority",
        "due_date",
        "archived_at",
    )
    assert columns(database, "redaction_events") == LEGACY_REDACTION_COLUMNS
    after_tasks = rows(database, "tasks")
    assert [row[:5] for row in after_tasks] == before_tasks
    assert all(row[5:8] == (None, None, None) for row in after_tasks)
    assert all(row[8] == "MEDIUM" and row[9:] == (None, None) for row in after_tasks)
    assert rows(database, "redaction_events") == before_events
    assert {row[2] for row in after_tasks} == set(STATUSES)
    assert integrity(database) == "ok"


def test_upgrade_initializes_an_explicit_empty_database(tmp_path):
    _, _, _, _, main = migration_api()
    database = tmp_path / "empty.sqlite3"
    sqlite3.connect(database).close()

    assert main(["upgrade", "--database-path", str(database)]) == 0

    assert columns(database, "tasks") == LEGACY_TASK_COLUMNS + (
        "description",
        "department",
        "assigned_ai",
        "priority",
        "due_date",
        "archived_at",
    )
    assert columns(database, "redaction_events") == LEGACY_REDACTION_COLUMNS
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert integrity(database) == "ok"


def test_unknown_schema_is_rejected_without_changing_the_database(tmp_path):
    MigrationError, _, _, upgrade_database, _ = migration_api()
    database = tmp_path / "unknown.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT NOT NULL)")
        connection.execute("INSERT INTO unrelated VALUES ('synthetic')")
    before_hash = hashlib.sha256(database.read_bytes()).hexdigest()

    with pytest.raises(MigrationError, match="schema"):
        upgrade_database(database)

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before_hash
    assert columns(database, "unrelated") == ("value",)
    assert rows(database, "unrelated") == [("synthetic",)]


def test_repeated_upgrade_does_not_change_schema_or_data(tmp_path):
    _, _, _, upgrade_database, _ = migration_api()
    database = tmp_path / "repeat.sqlite3"
    create_legacy_database(database)

    upgrade_database(database)
    first_tasks = rows(database, "tasks")
    first_events = rows(database, "redaction_events")
    first_columns = columns(database, "tasks")
    upgrade_database(database)

    assert columns(database, "tasks") == first_columns
    assert rows(database, "tasks") == first_tasks
    assert rows(database, "redaction_events") == first_events
    assert integrity(database) == "ok"


def test_backup_restore_recovers_legacy_schema_and_every_row(tmp_path):
    _, backup_database, restore_database, upgrade_database, _ = migration_api()
    database = tmp_path / "restore-target.sqlite3"
    backup = tmp_path / "verified-backup.sqlite3"
    create_legacy_database(database)
    before_tasks = rows(database, "tasks")
    before_events = rows(database, "redaction_events")
    before_task_columns = columns(database, "tasks")
    before_event_columns = columns(database, "redaction_events")

    backup_database(database, backup)
    assert integrity(backup) == "ok"
    upgrade_database(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute("DROP TABLE tasks")
        connection.execute("CREATE TABLE tasks (wrong_schema TEXT)")
        connection.execute("INSERT INTO tasks VALUES ('synthetic damage')")
        connection.commit()
    finally:
        connection.close()

    restore_database(backup, database)

    assert columns(database, "tasks") == before_task_columns
    assert columns(database, "redaction_events") == before_event_columns
    assert rows(database, "tasks") == before_tasks
    assert rows(database, "redaction_events") == before_events
    assert {row[2] for row in rows(database, "tasks")} == set(STATUSES)
    with sqlite3.connect(database) as connection:
        restored_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert restored_tables == {"tasks", "redaction_events"}
    assert integrity(database) == "ok"


def test_cli_requires_explicit_database_path_and_ignores_database_url_env(
    tmp_path, monkeypatch
):
    _, _, _, _, main = migration_api()
    fallback_database = tmp_path / ".task-center" / "tasks.sqlite3"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TASK_CENTER_DATABASE_URL", f"sqlite:///{fallback_database}")

    with pytest.raises(SystemExit) as error:
        main(["upgrade"])

    assert error.value.code == 2
    assert not fallback_database.exists()


def test_upgrade_rejects_relative_database_paths(tmp_path):
    MigrationError, _, _, upgrade_database, _ = migration_api()
    with pytest.raises(MigrationError, match="absolute"):
        upgrade_database("relative.sqlite3")


def create_metadata_database(path):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE tasks (
                id VARCHAR(36) NOT NULL,
                title VARCHAR NOT NULL,
                status VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                description TEXT,
                department TEXT,
                assigned_ai TEXT,
                priority TEXT DEFAULT 'MEDIUM' NOT NULL,
                due_date DATE,
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
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version VALUES ('0002_task_metadata');
            INSERT INTO tasks VALUES (
                'synthetic-0002', 'synthetic task', 'TODO',
                '2026-11-15T00:00:00+00:00', '2026-11-15T00:00:00+00:00',
                'synthetic description', 'DEVELOPMENT', 'CODEX', 'HIGH', '2026-11-20'
            );
            INSERT INTO redaction_events VALUES (
                'synthetic-event', 'title', 6, 'EMAIL', 1, 7,
                '2026-11-15T00:00:00+00:00'
            );
            """
        )


def test_upgrade_0002_adds_nullable_archived_at_without_changing_synthetic_data(tmp_path):
    _, _, _, upgrade_database, _ = migration_api()
    database = tmp_path / "metadata.sqlite3"
    create_metadata_database(database)
    before_task = rows(database, "tasks")
    before_events = rows(database, "redaction_events")

    upgrade_database(database)

    assert rows(database, "tasks") == [before_task[0] + (None,)]
    assert rows(database, "redaction_events") == before_events
    task_columns = columns(database, "tasks")
    assert task_columns[-1] == "archived_at"
    with sqlite3.connect(database) as connection:
        archived_column = connection.execute(
            "PRAGMA table_info(tasks)"
        ).fetchall()[-1]
        assert archived_column[2].upper() == "DATETIME"
        assert archived_column[3] == 0
        assert archived_column[4] is None
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0] == "0003_task_archiving"
        assert not any(
            "archived_at" in index[1].lower()
            for index in connection.execute("PRAGMA index_list(tasks)")
        )
    assert integrity(database) == "ok"
