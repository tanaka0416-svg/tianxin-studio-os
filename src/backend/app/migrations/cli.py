import argparse
from pathlib import Path
import sys
from typing import Sequence

from app.migrations.core import MigrationError, upgrade_database


def _absolute_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("--database-path must be an absolute path")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit-path task-center schema migration tool")
    commands = parser.add_subparsers(dest="command", required=True)
    upgrade = commands.add_parser("upgrade", help="upgrade the explicitly specified SQLite database")
    upgrade.add_argument("--database-path", required=True, type=_absolute_path)
    args = parser.parse_args(argv)

    try:
        upgrade_database(args.database_path)
    except MigrationError as error:
        print(f"Migration stopped safely: {error}", file=sys.stderr)
        return 2
    print("Migration completed for the explicitly specified database.")
    return 0
