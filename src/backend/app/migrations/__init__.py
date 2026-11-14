"""Explicit, versioned SQLite schema migrations and synthetic backup helpers."""

from app.migrations.core import (
    MigrationError,
    backup_database,
    require_current_database,
    restore_database,
    upgrade_database,
)

__all__ = [
    "MigrationError",
    "backup_database",
    "require_current_database",
    "restore_database",
    "upgrade_database",
]
