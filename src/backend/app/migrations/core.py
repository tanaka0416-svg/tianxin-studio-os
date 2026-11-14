from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from alembic import command
from alembic.config import Config


LEGACY_REVISION = "0001_legacy_baseline"
CURRENT_REVISION = "0002_task_metadata"
LEGACY_TASK_COLUMNS = ("id", "title", "status", "created_at", "updated_at")
TASK_COLUMNS = LEGACY_TASK_COLUMNS + (
    "description",
    "department",
    "assigned_ai",
    "priority",
    "due_date",
)
REDACTION_COLUMNS = (
    "id",
    "field_name",
    "original_length",
    "redaction_type",
    "start_position",
    "end_position",
    "created_at",
)


class MigrationError(RuntimeError):
    """Raised when a database path or schema cannot be handled safely."""


def _absolute_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise MigrationError("Database paths must be absolute.")
    path = path.resolve()
    if not path.parent.is_dir():
        raise MigrationError("The database parent directory must already exist.")
    if path.exists() and not path.is_file():
        raise MigrationError("The database path must point to a file.")
    return path


def _readonly_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[tuple, ...]:
    return tuple(connection.execute(f'PRAGMA table_info("{table}")'))


def _validate_columns(
    connection: sqlite3.Connection,
    table: str,
    expected_names: tuple[str, ...],
    expected_types: tuple[str, ...],
    required_names: frozenset[str],
) -> None:
    info = _table_columns(connection, table)
    if tuple(row[1] for row in info) != expected_names:
        raise MigrationError(f"Unsupported schema in table '{table}'.")
    if tuple(row[2].upper() for row in info) != expected_types:
        raise MigrationError(f"Unsupported column types in table '{table}'.")
    for row in info:
        name, not_null, primary_key = row[1], bool(row[3]), bool(row[5])
        if (name in required_names) != not_null:
            raise MigrationError(f"Unsupported nullability in table '{table}'.")
        if primary_key != (name == "id"):
            raise MigrationError(f"Unsupported primary key in table '{table}'.")


def _validate_task_schema(connection: sqlite3.Connection, current: bool) -> None:
    expected_names = TASK_COLUMNS if current else LEGACY_TASK_COLUMNS
    expected_types = (
        ("VARCHAR(36)", "VARCHAR", "VARCHAR(20)", "DATETIME", "DATETIME")
        + (("TEXT", "TEXT", "TEXT", "TEXT", "DATE") if current else ())
    )
    required = frozenset(("id", "title", "status", "created_at", "updated_at"))
    if current:
        required = required | {"priority"}
    _validate_columns(
        connection,
        "tasks",
        expected_names,
        expected_types,
        required,
    )
    create_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
    ).fetchone()[0].lower()
    if "check" not in create_sql or any(
        status.lower() not in create_sql
        for status in ("TODO", "IN_PROGRESS", "REVIEW", "BLOCKED", "RETURNED", "DONE")
    ):
        raise MigrationError("Unsupported task status constraint.")
    if current:
        priority_default = _table_columns(connection, "tasks")[8][4]
        if priority_default != "'MEDIUM'":
            raise MigrationError("Unsupported priority default in table 'tasks'.")


def _validate_redaction_schema(connection: sqlite3.Connection) -> None:
    _validate_columns(
        connection,
        "redaction_events",
        REDACTION_COLUMNS,
        ("VARCHAR(36)", "VARCHAR(32)", "INTEGER", "VARCHAR(32)", "INTEGER", "INTEGER", "DATETIME"),
        frozenset(REDACTION_COLUMNS),
    )


