"""Deployment boundary and recovery tests; no production services or data."""
import io
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy_vm import (Installation, RecoveryRequired, PROFILE_FROM, PROFILE_TO,
                       restore_transition_snapshot, table_fingerprints)
from runtime_bundle import digest, unpack


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "nen"
        for name in ("api", "web"):
            (self.root / name).mkdir(parents=True)
            (self.root / name / "version").write_text("old")
        (self.root / "api/.venv").mkdir()
        (self.root / "api/.venv/dependencies").write_text("old dependencies")
        self.installation = Installation(self.root, self.base / "previous", self.base / "unit/override.conf")
        self.candidate = self.base / "work/candidate"
        for name in ("api", "web"):
            (self.candidate / name).mkdir(parents=True)
            (self.candidate / name / "version").write_text("new")
        (self.candidate / "web/server.js").write_text("// standalone")

    def test_success_keeps_only_one_previous_including_dependencies(self):
        self.installation.previous.mkdir()
        (self.installation.previous / "previous.json").write_text("{}")
        (self.installation.previous / "obsolete").write_text("discard only on success")
        self.installation.validate()
        self.installation.switch(self.candidate, lambda: None, "baseline")
        self.assertEqual((self.root / "web/version").read_text(), "new")
        self.assertEqual((self.installation.previous / "api/.venv/dependencies").read_text(), "old dependencies")
        self.assertFalse((self.installation.previous / "obsolete").exists())
        self.assertFalse(self.installation.marker.exists())

    def test_failed_health_restores_code_dependencies_and_unit(self):
        self.installation.override.parent.mkdir()
        self.installation.override.write_text("original unit override")
        self.installation.previous.mkdir()
        (self.installation.previous / "previous.json").write_text("{}")
        (self.installation.previous / "keep").write_text("older good copy")

        def fail():
            raise RuntimeError("health failed")

        with self.assertRaisesRegex(RuntimeError, "health failed"):
            self.installation.switch(self.candidate, fail, "baseline")
        self.assertEqual((self.root / "api/version").read_text(), "old")
        self.assertEqual((self.root / "api/.venv/dependencies").read_text(), "old dependencies")
        self.assertEqual(self.installation.override.read_text(), "original unit override")
        self.assertEqual((self.installation.previous / "keep").read_text(), "older good copy")
        self.assertFalse(self.installation.marker.exists())

    def test_partial_move_failure_restores_first_directory(self):
        (self.candidate / "web/version").unlink()
        (self.candidate / "web/server.js").unlink()
        (self.candidate / "web").rmdir()
        with self.assertRaises(FileNotFoundError):
            self.installation.switch(self.candidate, lambda: None, "baseline")
        self.assertEqual((self.root / "api/version").read_text(), "old")
        self.assertEqual((self.root / "web/version").read_text(), "old")
        self.assertFalse(self.installation.override.exists())

    def test_manual_rollback_can_restore_original_next_start_layout(self):
        (self.candidate / "web/server.js").unlink()
        (self.candidate / "config").mkdir()
        self.installation.override.parent.mkdir()
        self.installation.override.write_text("standalone")
        self.installation.switch(self.candidate, lambda: None, "baseline")
        self.assertFalse(self.installation.override.exists())
        self.assertEqual((self.installation.previous / "config/web-override.conf").read_text(), "standalone")

    def test_interrupted_state_blocks_new_deploy(self):
        self.installation.marker.write_text("{}")
        with self.assertRaisesRegex(ValueError, "Interrupted"):
            self.installation.validate()

    def test_unstoppable_process_retains_both_versions_and_journal(self):
        def fail():
            raise RecoveryRequired("service cannot stop")

        with self.assertRaises(RecoveryRequired):
            self.installation.switch(self.candidate, fail, "baseline")
        self.assertTrue(self.installation.marker.exists())
        self.assertEqual((self.root / "web/version").read_text(), "new")
        self.assertEqual((self.base / "work/old/web/version").read_text(), "old")

    def test_unrecognized_previous_is_preserved(self):
        self.installation.previous.mkdir()
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            self.installation.validate()

    def test_checksum_mismatch_never_extracts(self):
        archive = self.base / "bundle.tar.gz"
        archive.write_bytes(b"not an archive")
        destination = self.base / "extract"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            unpack(archive, destination, "0" * 64)
        self.assertFalse(destination.exists())

    def test_traversal_links_and_duplicate_entries_rejected_before_extraction(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("/escape", tarfile.REGTYPE),
                           ("web/link", tarfile.SYMTYPE), ("web/hard", tarfile.LNKTYPE),
                           ("web/device", tarfile.CHRTYPE), ("web/../../escape", tarfile.REGTYPE)):
            with self.subTest(name=name):
                archive = self.base / "bundle.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    info = tarfile.TarInfo(name)
                    info.type = kind
                    bundle.addfile(info, io.BytesIO())
                destination = self.base / "extract"
                with self.assertRaisesRegex(ValueError, "Unsafe"):
                    unpack(archive, destination, digest(archive))
                self.assertFalse(destination.exists())

    def test_duplicate_names_are_rejected(self):
        archive = self.base / "bundle.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for _ in range(2):
                bundle.addfile(tarfile.TarInfo("web/server.js"), io.BytesIO())
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            unpack(archive, self.base / "extract", digest(archive))


class TransitionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.database = self.base / "live.db"
        self.snapshot = self.base / "snapshot.sqlite3"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TABLE alembic_version (version_num TEXT)")
            connection.execute("INSERT INTO alembic_version VALUES (?)", (PROFILE_FROM,))
            connection.execute("CREATE TABLE files (id INTEGER PRIMARY KEY, body BLOB)")
            connection.execute("INSERT INTO files VALUES (1, ?)", (b"\x00original\xff",))
        self.snapshot.write_bytes(self.database.read_bytes())
        self.manifest = self.snapshot.with_suffix(".sqlite3.json")
        self.manifest.write_text(json.dumps({"format_version": 1, "filename": self.snapshot.name,
            "bytes": self.snapshot.stat().st_size, "sha256": digest(self.snapshot)}))

    def change_database(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("UPDATE alembic_version SET version_num=?", (PROFILE_TO,))
            connection.execute("CREATE TABLE likes (id INTEGER PRIMARY KEY)")
            connection.execute("UPDATE files SET body=?", (b"changed",))

    def test_recovery_restores_revision_rows_and_blobs_in_existing_wal_database(self):
        self.change_database()
        restore_transition_snapshot(self.snapshot, self.database)
        self.assertEqual(table_fingerprints(self.database), table_fingerprints(self.snapshot))
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), (PROFILE_FROM,))
            self.assertEqual(connection.execute("SELECT body FROM files").fetchone(), (b"\x00original\xff",))
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='likes'").fetchone())

    def test_invalid_backup_is_rejected_before_database_changes(self):
        self.change_database()
        before = table_fingerprints(self.database)
        self.snapshot.write_bytes(b"damaged backup")
        with self.assertRaisesRegex(ValueError, "verification"):
            restore_transition_snapshot(self.snapshot, self.database)
        self.assertEqual(table_fingerprints(self.database), before)

    def test_fingerprints_compare_only_original_tables_but_detect_changed_file(self):
        before = table_fingerprints(self.database)
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TABLE new_table (id INTEGER)")
        self.assertEqual(table_fingerprints(self.database, before), before)
        self.change_database()
        self.assertNotEqual(table_fingerprints(self.database, before), before)

    def test_wrong_snapshot_revision_is_refused(self):
        with closing(sqlite3.connect(self.snapshot)) as connection, connection:
            connection.execute("UPDATE alembic_version SET version_num=?", (PROFILE_TO,))
        metadata = json.loads(self.manifest.read_text())
        metadata["sha256"] = digest(self.snapshot)
        self.manifest.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "recovery source"):
            restore_transition_snapshot(self.snapshot, self.database)


if __name__ == "__main__":
    unittest.main()
