"""Fixed-path Nen deployment: one working version and one previous copy.

Run as root on the existing VM. Normal CD refuses database schema changes.
The explicit profile-upgrade command coordinates the reviewed 0001 -> 0002 change.
"""
import argparse
from contextlib import closing
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

from runtime_bundle import unpack

SERVICES = ("nen-api.service", "nen-web.service")
PROFILE_FROM = "20261019_0001"
PROFILE_TO = "20261019_0002"
WEB_OVERRIDE = """[Service]
Environment=HOSTNAME=127.0.0.1
Environment=PORT=3000
ExecStart=
ExecStart=/usr/local/bin/node /srv/nen/web/server.js
"""


class RecoveryRequired(RuntimeError):
    """Processes could not be stopped; leave files and journal for an operator."""


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def health():
    for url in ("http://127.0.0.1:8000/api/v1/health", "http://127.0.0.1:3000/api/v1/health",
                "http://127.0.0.1:3000/"):
        deadline = time.monotonic() + 45
        while True:
            try:
                with urllib.request.urlopen(url, timeout=4) as response:
                    if response.status != 200:
                        raise ValueError("Unexpected health response")
                    if url.endswith("/health") and json.load(response) != {"status": "ok"}:
                        raise ValueError("Unexpected API health body")
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Health check failed: {url}") from None
                time.sleep(1)


def schema_revision(database):
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows) != 1:
        raise ValueError("Expected one registered Alembic revision")
    return rows[0][0]


def table_fingerprints(database, tables=None):
    """Compare original rows/BLOBs without logging their contents."""
    result = {}
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("BEGIN")
        if tables is None:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "AND name != 'alembic_version' ORDER BY name")]
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            cursor = connection.execute("SELECT * FROM " + quoted + " ORDER BY rowid")
            checksum = hashlib.sha256()
            for row in cursor:
                encoded = repr(tuple(row)).encode("utf-8")
                checksum.update(len(encoded).to_bytes(8, "big") + encoded)
            result[table] = ([column[0] for column in cursor.description], checksum.hexdigest())
    return result


def verify_snapshot(snapshot):
    from runtime_bundle import digest
    manifest = snapshot.with_suffix(snapshot.suffix + ".json")
    if snapshot.is_symlink() or manifest.is_symlink():
        raise ValueError("Snapshot files must not be symlinks")
    metadata = json.loads(manifest.read_text())
    if (metadata.get("format_version") != 1 or metadata.get("filename") != snapshot.name
            or metadata.get("bytes") != snapshot.stat().st_size or metadata.get("sha256") != digest(snapshot)):
        raise ValueError("Snapshot verification failed")
    with closing(sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True)) as connection:
        if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("Snapshot integrity check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise ValueError("Snapshot foreign keys check failed")


def restore_transition_snapshot(snapshot, database):
    """Only called before public access resumes, with both app services stopped.

    SQLite's backup API restores into the existing file and handles WAL correctly;
    no raw copy/unlink of a potentially journalled live SQLite file is used.
    """
    verify_snapshot(snapshot)
    if database.is_symlink() or schema_revision(snapshot) != PROFILE_FROM:
        raise ValueError("Unexpected database recovery source/destination")
    with closing(sqlite3.connect(snapshot.as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)) as destination:
            source.backup(destination)
            if (destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]
                    or destination.execute("PRAGMA foreign_key_check").fetchone() is not None):
                raise ValueError("Recovered database integrity check failed")
    if schema_revision(database) != PROFILE_FROM or table_fingerprints(database) != table_fingerprints(snapshot):
        raise ValueError("Recovered database differs from the pre-upgrade snapshot")


def take_snapshot(api, database, directory):
    output = app_run(api, "-m", "app.sqlite_backup", "backup", "--source", str(database),
                     "--directory", str(directory), "--label", "profile-upgrade", capture=True)
    snapshot = Path(json.loads(output.stdout)["backup"])
    if snapshot.parent != directory or not snapshot.is_file():
        raise ValueError("Unexpected snapshot location")
    verify_snapshot(snapshot)
    return snapshot


