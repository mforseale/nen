"""Migration configuration and conservative schema checks for SQLite."""

from pathlib import Path
import re

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect


BASELINE = "20261019_0001"
API_ROOT = Path(__file__).resolve().parents[1]


def migration_config(connection=None):
    config = Config(str(API_ROOT / "alembic.ini"))
    config.attributes["skip_logging"] = True
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def head_revision():
    return ScriptDirectory.from_config(migration_config()).get_current_head()


def require_current_revision(connection):
    current = MigrationContext.configure(connection).get_current_heads()
    if current != (head_revision(),):
        raise RuntimeError(
            "Database migration required. Run python -m app.db_admin migrate "
            "--backup-dir <directory>; existing unversioned databases also need --adopt-existing."
        )


def _sql(value):
    return re.sub(r"\s+", " ", str(value).strip()) if value is not None else None


def schema_signature(connection):
    inspector = inspect(connection)
    result = {}
    for table in sorted(set(inspector.get_table_names()) - {"alembic_version"}):
        foreign_keys = [
            (tuple(fk["constrained_columns"]), fk["referred_table"],
             tuple(fk["referred_columns"]), fk.get("referred_schema"),
             tuple(sorted(fk.get("options", {}).items())))
            for fk in inspector.get_foreign_keys(table)
        ]
        indexes = [
            (index["name"], tuple(index["column_names"]), bool(index["unique"]),
             tuple(sorted((key, _sql(value)) for key, value in index.get("dialect_options", {}).items())))
            for index in inspector.get_indexes(table)
        ]
        result[table] = {
            "columns": [(column["name"], str(column["type"]), column["nullable"],
                         _sql(column.get("default")), _sql(column.get("computed")))
                        for column in inspector.get_columns(table)],
            "primary_key": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
            "foreign_keys": sorted(foreign_keys, key=repr),
            "unique": sorted(tuple(item["column_names"]) for item in inspector.get_unique_constraints(table)),
            "checks": sorted(_sql(item["sqltext"]) for item in inspector.get_check_constraints(table)),
            "indexes": sorted(indexes, key=repr),
        }
    # Inspector skips some expression indexes; their extra names must still be detected.
    result["__explicit_index_names__"] = connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name"
    ).scalars().all()
    result["__views_and_triggers__"] = connection.exec_driver_sql(
        "SELECT type, name, sql FROM sqlite_master WHERE type IN ('view', 'trigger') ORDER BY type, name"
    ).fetchall()
    return result


def require_schema_at_revision(connection, revision):
    reference = create_engine("sqlite://")
    try:
        with reference.begin() as expected:
            command.upgrade(migration_config(expected), revision)
            expected_schema = schema_signature(expected)
        actual_schema = schema_signature(connection)
        if actual_schema != expected_schema:
            differences = sorted(
                key for key in set(actual_schema) | set(expected_schema)
                if actual_schema.get(key) != expected_schema.get(key)
            )
            raise ValueError("Schema does not match revision " + revision + ": " + ", ".join(differences))
    finally:
        reference.dispose()
