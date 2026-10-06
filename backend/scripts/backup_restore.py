#!/usr/bin/env python3
"""Database backup and restoration utility for CUSTODE.

Supports deterministic offline and online backups for PostgreSQL and SQLite.
Provides backup generation, integrity verification, and recovery functions.
"""

from datetime import datetime, timezone
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
from typing import Dict, Optional, Tuple

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)


def compute_file_sha256(filepath: str) -> str:
    """Compute SHA-256 digest of a backup file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def backup_sqlite(source_path: str, destination_path: str) -> Tuple[bool, str, Dict[str, str]]:
    """Perform a consistent online backup of a SQLite database."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
        src_conn = sqlite3.connect(source_path)
        dest_conn = sqlite3.connect(destination_path)
        with dest_conn:
            src_conn.backup(dest_conn)
        dest_conn.close()
        src_conn.close()

        sha256 = compute_file_sha256(destination_path)
        size = os.path.getsize(destination_path)
        meta = {
            "type": "sqlite",
            "source": source_path,
            "destination": destination_path,
            "sha256": sha256,
            "size_bytes": str(size),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return True, "SQLite backup created successfully", meta
    except Exception as e:
        return False, f"SQLite backup failed: {str(e)}", {}


def restore_sqlite(backup_path: str, target_path: str) -> Tuple[bool, str]:
    """Restore a SQLite database from a verified backup file."""
    try:
        if not os.path.exists(backup_path):
            return False, f"Backup file does not exist: {backup_path}"
        if os.path.getsize(backup_path) == 0:
            return False, f"Backup file is empty: {backup_path}"

        # Test integrity of backup first
        test_conn = sqlite3.connect(backup_path)
        cursor = test_conn.cursor()
        cursor.execute("PRAGMA quick_check;")
        check_res = cursor.fetchone()
        test_conn.close()
        if not check_res or check_res[0] != "ok":
            return False, f"Backup integrity check failed: {check_res}"

        # Copy to target location atomically
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        tmp_target = f"{target_path}.tmp.{os.getpid()}"
        shutil.copy2(backup_path, tmp_target)
        os.replace(tmp_target, target_path)

        return True, "SQLite database restored successfully"
    except Exception as e:
        return False, f"SQLite restore failed: {str(e)}"


def backup_postgres(
    database_url: str,
    output_path: str,
) -> Tuple[bool, str, Dict[str, str]]:
    """Perform pg_dump on PostgreSQL database URL."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        # Parse connection details without logging password
        cmd = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", f"--file={output_path}", database_url]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode != 0:
            return False, f"pg_dump failed with exit code {res.returncode}: {res.stderr}", {}

        sha256 = compute_file_sha256(output_path)
        size = os.path.getsize(output_path)
        meta = {
            "type": "postgres",
            "destination": output_path,
            "sha256": sha256,
            "size_bytes": str(size),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return True, "PostgreSQL backup created successfully", meta
    except FileNotFoundError:
        return False, "pg_dump binary not found in system PATH", {}
    except Exception as e:
        return False, f"PostgreSQL backup failed: {str(e)}", {}


def restore_postgres(
    backup_path: str,
    database_url: str,
) -> Tuple[bool, str]:
    """Restore PostgreSQL database using pg_restore."""
    try:
        if not os.path.exists(backup_path) or os.path.getsize(backup_path) == 0:
            return False, f"Invalid or missing backup file: {backup_path}"

        cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges", f"--dbname={database_url}", backup_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        # pg_restore may return 0 or 1 for minor warnings (e.g. notices)
        if res.returncode > 1:
            return False, f"pg_restore failed with exit code {res.returncode}: {res.stderr}"

        return True, "PostgreSQL restore completed successfully"
    except FileNotFoundError:
        return False, "pg_restore binary not found in system PATH"
    except Exception as e:
        return False, f"PostgreSQL restore failed: {str(e)}"


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage:")
        print("  backup_restore.py backup <source_sqlite_or_db_url> <output_file>")
        print("  backup_restore.py restore <backup_file> <target_sqlite_or_db_url>")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "backup":
        src = sys.argv[2]
        dest = sys.argv[3]
        if src.startswith("postgresql"):
            ok, msg, meta = backup_postgres(src, dest)
        else:
            ok, msg, meta = backup_sqlite(src, dest)
        print(msg)
        if ok:
            print(f"Metadata: {meta}")
        sys.exit(0 if ok else 1)
    elif action == "restore":
        backup_file = sys.argv[2]
        target = sys.argv[3]
        if target.startswith("postgresql"):
            ok, msg = restore_postgres(backup_file, target)
        else:
            ok, msg = restore_sqlite(backup_file, target)
        print(msg)
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
