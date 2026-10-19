"""SQLite online backup/restore; also runs standalone with Python 3.10+."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time


def readonly(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"Database does not exist: {path}")
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)


def check_integrity(connection):
    if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite quick_check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("SQLite foreign_key_check failed")


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _reserve(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)


def _sync(path):
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _sync_directory(path):
    if os.name == "posix":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _copy(source, destination, timeout):
    deadline = time.monotonic() + timeout

    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError("SQLite backup exceeded its time limit")

    with closing(readonly(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst, pages=128, progress=progress, sleep=0.1)
        check_integrity(dst)
    _sync(destination)


def prune_daily(directory, keep):
    """Only delete complete daily pairs in this exact directory, never manual copies."""
    if keep < 1:
        raise ValueError("At least one daily backup must be retained")
    directory = Path(directory).resolve()
    pattern = re.compile(r"nen-daily-\d{8}T\d{12}Z-[0-9a-f]{8}\.sqlite3")
    pairs = []
    for path in directory.iterdir():
        manifest = path.with_suffix(path.suffix + ".json")
        if not pattern.fullmatch(path.name) or path.is_symlink() or manifest.is_symlink():
            continue
        if path.is_file() and manifest.is_file():
            try:
                metadata = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(metadata, dict) and metadata.get("format_version") == 1 and metadata.get("filename") == path.name:
                pairs.append(path)
    for path in sorted(pairs, reverse=True)[keep:]:
        path.with_suffix(path.suffix + ".json").unlink()
        path.unlink()
    _sync_directory(directory)


def backup_database(source, directory, label="manual", keep=None, timeout=120):
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", label):
        raise ValueError("Invalid backup label")
    if keep is not None and (label != "daily" or keep < 1):
        raise ValueError("Retention is supported only for daily backups, keep >= 1")
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError(f"Database does not exist: {source}")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = directory / f"nen-{label}-{stamp}-{secrets.token_hex(4)}.sqlite3"
    manifest = destination.with_suffix(destination.suffix + ".json")
    partial = destination.with_suffix(destination.suffix + ".partial")
    partial_manifest = manifest.with_suffix(manifest.suffix + ".partial")
    _reserve(partial)
    published = False
    manifest_reserved = False
    try:
        _copy(source, partial, timeout)
        metadata = {
            "format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "filename": destination.name,
            "bytes": partial.stat().st_size,
            "sha256": digest(partial),
        }
        _reserve(partial_manifest)
        manifest_reserved = True
        partial_manifest.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        _sync(partial_manifest)
        # Hard links publish atomically without replacing an existing file.
        os.link(partial, destination)
        published = True
        os.link(partial_manifest, manifest)
    except BaseException:
        if published:
            destination.unlink()
        raise
    finally:
        partial.unlink(missing_ok=True)
        if manifest_reserved:
            partial_manifest.unlink(missing_ok=True)
    _sync_directory(directory)
    if keep is not None:
        prune_daily(directory, keep)
    return destination


def verify_backup(source):
    source = Path(source).resolve()
    manifest = source.with_suffix(source.suffix + ".json")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("format_version") != 1 or metadata.get("filename") != source.name:
        raise ValueError("Invalid backup manifest")
    if source.stat().st_size != metadata.get("bytes") or digest(source) != metadata.get("sha256"):
        raise ValueError("Backup checksum or size mismatch")
    with closing(readonly(source)) as connection:
        check_integrity(connection)
    return metadata


def restore_backup(source, destination, timeout=120):
    source = Path(source).resolve()
    # Do not resolve the destination leaf: even a dangling symlink must be refused.
    raw = Path(destination).absolute()
    destination = raw.parent.resolve() / raw.name
    for suffix in ("", "-wal", "-shm", "-journal"):
        candidate = Path(str(destination) + suffix)
        if candidate.exists() or candidate.is_symlink():
            raise ValueError(f"Restore requires a new destination: {candidate}")
    if not destination.parent.is_dir():
        raise ValueError("Restore destination directory does not exist")
    verify_backup(source)
    partial = destination.with_name(destination.name + ".restore-" + secrets.token_hex(8) + ".partial")
    _reserve(partial)
    try:
        _copy(source, partial, timeout)
        os.link(partial, destination)
    finally:
        partial.unlink(missing_ok=True)
    _sync_directory(destination.parent)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("backup")
    backup.add_argument("--source", type=Path, required=True)
    backup.add_argument("--directory", type=Path, required=True)
    backup.add_argument("--label", default="manual")
    backup.add_argument("--keep", type=int)
    verify = commands.add_parser("verify")
    verify.add_argument("--source", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--source", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "backup":
            result = {"backup": str(backup_database(args.source, args.directory, args.label, args.keep))}
        elif args.command == "verify":
            result = verify_backup(args.source)
        else:
            result = {"restored": str(restore_backup(args.source, args.destination))}
    except (OSError, ValueError, sqlite3.Error, TimeoutError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
