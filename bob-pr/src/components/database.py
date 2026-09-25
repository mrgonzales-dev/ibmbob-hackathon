"""Database layer: SQLite schema and connection setup.

All state lives in one file: .bob-pr/bob_pr.db under the project root.
Three tables: prs (one row per plan), revisions (one row per plan version),
events (one row per comment or decision).
"""

import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS prs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pr_id INTEGER NOT NULL REFERENCES prs(id),
  n INTEGER NOT NULL,
  summary TEXT NOT NULL,
  files_json TEXT NOT NULL,
  diffs_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pr_id INTEGER NOT NULL REFERENCES prs(id),
  revision_id INTEGER,
  kind TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
"""


def _ensure_column(connection, table_name, column_name, column_type):
    """Add a column to an existing table when it is missing.

    CREATE TABLE IF NOT EXISTS does not upgrade old databases, so this
    applies a plain ALTER TABLE for databases created before the column
    existed.
    """
    existing = [
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})")
    ]
    if column_name not in existing:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )
        connection.commit()


def init_db(database_path):
    """Open the SQLite database at database_path, creating it if needed.

    Creates the parent directory, applies the schema, and upgrades older
    databases that lack newer columns. Returns a sqlite3.Connection with
    foreign keys enabled.
    """
    parent_dir = os.path.dirname(os.path.abspath(database_path))
    os.makedirs(parent_dir, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    _ensure_column(connection, "revisions", "diffs_json", "TEXT")
    return connection
