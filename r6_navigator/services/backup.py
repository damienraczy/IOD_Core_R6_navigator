from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def save_backup(db_path: Path, backup_dir: Path) -> Path:
    """Copies the DB to backup_dir/r6_navigator_YYYYMMDD_HHMMSS.db.

    Returns the backup file path. Raises IOError on failure.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"r6_navigator_{timestamp}.db"
    try:
        shutil.copy2(db_path, backup_path)
    except OSError as e:
        raise IOError(f"Backup failed: {e}") from e
    return backup_path


def restore_backup(backup_path: Path, db_path: Path) -> None:
    """Validates backup_path (sqlite3 integrity_check) then copies it over db_path.

    Raises IOError if the file is not a valid SQLite database.
    Caller is responsible for reinitialising the session and reloading the UI.
    """
    try:
        conn = sqlite3.connect(str(backup_path))
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
    except sqlite3.DatabaseError as e:
        raise IOError(f"Not a valid SQLite file: {backup_path}") from e

    if result is None or result[0] != "ok":
        raise IOError(f"Backup failed integrity check: {backup_path}")

    try:
        shutil.copy2(backup_path, db_path)
    except OSError as e:
        raise IOError(f"Restore failed: {e}") from e