def migrate_profile(api, database, backup_directory, fingerprints):
    app_run(api, "-m", "app.db_admin", "migrate", "--backup-dir", str(backup_directory),
            database="sqlite:///" + database.as_posix(), capture=True)
    app_run(api, "-m", "app.db_admin", "check", database="sqlite:///" + database.as_posix(), capture=True)
    if schema_revision(database) != PROFILE_TO or table_fingerprints(database, fingerprints) != fingerprints:
        raise ValueError("Migration did not preserve original rows and BLOBs")


def rehearse_profile(api, database, work):
    directory = work / "rehearsal"
    directory.mkdir(mode=0o700)
    shutil.chown(directory, user="nen", group="nen")
    snapshot = take_snapshot(api, database, directory)
    restored = directory / "check.sqlite3"
    app_run(api, "-m", "app.sqlite_backup", "restore", "--source", str(snapshot),
            "--destination", str(restored), capture=True)
    migrate_profile(api, restored, directory, table_fingerprints(snapshot))
    print("Migration rehearsal verified: original rows and BLOBs preserved.", flush=True)


class Installation:
    """Path operations are isolated so failure recovery can be tested without root."""
    def __init__(self, root=Path("/srv/nen"), previous=Path("/srv/nen-previous"),
                 override=Path("/etc/systemd/system/nen-web.service.d/nen-standalone.conf")):
        self.root, self.previous, self.override = root, previous, override
        self.marker = root.parent / "nen-deploy-state.json"

    def validate(self):
        for path in (self.root, self.previous, self.override, self.marker):
            if path.is_symlink() or path.resolve() != path:
                raise ValueError(f"Expected a real, absolute path: {path}")
        for name in ("api", "web"):
            path = self.root / name
            if not path.is_dir() or path.is_symlink():
                raise ValueError(f"Expected an existing application directory: {path}")
        if self.previous.exists() and not (self.previous / "previous.json").is_file():
            raise ValueError("Refusing to replace an unrecognized previous directory")
        if self.marker.exists():
            raise ValueError(f"Interrupted deployment: inspect {self.marker} before continuing")

    def snapshot_override(self, destination):
        destination.mkdir()
        if self.override.exists():
            shutil.copy2(self.override, destination / "web-override.conf")

    def restore_override(self, source):
        if (source / "web-override.conf").exists():
            self.override.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / "web-override.conf", self.override)
        elif self.override.exists():
            self.override.unlink()

    def switch(self, candidate, finish, revision, database_backup=None):
        """Keep old files/dependencies until health succeeds; reverse partial moves."""
        candidate = Path(candidate)
        old = candidate.parent / "old"
        old.mkdir(mode=0o700)
        self.snapshot_override(old / "config")
        recovery = {"schema_revision": revision}
        if database_backup is not None:
            recovery["database_backup"] = str(database_backup)
        (old / "previous.json").write_text(json.dumps(recovery) + "\n")
        self.marker.write_text(json.dumps({"work": str(candidate.parent), **recovery}) + "\n")
        try:
            for name in ("api", "web"):
                (self.root / name).rename(old / name)
                (candidate / name).rename(self.root / name)
            self.override.parent.mkdir(parents=True, exist_ok=True)
            if (self.root / "web/server.js").is_file():
                self.override.write_text(WEB_OVERRIDE)
                self.override.chmod(0o644)
            else:
                self.restore_override(candidate / "config")
            finish()
        except BaseException as error:
            if isinstance(error, RecoveryRequired):
                raise
            # finish() must stop processes before they can keep using failed files.
            for name in ("web", "api"):
                if (old / name).exists():
                    if (self.root / name).exists():
                        shutil.rmtree(self.root / name)
                    (old / name).rename(self.root / name)
            self.restore_override(old / "config")
            self.marker.unlink()
            raise
        # Only a verified deployment replaces the previous rollback copy.
        if self.previous.exists():
            shutil.rmtree(self.previous)
        old.rename(self.previous)
        self.marker.unlink()


def app_run(api, *arguments, database="sqlite:////var/lib/nen/pact.db", capture=False):
    return run("runuser", "-u", "nen", "--", "env", f"DATABASE_URL={database}",
               "PYTHONDONTWRITEBYTECODE=1", "PACT_DEBUG=false", "PACT_COOKIE_SECURE=true",
               str(api / ".venv/bin/python"), *arguments, cwd=api,
               capture_output=capture, text=capture)


