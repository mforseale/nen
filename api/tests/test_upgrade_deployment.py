"""Exercise the upgrade coordinator on temporary SQLite/files; never call systemd.

All fixed server paths, account operations, service commands and runtime preparation
are replaced before deploy() runs. Alembic, snapshots and recovery use real SQLite.
"""
from contextlib import ExitStack, nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import deploy_vm as deployment
from alembic import command
from sqlalchemy import create_engine
from app.db_admin import database_status, migrate_database
from app.migrations import migration_config
from app.sqlite_backup import backup_database, restore_backup


class ProfileUpgradeDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nen-upgrade-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "application"
        self.previous = self.base / "previous"
        self.backups = self.base / "backups"
        self.backups.mkdir()
        self.database = self.base / "live.sqlite3"
        self.url = "sqlite:///" + self.database.as_posix()
        engine = create_engine(self.url)
        with engine.begin() as connection:
            command.upgrade(migration_config(connection), deployment.PROFILE_FROM)
            connection.exec_driver_sql("INSERT INTO users VALUES (1, 'upgrade', 'upgrade@example.test', 'Upgrade', '2026-10-20')")
            connection.exec_driver_sql(
                "INSERT INTO profile_files (user_id, name, media_type, kind, size, content, position, pinned, visibility, created_at) "
                "VALUES (1, 'original.bin', 'application/octet-stream', 'file', 5, ?, 0, 0, 'private', '2026-10-20')",
                (b"\x00old\xff",))
        engine.dispose()
        self.before = deployment.table_fingerprints(self.database)
        for name in ("api", "web"):
            (self.root / name).mkdir(parents=True)
            (self.root / name / "version").write_text("old")
        (self.root / "api/.venv").mkdir()
        (self.root / "api/.venv/dependencies").write_text("old dependencies")
        (self.root / "api/runtime.json").write_text(json.dumps({"commit": "0" * 40}))
        self.installation = deployment.Installation(self.root, self.previous, self.base / "config/web.conf")
        self.work = self.base / "work"
        self.work.mkdir()
        self.services = {name: True for name in (*deployment.SERVICES, "caddy.service")}
        self.commands = []
        self.health_calls = 0
        self.fail_health = False

    def run_service(self, *arguments, **kwargs):
        self.assertEqual(arguments[0], "systemctl")
        action = arguments[1]
        self.commands.append(arguments)
        if action in ("stop", "start"):
            for name in arguments[2:]:
                self.assertIn(name, self.services)
                self.services[name] = action == "start"
        elif action == "is-active":
            self.assertTrue(self.services[arguments[-1]])
        else:
            self.assertEqual(action, "daemon-reload")
        return subprocess.CompletedProcess(arguments, 0)

    def health(self):
        self.health_calls += 1
        self.assertTrue(all(self.services[name] for name in deployment.SERVICES))
        expected = deployment.PROFILE_TO if (self.root / "api/version").read_text() == "new" else deployment.PROFILE_FROM
        self.assertEqual(deployment.schema_revision(self.database), expected)
        if self.fail_health and self.health_calls == 2:
            raise RuntimeError("new application failed health")

    def app_run(self, api, *arguments, database=None, capture=False):
        # No subprocess/app execution. Only migration and backup library functions,
        # with an asserted destination inside this test's temporary directory.
        target = self.database if database is None else Path(database.removeprefix("sqlite:///"))
        self.assertTrue(target.is_relative_to(self.base))
        module, action, *rest = arguments[1:]
        if module == "app.db_admin":
            if action == "migrate":
                result = migrate_database("sqlite:///" + target.as_posix(), Path(rest[1]))
            else:
                result = database_status("sqlite:///" + target.as_posix())
                if action == "check":
                    self.assertTrue(result["ready"])
        else:
            self.assertEqual(module, "app.sqlite_backup")
            options = dict(zip(rest[::2], rest[1::2]))
            source = Path(options["--source"])
            self.assertTrue(source.is_relative_to(self.base))
            if action == "backup":
                directory = Path(options["--directory"])
                self.assertTrue(directory.is_relative_to(self.base))
                result = {"backup": str(backup_database(source, directory, options["--label"]))}
            else:
                destination = Path(options["--destination"])
                self.assertTrue(destination.is_relative_to(self.base))
                result = {"restored": str(restore_backup(source, destination))}
        return SimpleNamespace(stdout=json.dumps(result))

    def deploy(self, *, upgrade=True, recovery_failure=False):
        original_path = Path
        mapping = {"/var/lib/nen/pact.db": self.database, "/var/backups/nen": self.backups,
                   "/run/nen-deploy": self.base / "lock"}

        def fixed_path(value):
            self.assertIn(value, mapping, "Unexpected fixed server path")
            return mapping[value]

        def unpack(archive, candidate, sha):
            for name in ("api", "web"):
                (candidate / name).mkdir(parents=True)
                (candidate / name / "version").write_text("new")
            (candidate / "web/server.js").write_text("// test runtime")
            metadata = {"commit": "a" * 40}
            (candidate / "runtime.json").write_text(json.dumps(metadata))
            return metadata

        # Path() is also used for the snapshot path returned by the backup CLI.
        def path(value):
            return fixed_path(value) if isinstance(value, str) and value.startswith(("/var/", "/run/")) else original_path(value)

        with ExitStack() as stack:
            for name, value in {
                "Installation": lambda: self.installation, "Path": path,
                "environment_checks": self.health, "interruption_guard": nullcontext,
                "run": self.run_service, "health": self.health, "unpack": unpack,
                "protect_candidate": lambda candidate: None,
                "prepare": lambda api: (api / ".venv").mkdir(), "app_run": self.app_run,
            }.items():
                stack.enter_context(patch.object(deployment, name, value))
            stack.enter_context(patch.object(deployment.tempfile, "mkdtemp", return_value=str(self.work)))
            stack.enter_context(patch.object(deployment.shutil, "chown"))
            stack.enter_context(patch.dict(sys.modules, {"fcntl": SimpleNamespace(flock=lambda *args: None, LOCK_EX=1, LOCK_NB=2)}))
            if recovery_failure:
                stack.enter_context(patch.object(deployment, "restore_transition_snapshot", side_effect=OSError("disk failure")))
            deployment.deploy(expected_commit="a" * 40, profile_upgrade=upgrade)

    def test_normal_cd_refuses_pending_migration_without_stopping_services(self):
        with self.assertRaisesRegex(ValueError, "migration must be reviewed"):
            self.deploy(upgrade=False)
        self.assertEqual(self.commands, [])
        self.assertTrue(all(self.services.values()))
        self.assertEqual(deployment.table_fingerprints(self.database), self.before)

    def test_upgrade_preserves_data_and_keeps_compatible_snapshot_with_previous_code(self):
        self.deploy()
        self.assertTrue(database_status(self.url)["ready"])
        self.assertEqual(deployment.table_fingerprints(self.database, self.before), self.before)
        previous = json.loads((self.previous / "previous.json").read_text())
        self.assertEqual(previous["schema_revision"], deployment.PROFILE_FROM)
        self.assertEqual(deployment.schema_revision(Path(previous["database_backup"])), deployment.PROFILE_FROM)
        self.assertEqual((self.previous / "api/.venv/dependencies").read_text(), "old dependencies")
        self.assertTrue(all(self.services.values()))
        self.assertEqual(self.commands[1], ("systemctl", "stop", "caddy.service"))
        self.assertEqual(self.commands[-1], ("systemctl", "start", "caddy.service"))
        self.assertFalse(self.installation.marker.exists())
        self.assertEqual(len(list(self.backups.glob("*.sqlite3"))), 1)

    def test_failed_startup_recovers_database_and_code_before_restoring_public_access(self):
        self.fail_health = True
        with self.assertRaisesRegex(RuntimeError, "application failed health"):
            self.deploy()
        self.assertEqual(deployment.schema_revision(self.database), deployment.PROFILE_FROM)
        self.assertEqual(deployment.table_fingerprints(self.database), self.before)
        self.assertEqual((self.root / "api/.venv/dependencies").read_text(), "old dependencies")
        self.assertEqual((self.root / "api/version").read_text(), "old")
        self.assertTrue(all(self.services.values()))
        self.assertEqual(self.health_calls, 3)
        self.assertFalse(self.installation.marker.exists())

    def test_recovery_failure_retains_journal_snapshot_code_and_closed_public_gateway(self):
        self.fail_health = True
        with self.assertRaises(deployment.RecoveryRequired):
            self.deploy(recovery_failure=True)
        self.assertFalse(any(self.services.values()))
        marker = json.loads(self.installation.marker.read_text())
        self.assertTrue(Path(marker["database_backup"]).is_file())
        self.assertTrue((Path(marker["work"]) / "old/api/.venv/dependencies").is_file())
        self.assertEqual((self.root / "api/version").read_text(), "new")


if __name__ == "__main__":
    unittest.main()
