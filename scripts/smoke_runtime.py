"""Boot the actual packed Linux runtime against a disposable database in CI."""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

from runtime_bundle import unpack


def request(opener, url, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    with opener.open(urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}), timeout=10) as response:
        return response.read(), response.headers


def wait_ready(url, processes):
    opener = urllib.request.build_opener()
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("A runtime process exited before readiness")
        try:
            body, _ = request(opener, url)
            if json.loads(body) == {"status": "ok"}:
                return
        except (OSError, ValueError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"Runtime did not become ready: {url}")


def smoke(archive, sha):
    processes = []
    with tempfile.TemporaryDirectory(prefix="nen-runtime-smoke-") as temporary:
        work = Path(temporary)
        bundle = work / "unpacked"
        metadata = unpack(archive, bundle, sha)
        api = bundle / "api"
        venv = work / "venv"
        subprocess.run(["python", "-m", "venv", str(venv)], check=True)
        python = str(venv / "bin/python")
        subprocess.run([python, "-m", "pip", "install", "--no-index", "--find-links", str(api / "wheels"),
                        "-r", str(api / "requirements.txt")], check=True)
        env = {**os.environ, "DATABASE_URL": "sqlite:///" + (work / "smoke.db").as_posix(),
               "PACT_COOKIE_SECURE": "false", "PACT_DEBUG": "false", "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run([python, "-m", "app.db_admin", "migrate", "--backup-dir", str(work / "backups")],
                       cwd=api, env=env, check=True)
        log = work / "runtime.log"
        try:
            with log.open("w") as output:
                processes.append(subprocess.Popen([python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                                   "--port", "8000"], cwd=api, env=env, stdout=output, stderr=output))
                processes.append(subprocess.Popen(["node", "server.js"], cwd=bundle / "web",
                                 env={**env, "HOSTNAME": "127.0.0.1", "PORT": "3300", "NODE_ENV": "production"},
                                 stdout=output, stderr=output))
                wait_ready("http://127.0.0.1:8000/api/v1/health", processes)
                wait_ready("http://127.0.0.1:3300/api/v1/health", processes)
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                base = "http://127.0.0.1:3300"
                home, _ = request(opener, base + "/")
                static_paths = re.findall(rb'(?:src|href)="([^"?]*?/_next/static/[^"?]+)', home)
                if not static_paths:
                    raise RuntimeError("Home page has no static assets")
                for path in set(static_paths):
                    request(opener, base + path.decode())
                body, _ = request(opener, base + "/nen-bg.jpg")
                if len(body) < 100_000:
                    raise RuntimeError("Public background is missing")
                # Exercises sharp's native Linux dependency in the packed server.
                body, headers = request(opener, base + "/_next/image?url=%2Fnen-bg.jpg&w=640&q=75")
                if not headers.get("Content-Type", "").startswith("image/") or not body:
                    raise RuntimeError("Image optimizer did not serve an image")
                user, _ = request(opener, base + "/api/v1/auth/register", {
                    "username": "runtime_test", "email": "runtime@example.test", "full_name": "Runtime Test",
                    "password": "RuntimeSmoke123!",
                })
                if json.loads(user)["username"] != "runtime_test":
                    raise RuntimeError("Registration through the frontend proxy failed")
                me, _ = request(opener, base + "/api/v1/auth/me")
                if json.loads(me)["username"] != "runtime_test":
                    raise RuntimeError("Session cookie did not reach the API")
                for path in ("/forum", "/people/runtime_test"):
                    request(opener, base + path)
                print(json.dumps({"runtime_smoke": "passed", "commit": metadata["commit"],
                                  "checks": ["offline API install", "migrations", "API and proxy health", "pages",
                                             "JS/CSS assets", "public background", "native image optimizer", "registration/session"]}))
        except BaseException:
            print(log.read_text(errors="replace")[-12000:])
            raise
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    smoke(args.archive, args.sha256)
