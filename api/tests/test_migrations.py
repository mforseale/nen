import json
import io
from contextlib import closing, redirect_stderr
from datetime import datetime, timezone
import os
import re
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import CheckConstraint, MetaData, create_engine, inspect

from app.database import Base
from app.db_admin import database_path, database_status, migrate_database, rehearse_baseline
from app.migrations import API_ROOT, BASELINE, head_revision, migration_config, require_schema_at_revision
from app.sqlite_backup import backup_database, digest, restore_backup, verify_backup
from test_persistence import isolated_app


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nen-migration-")
        self.root = Path(self.temporary.name)
        self.path = self.root / "pact.sqlite3"
        self.url = "sqlite:///" + self.path.as_posix()
        self.backups = self.root / "backups"

    def tearDown(self):
        self.temporary.cleanup()

    def legacy(self):
        engine = create_engine(self.url)
        with engine.begin() as connection:
            command.upgrade(migration_config(connection), BASELINE)
            connection.exec_driver_sql("DROP TABLE alembic_version")
        engine.dispose()

    def test_empty_database_migrates_matches_models_and_repeat_is_idempotent(self):
        result = migrate_database(self.url, self.backups)
        self.assertEqual(result, {"revision": head_revision(), "changed": True, "backup": None, "adopted": False})
        engine = create_engine(self.url)
        try:
            with engine.connect() as connection:
                self.assertEqual(compare_metadata(MigrationContext.configure(connection), Base.metadata), [])
                require_schema_at_revision(connection, head_revision())
        finally:
            engine.dispose()
        before = digest(self.path)
        self.assertFalse(migrate_database(self.url, self.backups)["changed"])
        self.assertEqual(digest(self.path), before)
        self.assertTrue(database_status(self.url)["ready"])

    def test_unversioned_schema_requires_explicit_adoption_without_mutating_data(self):
        self.legacy()
        before = digest(self.path)
        with self.assertRaisesRegex(ValueError, "adopt-existing"):
            migrate_database(self.url, self.backups)
        self.assertEqual(digest(self.path), before)
        self.assertFalse(database_status(self.url)["ready"])
        self.assertFalse(self.backups.exists())

    def test_adopt_backup_restore_preserve_login_pact_progress_and_binary_attachment(self):
        migrate_database(self.url, self.backups)
        engine = create_engine(self.url)
        try:
            with TestClient(isolated_app(engine)) as client:
                response = client.post("/api/v1/auth/register", json={"username": "migration", "full_name": "Migration user", "email": "migration@example.test", "password": "test-password-123"})
                self.assertEqual(response.status_code, 201, response.text)
                token = client.cookies.get("nen_session")
                response = client.post("/api/v1/my/pacts", json={"title": "Keep progress", "description": "Practice every day", "rarity": "common"})
                self.assertEqual(response.status_code, 201, response.text)
                pact = response.json()
                self.assertEqual(client.post(f"/api/v1/my/pacts/{pact['id']}/checkin", json={"day": datetime.now(timezone.utc).date().isoformat()}).status_code, 200)
                post = client.post("/api/v1/my/feed", data={"payload": json.dumps({"content": "Keep my post", "pin_new": True})}, files=[("files", ("important.bin", b"\x00original-file\xff", "application/octet-stream"))])
                self.assertEqual(post.status_code, 201, post.text)
                asset = post.json()["attachments"][0]
        finally:
            engine.dispose()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for table in ("profile_details", "profile_post_likes", "profile_post_comments", "pact_breaks", "pact_tracking"):
                connection.execute("DROP TABLE " + table)
            connection.execute("DELETE FROM alembic_version")
        result = migrate_database(self.url, self.backups, adopt_existing=True)
        self.assertTrue(result["adopted"])
        backup = Path(result["backup"])
        verify_backup(backup)
        restored = self.root / "restored.sqlite3"
        restore_backup(backup, restored)
        restored_url = "sqlite:///" + restored.as_posix()
        self.assertFalse(database_status(restored_url)["ready"])
        migrate_database(restored_url, self.backups, adopt_existing=True)
        for url in (self.url, restored_url):
            engine = create_engine(url)
            try:
                with TestClient(isolated_app(engine)) as client:
                    client.cookies.set("nen_session", token)
                    self.assertEqual(client.get("/api/v1/auth/me").json()["username"], "migration")
                    self.assertEqual(client.get("/api/v1/my/pacts").json()[0]["id"], pact["id"])
                    self.assertEqual(len(client.get("/api/v1/my/pacts").json()[0]["checkins"]), 1)
                    self.assertEqual(client.get(asset["url"]).content, b"\x00original-file\xff")
                    self.assertTrue(client.get("/api/v1/my/files").json()[0]["pinned"])
            finally:
                engine.dispose()

    def test_schema_drift_is_refused_before_stamp_or_backup(self):
        statements = [
            "ALTER TABLE users ADD COLUMN unexpected TEXT",
            "DROP INDEX ix_users_id",
            "CREATE TABLE unexpected (id INTEGER)",
            "CREATE TRIGGER unexpected AFTER INSERT ON users BEGIN SELECT 1; END",
            "CREATE INDEX unexpected ON users (lower(username))",
        ]
        for index, statement in enumerate(statements):
            with self.subTest(statement=statement):
                path = self.root / f"drift-{index}.sqlite3"
                url = "sqlite:///" + path.as_posix()
                engine = create_engine(url)
                with engine.begin() as connection:
                    command.upgrade(migration_config(connection), BASELINE)
                    connection.exec_driver_sql("DROP TABLE alembic_version")
                    connection.exec_driver_sql(statement)
                engine.dispose()
                before = digest(path)
                with self.assertRaisesRegex(ValueError, "Schema does not match"):
                    migrate_database(url, self.backups, adopt_existing=True)
                self.assertEqual(digest(path), before)
        self.assertFalse(self.backups.exists())

    def test_missing_check_constraint_is_refused(self):
        metadata = MetaData()
        reference = create_engine("sqlite://")
        with reference.begin() as connection:
            command.upgrade(migration_config(connection), BASELINE)
            metadata.reflect(connection, only=lambda name, _: name != "alembic_version")
        reference.dispose()
        friendships = metadata.tables["friendships"]
        for constraint in list(friendships.constraints):
            if isinstance(constraint, CheckConstraint):
                friendships.constraints.remove(constraint)
        engine = create_engine(self.url)
        metadata.create_all(engine)
        engine.dispose()
        with self.assertRaisesRegex(ValueError, "friendships"):
            migrate_database(self.url, self.backups, adopt_existing=True)

    def test_orphaned_foreign_key_is_refused_without_changing_schema(self):
        self.legacy()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO notes VALUES (1, 999, 'orphan', 'text', 'private', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
        before = digest(self.path)
        with self.assertRaisesRegex(ValueError, "foreign_key_check"):
            migrate_database(self.url, self.backups, adopt_existing=True)
        self.assertEqual(digest(self.path), before)

    def test_failed_migration_rolls_back_ddl_stamp_and_data_but_retains_backup(self):
        self.legacy()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO users VALUES (1, 'saved', 'saved@example.test', 'Original', CURRENT_TIMESTAMP)")
        upgrade = command.upgrade

        def failing_upgrade(config, revision, *args, **kwargs):
            connection = config.attributes["connection"]
            if connection.engine.url.database and Path(connection.engine.url.database).resolve() == self.path:
                connection.exec_driver_sql("CREATE TABLE must_rollback (id INTEGER)")
                connection.exec_driver_sql("UPDATE users SET full_name='Wrong'")
                raise RuntimeError("simulated migration failure")
            return upgrade(config, revision, *args, **kwargs)

        with patch("app.db_admin.command.upgrade", side_effect=failing_upgrade):
            with self.assertRaisesRegex(RuntimeError, "simulated migration failure"):
                migrate_database(self.url, self.backups, adopt_existing=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("SELECT full_name FROM users").fetchone(), ("Original",))
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("alembic_version", tables)
            self.assertNotIn("must_rollback", tables)
        backups = list(self.backups.glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        verify_backup(backups[0])

    def test_unknown_revision_and_drift_at_head_are_refused(self):
        migrate_database(self.url, self.backups)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE alembic_version SET version_num='unknown_revision'")
        with self.assertRaisesRegex(Exception, "revision"):
            migrate_database(self.url, self.backups)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("UPDATE alembic_version SET version_num=?", (BASELINE,))
            connection.execute("DROP INDEX ix_users_id")
        with self.assertRaisesRegex(ValueError, "Schema does not match"):
            migrate_database(self.url, self.backups)

    def test_alembic_uses_environment_url_and_absolute_config_from_another_directory(self):
        env = {**os.environ, "DATABASE_URL": self.url}
        for arguments in (("upgrade", "head"), ("check",)):
            result = subprocess.run([sys.executable, "-m", "alembic", "-c", str(API_ROOT / "alembic.ini"), *arguments], env=env, cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(database_status(self.url)["ready"])
        self.assertFalse((self.root / "pact.db").exists())

    def test_api_import_does_not_create_schema_and_start_requires_migrations(self):
        env = {**os.environ, "DATABASE_URL": self.url, "PYTHONPATH": str(API_ROOT)}
        result = subprocess.run([sys.executable, "-c", "import app.main"], env=env, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.path.exists())
        self.legacy()
        from app.main import app
        engine = create_engine(self.url)
        try:
            with patch("app.main.engine", engine):
                with self.assertRaisesRegex(RuntimeError, "migration required"):
                    with TestClient(app):
                        pass
                migrate_database(self.url, self.backups, adopt_existing=True)
                with TestClient(app) as client:
                    self.assertEqual(client.get("/api/v1/health").json(), {"status": "ok"})
        finally:
            engine.dispose()

    def test_admin_rejects_non_file_urls_and_status_never_creates_a_database(self):
        for url in ("sqlite://", "sqlite:///:memory:", "sqlite:///file:test?uri=true", "postgresql://localhost/example"):
            with self.assertRaises(ValueError):
                database_path(url)
        with self.assertRaises(ValueError):
            database_status(self.url)
        self.assertFalse(self.path.exists())

    def test_baseline_upgrade_preserves_blob_and_starts_tracking_only_at_upgrade(self):
        self.legacy()
        old_created = "2025-01-01 12:00:00"
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("INSERT INTO users VALUES (1, 'owner', 'owner@example.test', 'Original', CURRENT_TIMESTAMP)")
            connection.execute("INSERT INTO profile_avatars VALUES (1, ?, 'image/png', 'version1')", (b"\x00private-blob\xff",))
            connection.execute("INSERT INTO pacts (id,title,rarity,status,visibility,is_joint,created_at,updated_at,creator_id) VALUES (1,'Past pact','legendary','active','private',0,?,?,1)", (old_created,old_created))
            connection.execute("INSERT INTO pact_participants (id,pact_id,user_id,role,joined_at) VALUES (1,1,1,'creator',?)", (old_created,))
            connection.execute("INSERT INTO pact_checkins (id,pact_id,user_id,day) VALUES (1,1,1,'2025-01-02')")
        result = migrate_database(self.url, self.backups, adopt_existing=True)
        self.assertEqual(result["revision"], head_revision())
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT content FROM profile_avatars").fetchone(), (b"\x00private-blob\xff",))
            self.assertEqual(connection.execute("SELECT day FROM pact_checkins").fetchall(), [("2025-01-02",)])
            started = datetime.fromisoformat(connection.execute("SELECT started_at FROM pact_tracking").fetchone()[0])
            self.assertEqual(started.date(), datetime.now(timezone.utc).date())
            self.assertEqual(connection.execute("SELECT count(*) FROM pact_breaks").fetchone(), (0,))
        backup = Path(result["backup"])
        verify_backup(backup)
        with closing(sqlite3.connect(backup)) as connection:
            self.assertNotIn("pact_tracking", {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")})

    def test_versioned_baseline_upgrade_uses_backup_and_keeps_original_rows(self):
        engine = create_engine(self.url)
        with engine.begin() as connection:
            command.upgrade(migration_config(connection), BASELINE)
            connection.exec_driver_sql("INSERT INTO users VALUES (1, 'saved', 'saved@example.test', 'Original', CURRENT_TIMESTAMP)")
            connection.exec_driver_sql("INSERT INTO profile_avatars VALUES (1, X'0042FF', 'image/png', 'version1')")
        engine.dispose()
        result = migrate_database(self.url, self.backups)
        self.assertFalse(result["adopted"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["revision"], head_revision())
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT full_name FROM users").fetchone(), ("Original",))
            self.assertEqual(connection.execute("SELECT content FROM profile_avatars").fetchone(), (b"\x00B\xff",))
        with closing(sqlite3.connect(result["backup"])) as connection:
            self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), (BASELINE,))
        self.assertTrue(database_status(self.url)["ready"])

    def test_one_time_baseline_rehearsal_now_refuses_new_head_without_touching_source(self):
        self.legacy()
        original_hash = digest(self.path)
        with self.assertRaisesRegex(ValueError, "baseline"):
            rehearse_baseline(self.url, self.backups, self.root / "rehearsal")
        self.assertEqual(digest(self.path), original_hash)
        self.assertFalse(self.backups.exists())

    def test_one_time_baseline_mode_refuses_future_migrations_before_touching_database(self):
        from app.db_admin import main

        with patch("app.db_admin.head_revision", return_value="future_revision"):
            with self.assertRaisesRegex(ValueError, "baseline"):
                rehearse_baseline(self.url, self.backups, self.root / "rehearsal")
            with patch("sys.argv", ["db_admin", "migrate", "--backup-dir", str(self.backups), "--baseline-only"]):
                with patch("app.db_admin.migrate_database") as migrate, redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as failure:
                        main()
                    self.assertEqual(failure.exception.code, 1)
                    migrate.assert_not_called()
        self.assertFalse(self.path.exists())
        self.assertFalse(self.backups.exists())


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nen-backup-")
        self.root = Path(self.temporary.name)
        self.path = self.root / "live.sqlite3"
        self.backups = self.root / "backups"
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE files (id INTEGER PRIMARY KEY, content BLOB)")
            connection.execute("INSERT INTO files VALUES (1, ?)", (b"saved\x00\xff",))

    def tearDown(self):
        self.temporary.cleanup()

    def test_online_wal_backup_restores_committed_blobs_but_excludes_uncommitted_data(self):
        writer = sqlite3.connect(self.path)
        try:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("INSERT INTO files VALUES (2, ?)", (b"wal-only",))
            writer.commit()
            self.assertGreater(Path(str(self.path) + "-wal").stat().st_size, 0)
            writer.execute("INSERT INTO files VALUES (3, ?)", (b"uncommitted",))
            backup = backup_database(self.path, self.backups)
            verify_backup(backup)
            restored = restore_backup(backup, self.root / "restored.sqlite3")
            with closing(sqlite3.connect(restored)) as connection, connection:
                self.assertEqual(connection.execute("SELECT * FROM files ORDER BY id").fetchall(), [(1, b"saved\x00\xff"), (2, b"wal-only")])
        finally:
            writer.rollback()
            writer.close()

    def test_corruption_and_existing_restore_destinations_are_refused(self):
        backup = backup_database(self.path, self.backups)
        with self.assertRaisesRegex(ValueError, "new destination"):
            restore_backup(backup, self.path)
        target = self.root / "sidecar.sqlite3"
        Path(str(target) + "-wal").write_bytes(b"keep")
        with self.assertRaisesRegex(ValueError, "new destination"):
            restore_backup(backup, target)
        with backup.open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum or size"):
            restore_backup(backup, self.root / "must-not-exist.sqlite3")
        self.assertFalse((self.root / "must-not-exist.sqlite3").exists())
        self.assertEqual(Path(str(target) + "-wal").read_bytes(), b"keep")

    def test_retention_only_removes_completed_daily_pairs(self):
        manual = backup_database(self.path, self.backups)
        migration = backup_database(self.path, self.backups, label="before-migration")
        partial = self.backups / "unfinished.partial"
        partial.write_bytes(b"keep")
        for _ in range(4):
            backup_database(self.path, self.backups, label="daily", keep=2)
        self.assertEqual(len(list(self.backups.glob("nen-daily-*.sqlite3"))), 2)
        self.assertTrue(manual.exists())
        self.assertTrue(migration.exists())
        self.assertTrue(partial.exists())
        for path in self.backups.glob("*.sqlite3"):
            verify_backup(path)

    def test_failed_backup_is_not_published_and_readonly_source_is_never_created(self):
        with self.assertRaises(ValueError):
            backup_database(self.root / "missing.sqlite3", self.backups)
        self.assertFalse((self.root / "missing.sqlite3").exists())
        with self.assertRaises(TimeoutError):
            backup_database(self.path, self.backups, timeout=-1)
        self.assertEqual(list(self.backups.iterdir()), [])

    def test_standalone_cli_does_not_require_application_dependencies(self):
        script = API_ROOT / "app" / "sqlite_backup.py"
        result = subprocess.run([sys.executable, "-S", str(script), "backup", "--source", str(self.path), "--directory", str(self.backups)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        backup = json.loads(result.stdout)["backup"]
        if os.name != "nt":
            self.assertEqual(Path(backup).stat().st_mode & 0o077, 0)
            self.assertEqual(Path(backup + ".json").stat().st_mode & 0o077, 0)
        result = subprocess.run([sys.executable, "-S", str(script), "verify", "--source", backup], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["sha256"], digest(backup))


class BackupServiceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux" and shutil.which("systemd-analyze"), "systemd verification runs on Linux CI")
    def test_installer_contains_valid_backup_service_and_timer(self):
        script = (API_ROOT.parent / "scripts" / "setup-vm-backups.sh").read_text(encoding="utf-8")
        units = re.findall(r"cat > /etc/systemd/system/(nen-backup\.(?:service|timer)) <<'UNIT'\n(.*?)\nUNIT", script, re.DOTALL)
        self.assertEqual({name for name, body in units}, {"nen-backup.service", "nen-backup.timer"})
        with tempfile.TemporaryDirectory(prefix="nen-systemd-") as directory:
            paths = []
            for name, body in units:
                path = Path(directory) / name
                path.write_text(body + "\n", encoding="utf-8")
                paths.append(str(path))
            result = subprocess.run(["systemd-analyze", "verify", *paths], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
