"""Exercise the real VM installer/SSH gate on a disposable GitHub Linux runner."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

from deploy_vm import WEB_OVERRIDE, app_run, health, prepare, protect_candidate
from runtime_bundle import unpack

ROOT = Path(__file__).resolve().parents[1]


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def main(archive, sha):
    if (os.geteuid() != 0 or os.environ.get("GITHUB_ACTIONS") != "true"
            or not str(ROOT).startswith("/home/runner/work/")):
        raise ValueError("This fixture is restricted to disposable GitHub-hosted Linux CI")
    for path in ("/srv/nen", "/srv/nen-previous", "/etc/nen", "/etc/systemd/system/nen-api.service",
                 "/etc/systemd/system/nen-web.service", "/var/lib/nen-cd"):
        if Path(path).exists():
            raise ValueError(f"CI fixture path already exists: {path}")
    node = Path(shutil.which("node")).resolve()
    node_link = Path("/usr/local/bin/node")
    if node_link.resolve() != node:
        if node_link.exists() or node_link.is_symlink():
            node_link.unlink()
        node_link.symlink_to(node)
    run("useradd", "--system", "--user-group", "--home-dir", "/srv/nen", "--shell", "/usr/sbin/nologin", "nen")
    runtime = Path("/srv/nen")
    metadata = unpack(archive, runtime, sha)
    protect_candidate(runtime)
    prepare(runtime / "api")
    (runtime / "api/runtime.json").write_text(json.dumps({"commit": "a" * 40}))
    run("install", "-d", "-o", "nen", "-g", "nen", "-m", "0750", "/var/lib/nen")
    app_run(runtime / "api", "-m", "app.db_admin", "migrate", "--backup-dir", "/var/backups/nen")
    Path("/etc/nen").mkdir()
    Path("/etc/nen/api.env").write_text("DATABASE_URL=sqlite:////var/lib/nen/pact.db\nPACT_DEBUG=false\nPACT_COOKIE_SECURE=true\n")
    units = (ROOT / "scripts/setup-vm-services.sh").read_text().split("<<'UNIT'\n")[1:]
    for name, source in zip(("nen-api.service", "nen-web.service"), units):
        Path("/etc/systemd/system", name).write_text(source.split("\nUNIT", 1)[0] + "\n")
    override = Path("/etc/systemd/system/nen-web.service.d")
    override.mkdir()
    (override / "nen-standalone.conf").write_text(WEB_OVERRIDE)
    run("systemctl", "daemon-reload")
    run("systemctl", "start", "nen-api.service", "nen-web.service")
    health()
    request = urllib.request.Request("http://127.0.0.1:3000/api/v1/auth/register", headers={"Content-Type": "application/json"},
                                    data=json.dumps({"username": "ssh_test", "email": "ssh@example.test",
                                                     "full_name": "SSH Test", "password": "SSHFixture123!"}).encode())
    with urllib.request.urlopen(request) as response:
        assert response.status == 201
    with tempfile.TemporaryDirectory(prefix="nen-ssh-fixture-") as temporary:
        work = Path(temporary)
        key = work / "client"
        host = work / "host"
        for path in (key, host):
            run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path))
        run("bash", str(ROOT / "scripts/setup-vm-cd.sh"), str(key.with_suffix(".pub")))
        Path("/run/sshd").mkdir(exist_ok=True)
        config = work / "sshd.conf"
        config.write_text(f"Port 2222\nListenAddress 127.0.0.1\nHostKey {host}\nPidFile {work / 'sshd.pid'}\n"
                          "PasswordAuthentication no\nKbdInteractiveAuthentication no\nUsePAM yes\nPermitRootLogin no\n"
                          "AllowUsers nen-deploy\nStrictModes yes\nAuthorizedKeysFile .ssh/authorized_keys\nLogLevel VERBOSE\n")
        ssh_log = work / "sshd.log"
        sshd = subprocess.Popen(["/usr/sbin/sshd", "-D", "-f", str(config), "-E", str(ssh_log)])
        env = {**os.environ, "NEN_DEPLOY_SSH_KEY": key.read_text(),
               "NEN_DEPLOY_KNOWN_HOSTS": "[127.0.0.1]:2222 " + " ".join(host.with_suffix(".pub").read_text().split()[:2])}
        delivery = ["/usr/bin/python3", str(ROOT / "scripts/deliver_runtime.py")]
        target = ["--host", "127.0.0.1", "--port", "2222"]
        try:
            time.sleep(0.5)
            run(*delivery, "probe", *target, env=env)
            command = [*delivery, "install", *target, "--archive", str(archive), "--sha256", sha, "--commit", metadata["commit"]]
            # Disconnect both the client and its ssh child during a real update.
            client = subprocess.Popen(command, env=env, start_new_session=True)
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                state = run("systemctl", "show", "nen-deploy.service", "--property=ActiveState", "--value",
                            capture_output=True, text=True).stdout.strip()
                if state == "activating":
                    os.killpg(client.pid, signal.SIGTERM)
                    client.wait(timeout=10)
                    break
                if client.poll() is not None:
                    raise RuntimeError("SSH fixture upload exited before the deployment started")
                time.sleep(0.1)
            else:
                os.killpg(client.pid, signal.SIGKILL)
                client.wait()
                raise RuntimeError("SSH fixture deployment did not start")
            result = Path("/var/lib/nen-cd/last-result.json")
            deadline = time.monotonic() + 120
            while not result.exists() and time.monotonic() < deadline:
                time.sleep(0.5)
            status = json.loads(result.read_text())
            assert status["status"] == "success", status
            health()
            previous = Path("/srv/nen-previous/api/runtime.json")
            before = previous.read_bytes()
            assert json.loads(before)["commit"] == "a" * 40
            # A retry must not destroy the last distinct rollback version.
            time.sleep(1)
            run(*command, env=env)
            assert previous.read_bytes() == before
            assert (runtime / "api").stat().st_uid == 0
            assert not (runtime / "api").stat().st_mode & 0o022
            with sqlite3.connect("/var/lib/nen/pact.db") as connection:
                assert connection.execute("SELECT username FROM users WHERE username='ssh_test'").fetchone() == ("ssh_test",)
            denied = subprocess.run(["runuser", "-u", "nen-deploy", "--", "sudo", "-n", "/usr/bin/id"], capture_output=True)
            assert denied.returncode != 0, "Deployment account unexpectedly has general sudo access"
            print(json.dumps({"ssh_vm_fixture": "passed", "checks": ["restricted SSH and sudo", "offline installation",
                             "deployment survives client disconnect", "same-commit retry preserves rollback", "root-owned code", "user data preserved"]}))
        except BaseException as error:
            journal = subprocess.run(["journalctl", "-u", "nen-deploy.service", "-u", "nen-api.service", "--no-pager", "-n", "45", "-o", "cat"],
                                     capture_output=True, text=True).stdout
            detail = f"{error}\n{ssh_log.read_text() if ssh_log.exists() else ''}\n{journal}"
            print("::error::" + detail[-9000:].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A"))
            raise
        finally:
            sshd.terminate()
            sshd.wait(timeout=10)
            subprocess.run(["systemctl", "stop", "nen-deploy.service", "nen-api.service", "nen-web.service"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    main(args.archive.resolve(), args.sha256)
