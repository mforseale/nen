"""Package Linux sources; optionally back up the local DB outside the archive."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tarfile


ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    "README.md", "CONTRIBUTING.md", "docs", "scripts", "api/app", "api/alembic", "api/tests",
    "api/alembic.ini", "api/requirements.txt", "api/.env.example",
    "web/src", "web/public", "web/tests", "web/package.json",
    "web/package-lock.json", "web/next.config.ts", "web/tsconfig.json",
    "web/eslint.config.mjs", "web/.env.example", "web/README.md",
)
EXCLUDED_PARTS = {".git", ".venv", "node_modules", ".next", "__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".tsbuildinfo", ".pem", ".key"}


def source_files():
    result = set()
    for relative in INPUTS:
        base = ROOT / relative
        if not base.exists():
            raise FileNotFoundError(base)
        candidates = base.rglob("*") if base.is_dir() else (base,)
        for path in candidates:
            parts = path.relative_to(ROOT).parts
            if any(part in EXCLUDED_PARTS for part in parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Symlinks must be reviewed before packaging: {path}")
            if not path.is_file():
                continue
            if path.suffix.lower() in EXCLUDED_SUFFIXES:
                continue
            if path.name.startswith(".env") and path.name != ".env.example":
                continue
            if parts[0] == "docs" and path.suffix != ".md" and not (
                len(parts) > 2 and parts[1] == "images" and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            ):
                continue
            result.add(path)
    return sorted(result)


def backup_database():
    source = ROOT / "api" / "pact.db"
    if not source.is_file():
        raise FileNotFoundError(source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = ROOT / ".local-backups" / f"before-vm-deploy-{stamp}.sqlite3"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise RuntimeError("Database backup failed quick_check")
            if dst.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("Database backup has foreign key violations")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-database", action="store_true")
    args = parser.parse_args()
    files = source_files()
    output = ROOT / ".deploy" / "nen-source.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as bundle:
        for path in files:
            bundle.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    checksum = hashlib.sha256()
    with output.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    digest = checksum.hexdigest()
    # GNU sha256sum treats a CR from Windows text newlines as part of the filename.
    output.with_name("nen-source.sha256").write_bytes(f"{digest}  {output.name}\n".encode("ascii"))
    backup = backup_database() if args.backup_database else None
    print(json.dumps({"archive": str(output), "files": len(files), "bytes": output.stat().st_size,
                      "sha256": digest, "database_backup": str(backup) if backup else None}, indent=2))


if __name__ == "__main__":
    main()
