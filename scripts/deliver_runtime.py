"""GitHub runner transport: pinned host key, dedicated identity, bounded upload."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from runtime_bundle import digest


@contextmanager
def identity():
    key = os.environ.get("NEN_DEPLOY_SSH_KEY", "").strip()
    hosts = os.environ.get("NEN_DEPLOY_KNOWN_HOSTS", "").strip()
    if not key.startswith("-----BEGIN OPENSSH PRIVATE KEY-----") or not hosts or "PRIVATE KEY" in hosts:
        raise ValueError("Configure NEN_DEPLOY_SSH_KEY and NEN_DEPLOY_KNOWN_HOSTS secrets")
    with tempfile.TemporaryDirectory(prefix="nen-ssh-") as temporary:
        key_path, hosts_path = Path(temporary) / "identity", Path(temporary) / "known_hosts"
        key_path.write_text(key.replace("\r\n", "\n") + "\n")
        key_path.chmod(0o600)
        hosts_path.write_text(hosts.replace("\r\n", "\n") + "\n")
        hosts_path.chmod(0o600)
        yield key_path, hosts_path


def deliver(host, port, mode, archive=None, sha=None, commit=None):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", host) or not 1 <= port <= 65535:
        raise ValueError("Invalid deploy host or port")
    message = {"version": 1, "action": mode}
    if mode == "install":
        if not re.fullmatch(r"[0-9a-f]{40}", commit or "") or digest(archive) != sha:
            raise ValueError("Archive checksum or CI commit is invalid")
        message.update(size=archive.stat().st_size, sha256=sha, commit=commit)
    with identity() as (key, hosts):
        command = ["ssh", "-F", "/dev/null", "-T", "-i", str(key), "-p", str(port),
                   "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
                   "-o", f"UserKnownHostsFile={hosts}", "-o", "GlobalKnownHostsFile=/dev/null",
                   "-o", "ConnectTimeout=15", "-o", "ConnectionAttempts=1",
                   "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=4", f"nen-deploy@{host}"]
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        try:
            process.stdin.write(json.dumps(message).encode() + b"\n")
            if mode == "install":
                with archive.open("rb") as source:
                    while block := source.read(1024 * 1024):
                        process.stdin.write(block)
            process.stdin.close()
            if process.wait(timeout=1100) != 0:
                raise RuntimeError("SSH deployment failed; inspect the VM journal and CD job log")
        except BaseException:
            process.kill()
            process.wait()
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["probe", "install", "status"])
    parser.add_argument("--host", default="144.31.189.98")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--commit")
    args = parser.parse_args()
    deliver(args.host, args.port, args.mode, args.archive, args.sha256, args.commit)
