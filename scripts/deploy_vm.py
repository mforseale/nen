"""Fixed-path Nen deployment: one working version and one previous copy.

Run as root on the existing VM. Database schema changes are deliberately refused
in this first CD stage; perform reviewed migrations separately before deploying.
"""
import argparse
from contextlib import contextmanager
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
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows) != 1:
        raise ValueError("Expected one registered Alembic revision")
    return rows[0][0]


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

    def switch(self, candidate, finish, revision):
        """Keep old files/dependencies until health succeeds; reverse partial moves."""
        candidate = Path(candidate)
        old = candidate.parent / "old"
        old.mkdir(mode=0o700)
        self.snapshot_override(old / "config")
        (old / "previous.json").write_text(json.dumps({"schema_revision": revision}) + "\n")
        self.marker.write_text(json.dumps({"work": str(candidate.parent), "schema_revision": revision}) + "\n")
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
    run("runuser", "-u", "nen", "--", "/usr/bin/python3", "-m", "venv", str(api / ".venv"))
    app_run(api, "-m", "pip", "install", "--no-index", "--no-cache-dir", "--find-links", str(api / "wheels"),
            "-r", str(api / "requirements.txt"))
    app_run(api, "-m", "pip", "check")


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


def deploy(archive=None, sha=None, rollback=False):
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
                print(f"Preparing {metadata['commit']}", flush=True)
                run("chown", "-hR", "nen:nen", str(candidate))
                prepare(candidate / "api")
                status = json.loads(app_run(candidate / "api", "-m", "app.db_admin", "check", capture=True).stdout)
                if not status["ready"]:
                    raise ValueError("Schema migration must be reviewed and applied separately first")
                shutil.rmtree(candidate / "api/.venv")
            run("chown", "-hR", "nen:nen", str(candidate))
            stopped = False
            try:
                stopped = True
                run("systemctl", "stop", *reversed(SERVICES))
                if schema_revision(database) != revision:
                    raise ValueError("The database revision changed during preparation")

                def finish():
                    try:
                        if not rollback:
                            prepare(installation.root / "api")
                            shutil.copy2(candidate / "runtime.json", installation.root / "api/runtime.json")
                        run("systemctl", "daemon-reload")
                        run("systemctl", "start", *SERVICES)
                        health()
                    except BaseException:
                        try:
                            run("systemctl", "stop", *reversed(SERVICES))
                        except BaseException as stop_error:
                            raise RecoveryRequired("Could not stop failed services; deployment journal retained") from stop_error
                        raise

                installation.switch(candidate, finish, revision)
                stopped = False
            finally:
                if stopped and not installation.marker.exists():
                    run("systemctl", "daemon-reload")
                    run("systemctl", "start", *SERVICES)
                    health()
            print("Deployment verified. Previous application: /srv/nen-previous. Database unchanged.", flush=True)
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
    commands.add_parser("rollback")
    args = parser.parse_args()
    deploy(rollback=True) if args.command == "rollback" else deploy(args.archive, args.sha256)
