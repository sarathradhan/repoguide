"""Persist repository-specific indexing lifecycle and last-success statistics."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from app.core.config import settings


class IndexingStatusService:
    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        database = Path(settings.CHROMA_PERSIST_DIRECTORY).expanduser().resolve() / "repository_index_status.sqlite3"
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(database), timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("""CREATE TABLE IF NOT EXISTS repository_index_status (
            owner TEXT NOT NULL,
            repository TEXT NOT NULL,
            status TEXT NOT NULL,
            indexed_files INTEGER NOT NULL DEFAULT 0,
            indexed_chunks INTEGER NOT NULL DEFAULT 0,
            indexed_vectors INTEGER NOT NULL DEFAULT 0,
            last_indexed_at TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(owner, repository)
        )""")
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def mark_started(cls, owner: str, repository: str) -> None:
        now = cls._now()
        with closing(cls._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO repository_index_status(owner, repository, status, updated_at)
                   VALUES (?, ?, 'indexing', ?)
                   ON CONFLICT(owner, repository) DO UPDATE SET status='indexing', updated_at=excluded.updated_at""",
                (owner.lower(), repository.lower(), now),
            )

    @classmethod
    def mark_completed(cls, owner: str, repository: str, files: int, chunks: int, vectors: int) -> None:
        now = cls._now()
        state = "indexed" if vectors else "empty"
        with closing(cls._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO repository_index_status
                   (owner, repository, status, indexed_files, indexed_chunks, indexed_vectors, last_indexed_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(owner, repository) DO UPDATE SET status=excluded.status,
                   indexed_files=excluded.indexed_files, indexed_chunks=excluded.indexed_chunks,
                   indexed_vectors=excluded.indexed_vectors, last_indexed_at=excluded.last_indexed_at,
                   updated_at=excluded.updated_at""",
                (owner.lower(), repository.lower(), state, files, chunks, vectors, now, now),
            )

    @classmethod
    def mark_failed(cls, owner: str, repository: str) -> None:
        now = cls._now()
        with closing(cls._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO repository_index_status(owner, repository, status, updated_at)
                   VALUES (?, ?, 'failed', ?)
                   ON CONFLICT(owner, repository) DO UPDATE SET status='failed', updated_at=excluded.updated_at""",
                (owner.lower(), repository.lower(), now),
            )

    @classmethod
    def get(cls, owner: str, repository: str):
        with closing(cls._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM repository_index_status WHERE owner=? AND repository=?",
                (owner.lower(), repository.lower()),
            ).fetchone()
        return dict(row) if row else None
