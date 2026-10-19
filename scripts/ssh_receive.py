#!/usr/bin/python3 -I
"""Fixed SSH entry point and systemd worker. Only root-owned code runs as root."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

STATE = Path("/var/lib/nen-cd")
TOOLS = Path("/usr/local/lib/nen/cd")
SERVICE = "nen-deploy.service"
MAX_BYTES = 512 * 1024 * 1024
ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C.UTF-8"}


def run(*command, **kwargs):
    return subprocess.run(command, check=True, env=ENV, **kwargs)


def header(stream):
    raw = stream.readline(4097)
    if len(raw) > 4096 or not raw.endswith(b"\n"):
        raise ValueError("Expected a bounded JSON deployment header")
    message = json.loads(raw)
    if not isinstance(message, dict) or message.get("version") != 1:
        raise ValueError("Unsupported deployment protocol")
    if message.get("action") not in {"probe", "install", "status"}:
        raise ValueError("Only probe, status and install are allowed")
    if message["action"] == "install":
        if (not isinstance(message.get("size"), int) or isinstance(message["size"], bool)
                or not 0 < message["size"] <= MAX_BYTES
                or not re.fullmatch(r"[0-9a-f]{64}", str(message.get("sha256", "")))
                or not re.fullmatch(r"[0-9a-f]{40}", str(message.get("commit", "")))):
            raise ValueError("Invalid runtime size, SHA-256 or commit")
    return message


def receive_file(stream, destination, message):
    remaining = message["size"]
    checksum = hashlib.sha256()
    with destination.open("xb") as output:
        while remaining:
            block = stream.read(min(remaining, 1024 * 1024))
            if not block:
                raise ValueError("Incomplete runtime upload")
            output.write(block)
            checksum.update(block)
            remaining -= len(block)
        output.flush()
        os.fsync(output.fileno())
    if stream.read(1):
        raise ValueError("Unexpected bytes after runtime upload")
    if checksum.hexdigest() != message["sha256"]:
        raise ValueError("Uploaded runtime SHA-256 mismatch")


def unit_busy():
    state = run("systemctl", "show", SERVICE, "--property=ActiveState", "--value", capture_output=True, text=True).stdout.strip()
    return state in {"active", "activating", "deactivating", "reloading"}


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as output:
        json.dump(value, output)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def receive(stream, state=STATE):
    import fcntl
    # The gate is a sudo command with no arguments. Incoming paths are never
    # chosen by the SSH caller, and the private spool is not writable by them.
    def interrupted(signum, frame):
        raise RuntimeError(f"SSH transfer interrupted by signal {signum}")

    for signum in (signal.SIGHUP, signal.SIGTERM, signal.SIGALRM):
        signal.signal(signum, interrupted)
    signal.alarm(180)
    message = header(stream)
    if message["action"] == "probe":
        print(json.dumps({"ready": (TOOLS / "deploy_vm.py").is_file(), "protocol": 1,
                          "busy": unit_busy()}), flush=True)
        return 0
    if message["action"] == "status":
        result = state / "last-result.json"
        print(result.read_text() if result.exists() else '{"status":"not-deployed"}', flush=True)
        return 0
    with (state / "receive.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        pending = state / "pending"
        if pending.exists() or unit_busy():
            raise ValueError("A deployment is running or pending; inspect systemctl status nen-deploy")
        work = Path(tempfile.mkdtemp(prefix="upload-", dir=state))
        owned_by_service = False
        try:
            receive_file(stream, work / "runtime.tar.gz", message)
            message["request_id"] = uuid.uuid4().hex
            atomic_json(work / "request.json", message)
            work.rename(pending)
            owned_by_service = True
            signal.alarm(0)
            run("systemctl", "reset-failed", SERVICE)
            run("systemctl", "start", "--no-block", SERVICE)
            # The service owns pending/ from now on. If SSH disappears, neither
            # its process nor its input files are removed by this connection.
            deadline = time.monotonic() + 950
            while time.monotonic() < deadline:
                result_path = state / "last-result.json"
                if result_path.exists():
                    result = json.loads(result_path.read_text())
                    if result.get("request_id") == message["request_id"] and not unit_busy():
                        run("journalctl", "-u", SERVICE, "--no-pager", "-n", "100", "-o", "cat")
                        print(json.dumps(result), flush=True)
                        return 0 if result["status"] == "success" else 1
                time.sleep(1)
            raise RuntimeError("Deployment wait timed out; check nen-deploy.service on the VM")
        finally:
            if not owned_by_service:
                shutil.rmtree(work)


def apply(state=STATE, tools=TOOLS):
    pending = state / "pending"
    message = json.loads((pending / "request.json").read_text())
    result = {key: message[key] for key in ("request_id", "commit", "sha256")}
    try:
        outcome = subprocess.run(["/usr/bin/python3", "-E", "-s", str(tools / "deploy_vm.py"), "install",
                                  str(pending / "runtime.tar.gz"), "--sha256", message["sha256"],
                                  "--expected-commit", message["commit"]], env=ENV)
        result.update(status="success" if outcome.returncode == 0 else "failure", exit_code=outcome.returncode)
        return outcome.returncode
    except BaseException:
        result.update(status="failure", exit_code=1)
        raise
    finally:
        atomic_json(state / "last-result.json", result)
        shutil.rmtree(pending)


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("This fixed entry point must run via its restricted sudo rule")
    os.umask(0o077)
    try:
        if sys.argv[1:] == ["apply"]:
            raise SystemExit(apply())
        if sys.argv[1:]:
            raise ValueError("The SSH entry point takes no command-line arguments")
        raise SystemExit(receive(sys.stdin.buffer))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Deployment rejected: {error}", file=sys.stderr)
        raise SystemExit(1)
