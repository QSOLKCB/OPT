#!/usr/bin/env python3
"""Create one private disposable SQLite fixture for OPT-DB-001, never overwrite."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import stat


def create_fixture(path):
    raw = Path(path).expanduser()
    if ".." in raw.parts:
        raise ValueError("path_traversal")
    path = raw.absolute()
    parent = path.parent
    info = parent.lstat()
    if (not stat.S_ISDIR(info.st_mode) or parent.is_symlink() or
            (os.name == "posix" and
             (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077))):
        raise ValueError("private parent directory required")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    os.close(fd)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=FULL")
        conn.executescript("""
            CREATE TABLE conversations (
                conversation_id TEXT PRIMARY KEY NOT NULL,
                created_utc TEXT NOT NULL,
                updated_utc TEXT NOT NULL,
                consent INTEGER NOT NULL CHECK (consent = 1)
            );
            CREATE TABLE messages (
                message_id INTEGER PRIMARY KEY,
                conversation_id TEXT NOT NULL
                    REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                classification TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE INDEX messages_by_conversation
                ON messages(conversation_id, message_id);
        """)
        with conn:
            for sid in range(40):
                session = f"session-{sid:04d}"
                stamp = f"2026-11-09T{sid % 24:02d}:00:00Z"
                conn.execute(
                    "INSERT INTO conversations VALUES (?,?,?,1)",
                    (session, stamp, stamp),
                )
                conn.executemany(
                    "INSERT INTO messages(conversation_id,role,content,"
                    "classification,created_utc) VALUES (?,?,?,?,?)",
                    [
                        (session, "user" if i % 2 == 0 else "assistant",
                         f"synthetic record {sid}:{i}", "user" if i % 2 == 0 else
                         "model_generated_unverified", stamp)
                        for i in range(12)
                    ],
                )
        # Verify fixture integrity without treating this as a benchmark result.
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("synthetic fixture integrity check failed")
    finally:
        conn.close()
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create private disposable SQLite fixture")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        path = create_fixture(args.output)
    except (OSError, sqlite3.Error, ValueError) as exc:
        parser.exit(2, f"OPT-DB-001 fixture: {type(exc).__name__}: {exc}\n")
    print("synthetic_fixture=" + str(path))
    print("synthetic_data_only=true")


if __name__ == "__main__":
    main()