def prepare(api):
    # Validate dependencies before stopping the site. The final venv is recreated
    # at its permanent path: virtualenv launchers must not be relocated.
    venv = api / ".venv"
    venv.mkdir(mode=0o750)
    shutil.chown(venv, user="nen", group="nen")
    run("runuser", "-u", "nen", "--", "/usr/bin/python3", "-m", "venv", str(venv))
    app_run(api, "-m", "pip", "install", "--no-index", "--no-cache-dir", "--find-links", str(api / "wheels"),
            "-r", str(api / "requirements.txt"))
    app_run(api, "-m", "pip", "check")


def protect_candidate(candidate):
    # Root later moves these paths and writes metadata. App processes must not
    # replace them with symlinks while pip or application code runs as nen.
    run("chown", "-hR", "root:nen", str(candidate))
    run("chmod", "-R", "u=rwX,g=rX,o=", str(candidate))
    run("chown", "-hR", "nen:nen", str(candidate / "web/.next"))


def already_installed(api, commit):
    metadata = api / "runtime.json"
    if metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_size > 4096:
        return False
    try:
        return json.loads(metadata.read_text()).get("commit") == commit
    except (OSError, ValueError, AttributeError):
        return False


def environment_checks():
    if os.geteuid() != 0 or sys.version_info[:2] != (3, 10) or platform.machine() != "x86_64":
        raise ValueError("Run as root with /usr/bin/python3 (3.10) on the Ubuntu 22.04 x64 VM")
    if platform.freedesktop_os_release().get("VERSION_ID") != "22.04":
        raise ValueError("This installer targets Ubuntu 22.04")
    if run("/usr/local/bin/node", "--version", capture_output=True, text=True).stdout.split(".")[0] != "v24":
        raise ValueError("Node.js 24 is required")
    for service in SERVICES:
        run("systemctl", "is-active", "--quiet", service)
        if run("systemctl", "show", service, "--property=User", "--value",
               capture_output=True, text=True).stdout.strip() != "nen":
            raise ValueError("Expected existing services running as nen")
    # Check the real running process, without printing or sourcing its secrets.
    pid = int(run("systemctl", "show", SERVICES[0], "--property=MainPID", "--value",
                  capture_output=True, text=True).stdout)
    variables = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
    if [v for v in variables if v.startswith(b"DATABASE_URL=")] != [b"DATABASE_URL=sqlite:////var/lib/nen/pact.db"]:
        raise ValueError("The API does not use the expected external database")
    for service in SERVICES:
        override_text = run("systemctl", "show", service, "--property=DropInPaths", "--value",
                            capture_output=True, text=True).stdout.split()
        allowed = "/etc/systemd/system/nen-web.service.d/nen-standalone.conf"
        if any(path != allowed or service != SERVICES[1] for path in override_text):
            raise ValueError("Unexpected systemd overrides; review them before deploying")
    health()


