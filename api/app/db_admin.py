"""Explicit SQLite migrations; production callers must stop API before changing schema."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3

from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.migrations import BASELINE, head_revision, migration_config, require_schema_at_revision
from app.sqlite_backup import backup_database, check_integrity, readonly, restore_backup


def database_path(url):
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite" or parsed.query or not parsed.database or parsed.database == ":memory:":
        raise ValueError("This command requires a file-backed SQLite DATABASE_URL without URI options")
    path = Path(parsed.database).absolute()
    if path.is_symlink():
        raise ValueError("Database symlinks must be reviewed before migration")
    return path.resolve()


def migrate_database(url, backup_dir, adopt_existing=False):
    path = database_path(url)
    if not path.parent.is_dir():
        raise ValueError("Database directory does not exist")
    engine = create_engine(make_url(url), poolclass=NullPool, connect_args={"timeout": 30})
    backup = None
    try:
        with engine.connect() as connection:
            # A real SQLite transaction makes DDL rollbackable and excludes other writers.
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                config = migration_config(connection)
                scripts = ScriptDirectory.from_config(config)
                head = scripts.get_current_head()
                current = MigrationContext.configure(connection).get_current_heads()
                tables = set(inspect(connection).get_table_names()) - {"alembic_version"}
                if len(current) > 1:
                    raise ValueError("Multiple database heads require manual review")
                previous = current[0] if current else None
                if previous:
                    scripts.get_revision(previous)
                    # Reject a database from another migration branch before making any change.
                    list(scripts.iterate_revisions(head, previous))
                    require_schema_at_revision(connection, previous)
                elif tables:
                    if not adopt_existing:
                        raise ValueError("Existing unversioned database: use --adopt-existing after reviewing the schema")
                    require_schema_at_revision(connection, BASELINE)
                check_integrity(connection.connection.driver_connection)
                if previous == head:
                    connection.rollback()
                    return {"revision": head, "changed": False, "backup": None, "adopted": False}
                # A separate read-only connection sees the committed pre-migration state.
                # The BEGIN IMMEDIATE above prevents writes between snapshot and migration.
                if path.is_file() and path.stat().st_size:
                    backup = backup_database(path, backup_dir, label="before-migration")
                if not previous and tables:
                    command.stamp(config, BASELINE)
                command.upgrade(config, "head")
                require_schema_at_revision(connection, head)
                check_integrity(connection.connection.driver_connection)
                connection.commit()
                return {"revision": head, "changed": True, "backup": str(backup) if backup else None,
                        "adopted": bool(not previous and tables)}
            except BaseException:
                connection.rollback()
                raise
    finally:
        engine.dispose()


def database_status(url):
    path = database_path(url)
    with closing(readonly(path)) as raw:
        check_integrity(raw)
    engine = create_engine("sqlite://", creator=lambda: readonly(path), poolclass=NullPool)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_heads()
            head = head_revision()
            result = {"revision": list(current), "head": head, "ready": current == (head,)}
            require_schema_at_revision(connection, current[0] if len(current) == 1 else BASELINE)
            return result
    finally:
        engine.dispose()


def require_baseline_only():
    if head_revision() != BASELINE:
        raise ValueError("This one-time operation requires the baseline to be the migration head")


def data_fingerprint(path):
    """Hash the SQLite values, including BLOB bytes, without printing private data."""
    result = hashlib.sha256()
    with closing(readonly(path)) as connection:
        connection.execute("BEGIN")
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version' ORDER BY name"
        ).fetchall()
        for (table,) in tables:
            encoded = table.encode("utf-8")
            result.update(len(encoded).to_bytes(8, "big") + encoded)
            quoted = '"' + table.replace('"', '""') + '"'
            for row in connection.execute("SELECT * FROM " + quoted + " ORDER BY rowid"):
                encoded = repr(tuple(row)).encode("utf-8")
                result.update(len(encoded).to_bytes(8, "big") + encoded)
    return result.hexdigest()


def rehearse_baseline(url, backup_dir, work_dir):
    require_baseline_only()
    source = database_path(url)
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    snapshot = backup_database(source, backup_dir, label="baseline-rehearsal")
    restored = work_dir / ("baseline-check-" + secrets.token_hex(8) + ".sqlite3")
    restore_backup(snapshot, restored)
    before = data_fingerprint(restored)
    restored_url = "sqlite:///" + restored.as_posix()
    result = migrate_database(restored_url, backup_dir, adopt_existing=True)
    if data_fingerprint(restored) != before:
        raise ValueError("Rehearsal changed original data; do not migrate the live database")
    if not database_status(restored_url)["ready"]:
        raise ValueError("Rehearsal database did not reach the current revision")
    return {"revision": result["revision"], "snapshot": str(snapshot), "rehearsal_database": str(restored),
            "original_rows_and_blobs_preserved": True, "source_opened_readonly": True}


def main():
    from app.config import settings

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate")
    migrate.add_argument("--backup-dir", type=Path, required=True)
    migrate.add_argument("--adopt-existing", action="store_true")
    migrate.add_argument("--baseline-only", action="store_true")
    rehearse = commands.add_parser("rehearse-baseline")
    rehearse.add_argument("--backup-dir", type=Path, required=True)
    rehearse.add_argument("--work-dir", type=Path, required=True)
    commands.add_parser("status")
    commands.add_parser("check")
    args = parser.parse_args()
    try:
        if args.command == "migrate":
            if args.baseline_only:
                require_baseline_only()
            result = migrate_database(settings.database_url, args.backup_dir, args.adopt_existing)
        elif args.command == "rehearse-baseline":
            result = rehearse_baseline(settings.database_url, args.backup_dir, args.work_dir)
        else:
            result = database_status(settings.database_url)
            if args.command == "check" and not result["ready"]:
                raise ValueError("Database is not at the current migration head")
    except (ValueError, OSError, sqlite3.Error, RuntimeError, CommandError, SQLAlchemyError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