def _inspect_database(path: Path) -> str:
    try:
        with closing(_readonly_connection(path)) as connection:
            tables = _table_names(connection)
            if not tables:
                return "empty"

            versioned = "alembic_version" in tables
            expected_tables = {"tasks", "redaction_events"}
            if versioned:
                expected_tables.add("alembic_version")
            if tables != expected_tables:
                raise MigrationError("Unsupported database schema: unexpected tables.")

            if versioned:
                version_columns = _table_columns(connection, "alembic_version")
                if tuple(row[1] for row in version_columns) != ("version_num",):
                    raise MigrationError("Unsupported Alembic version table.")
                versions = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchall()
                if len(versions) != 1:
                    raise MigrationError("Unsupported Alembic revision state.")
                revision = versions[0][0]
                if revision == LEGACY_REVISION:
                    current = False
                elif revision == CURRENT_REVISION:
                    current = True
                else:
                    raise MigrationError("Unknown Alembic revision.")
            else:
                current = False

            _validate_task_schema(connection, current=current)
            _validate_redaction_schema(connection)
            return "versioned" if versioned else "legacy"
    except MigrationError:
        raise
    except sqlite3.Error as error:
        raise MigrationError("The specified file is not a readable SQLite database.") from error


def _alembic_config(path: Path) -> Config:
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    config.attributes["database_path"] = path
    return config


def upgrade_database(database_path: str | Path) -> None:
    """Upgrade only the required absolute path; never consult app defaults or env vars."""
    path = _absolute_path(database_path)
    if not path.exists():
        try:
            sqlite3.connect(path).close()
        except sqlite3.Error as error:
            raise MigrationError("Could not create the explicitly specified SQLite file.") from error

    state = _inspect_database(path)
    config = _alembic_config(path)
    try:
        if state == "legacy":
            command.stamp(config, LEGACY_REVISION)
        command.upgrade(config, "head")
        if _inspect_database(path) != "versioned":
            raise MigrationError("Migration did not produce a recognized schema.")
    except MigrationError:
        raise
    except Exception as error:
        raise MigrationError(
            "Migration failed. Stop and preserve the database; recover only from a verified backup."
        ) from error


def _require_existing_sqlite(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise MigrationError("The specified SQLite file does not exist.")
    try:
        with closing(_readonly_connection(path)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise MigrationError("The specified SQLite file failed its integrity check.")
    except sqlite3.Error as error:
        raise MigrationError("The specified file is not a valid SQLite database.") from error


def backup_database(source_path: str | Path, backup_path: str | Path) -> None:
    """Create a new backup at an explicit path using SQLite's online backup API."""
    source = _absolute_path(source_path)
    backup = _absolute_path(backup_path)
    if source == backup:
        raise MigrationError("Source and backup paths must differ.")
    if backup.exists():
        raise MigrationError("Backup destination already exists; refusing to overwrite it.")
    _require_existing_sqlite(source)
    try:
        with closing(_readonly_connection(source)) as source_connection:
            with closing(sqlite3.connect(backup)) as backup_connection:
                source_connection.backup(backup_connection)
        _require_existing_sqlite(backup)
    except MigrationError:
        raise
    except sqlite3.Error as error:
        raise MigrationError("SQLite backup failed.") from error


def restore_database(backup_path: str | Path, database_path: str | Path) -> None:
    """Restore an explicit, stopped SQLite target from a verified backup."""
    backup = _absolute_path(backup_path)
    target = _absolute_path(database_path)
    if backup == target:
        raise MigrationError("Backup and restore target paths must differ.")
    if not target.exists():
        raise MigrationError("Restore target must exist; refusing to create an implicit target.")
    if Path(f"{target}-wal").exists() or Path(f"{target}-shm").exists():
        raise MigrationError("Stop all database users and resolve SQLite sidecars before restore.")
    _require_existing_sqlite(backup)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.restore-", suffix=".sqlite3", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(_readonly_connection(backup)) as source_connection:
            with closing(sqlite3.connect(temporary)) as temporary_connection:
                source_connection.backup(temporary_connection)
        _require_existing_sqlite(temporary)
        with closing(_readonly_connection(temporary)) as source_connection:
            with closing(sqlite3.connect(target)) as target_connection:
                source_connection.backup(target_connection)
        _require_existing_sqlite(target)
    except Exception as error:
        if isinstance(error, MigrationError):
            raise
        raise MigrationError("SQLite restore failed; preserve the target and verified backup.") from error
    finally:
        temporary.unlink(missing_ok=True)
