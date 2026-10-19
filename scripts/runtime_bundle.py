"""Build and safely unpack Nen's Linux runtime archive (stdlib only)."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def unpack(archive, destination, expected_sha):
    """Only regular files/directories; never follow archive links or overwrite files."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha) or digest(archive) != expected_sha:
        raise ValueError("Runtime archive SHA-256 mismatch")
    destination = Path(destination)
    if destination.is_symlink() or (destination.exists() and any(destination.iterdir())):
        raise ValueError("Extraction requires a new or empty directory")
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        names = set()
        total = 0
        for member in members:
            path = PurePosixPath(member.name)
            if (not path.parts or path.is_absolute() or ".." in path.parts
                    or "\\" in member.name or ":" in member.name
                    or path.parts[0] not in {"api", "web", "runtime.json"}
                    or not (member.isfile() or member.isdir())
                    or path.as_posix() in names):
                raise ValueError(f"Unsafe runtime archive entry: {member.name}")
            names.add(path.as_posix())
            total += member.size
        if total > 4 * 1024**3 or len(members) > 100_000:
            raise ValueError("Runtime archive exceeds size/file limit")
        destination.mkdir(parents=True, exist_ok=True)
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    metadata = json.loads((destination / "runtime.json").read_text())
    if (metadata.get("format") != 1 or metadata.get("platform") != "ubuntu-22.04-x64"
            or metadata.get("python") != "3.10" or metadata.get("node") != 24
            or not re.fullmatch(r"[0-9a-f]{40}", metadata.get("commit", ""))):
        raise ValueError("Unsupported runtime metadata")
    for name in ("api/app/main.py", "api/app/db_admin.py", "api/alembic.ini",
                 "api/requirements.txt", "web/server.js", "web/.next/BUILD_ID",
                 "web/public/nen-bg.jpg"):
        if not (destination / name).is_file():
            raise ValueError(f"Runtime file missing: {name}")
    if not list((destination / "api/wheels").glob("*.whl")):
        raise ValueError("API wheelhouse is missing")
    return metadata


def build(output, wheels, commit):
    if sys.platform != "linux" or platform.machine() != "x86_64" or sys.version_info[:2] != (3, 10):
        raise ValueError("Build runtime on Ubuntu 22.04 x64 with Python 3.10")
    os_release = platform.freedesktop_os_release()
    if os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID") != "22.04":
        raise ValueError("Build runtime on Ubuntu 22.04")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Expected a full source commit SHA")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="nen-bundle-") as temporary:
        stage = Path(temporary)
        for name in ("app", "alembic"):
            shutil.copytree(ROOT / "api" / name, stage / "api" / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env*"))
        for name in ("alembic.ini", "requirements.txt"):
            shutil.copy2(ROOT / "api" / name, stage / "api" / name)
        shutil.copytree(wheels, stage / "api/wheels")
        # Explicit tracing root is web/. No monorepo nesting in this bundle.
        shutil.copytree(ROOT / "web/.next/standalone", stage / "web")
        shutil.copytree(ROOT / "web/public", stage / "web/public", dirs_exist_ok=True)
        shutil.copytree(ROOT / "web/.next/static", stage / "web/.next/static", dirs_exist_ok=True)
        for path in (stage / "web").rglob("*"):
            if path.name.startswith(".env"):
                raise ValueError("Environment files must not enter runtime archives")
        (stage / "runtime.json").write_text(json.dumps({
            "format": 1, "commit": commit, "platform": "ubuntu-22.04-x64", "python": "3.10", "node": 24,
        }, indent=2) + "\n")
        archive = output / "nen-runtime.tar.gz"
        with tarfile.open(archive, "w:gz", dereference=True) as bundle:
            for path in sorted(stage.iterdir()):
                bundle.add(path, arcname=path.name)
        sha = digest(archive)
        (output / "nen-runtime.sha256").write_text(f"{sha}  {archive.name}\n", encoding="ascii", newline="\n")
        print(json.dumps({"archive": str(archive), "sha256": sha, "bytes": archive.stat().st_size}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    build(args.output, args.wheels, args.commit)