@contextmanager
def interruption_guard():
    def interrupted(signum, frame):
        raise RuntimeError(f"Deployment interrupted by signal {signum}")
    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def deploy(archive=None, sha=None, rollback=False, expected_commit=None, profile_upgrade=False):
    import fcntl
    installation = Installation()
    installation.validate()
    lock_directory = Path("/run/nen-deploy")
    if lock_directory.is_symlink():
        raise ValueError("Invalid deployment lock directory")
    lock_directory.mkdir(mode=0o700, exist_ok=True)
    with open(lock_directory / "lock", "a") as lock, interruption_guard():
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        installation.validate()
        environment_checks()
        database = Path("/var/lib/nen/pact.db")
        if database.is_symlink():
            raise ValueError("The live database must not be a symlink")
        revision = schema_revision(database)
        if profile_upgrade:
            if rollback or revision != PROFILE_FROM:
                raise ValueError("The reviewed profile upgrade requires database revision 20261019_0001")
            run("systemctl", "is-active", "--quiet", "caddy.service")
        work = Path(tempfile.mkdtemp(prefix=".nen-deploy-", dir="/srv"))
        work.chmod(0o750)
        shutil.chown(work, group="nen")
        try:
            candidate = work / "candidate"
            if rollback:
                recorded = json.loads((installation.previous / "previous.json").read_text())
                if recorded["schema_revision"] != revision:
                    raise ValueError("Previous code expects another DB revision; automatic rollback refused")
                shutil.copytree(installation.previous, candidate, symlinks=True)
            else:
                metadata = unpack(archive, candidate, sha)
                if expected_commit is not None and metadata["commit"] != expected_commit:
                    raise ValueError("Runtime commit does not match the verified CI commit")
                if already_installed(installation.root / "api", metadata["commit"]):
                    print("This commit is already installed; previous rollback copy preserved.", flush=True)
                    return
                print(f"Preparing {metadata['commit']}", flush=True)
                protect_candidate(candidate)
                prepare(candidate / "api")
                status = json.loads(app_run(candidate / "api", "-m", "app.db_admin", "status", capture=True).stdout)
                if profile_upgrade:
                    if status["head"] != PROFILE_TO or status["revision"] != [PROFILE_FROM]:
                        raise ValueError("This command permits only the reviewed 0001 -> 0002 profile migration")
                    rehearse_profile(candidate / "api", database, work)
                elif not status["ready"]:
                    raise ValueError("Schema migration must be reviewed and applied separately first")
                if not profile_upgrade:
                    shutil.rmtree(candidate / "api/.venv")
            if rollback:
                protect_candidate(candidate)
            stopped = False
            public_stopped = False
            safe_to_publish = False
            snapshot = None
            try:
                if profile_upgrade:
                    public_stopped = True
                    run("systemctl", "stop", "caddy.service")
                stopped = True
                run("systemctl", "stop", *reversed(SERVICES))
                if schema_revision(database) != revision:
                    raise ValueError("The database revision changed during preparation")
                if profile_upgrade:
                    snapshot = take_snapshot(candidate / "api", database, Path("/var/backups/nen"))
                    print(f"Pre-upgrade snapshot: {snapshot}", flush=True)
                    fingerprints = table_fingerprints(snapshot)
                    shutil.rmtree(candidate / "api/.venv")

                def finish():
                    migration_started = False
                    try:
                        if not rollback:
                            prepare(installation.root / "api")
                            shutil.copy2(candidate / "runtime.json", installation.root / "api/runtime.json")
                        if profile_upgrade:
                            migration_started = True
                            migrate_profile(installation.root / "api", database, work / "rehearsal", fingerprints)
                        run("systemctl", "daemon-reload")
                        run("systemctl", "start", *SERVICES)
                        health()
                    except BaseException:
                        try:
                            run("systemctl", "stop", *reversed(SERVICES))
                        except BaseException as stop_error:
                            raise RecoveryRequired("Could not stop failed services; deployment journal retained") from stop_error
                        if migration_started:
                            try:
                                restore_transition_snapshot(snapshot, database)
                            except BaseException as recovery_error:
                                raise RecoveryRequired("Database recovery failed; services remain stopped; inspect deployment journal") from recovery_error
                        raise

                installation.switch(candidate, finish, revision, database_backup=snapshot)
                stopped = False
                safe_to_publish = True
            finally:
                if stopped and not installation.marker.exists():
                    run("systemctl", "daemon-reload")
                    run("systemctl", "start", *SERVICES)
                    health()
                    safe_to_publish = True
                if public_stopped and safe_to_publish:
                    run("systemctl", "start", "caddy.service")
            message = "Database upgraded to 20261019_0002." if profile_upgrade else "Database unchanged."
            print(f"Deployment verified. Previous application: /srv/nen-previous. {message}", flush=True)
        finally:
            # A kill/power loss or failed recovery leaves the marker and work for inspection.
            if not installation.marker.exists():
                shutil.rmtree(work)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install")
    install.add_argument("archive", type=Path)
    install.add_argument("--sha256", required=True)
    install.add_argument("--expected-commit")
    upgrade = commands.add_parser("install-profile-upgrade", help="Root-only reviewed 0001 -> 0002 transition with rehearsal and recovery")
    upgrade.add_argument("archive", type=Path)
    upgrade.add_argument("--sha256", required=True)
    upgrade.add_argument("--expected-commit", required=True)
    commands.add_parser("rollback")
    args = parser.parse_args()
    if args.command == "rollback":
        deploy(rollback=True)
    else:
        deploy(args.archive, args.sha256, expected_commit=args.expected_commit,
               profile_upgrade=args.command == "install-profile-upgrade")
