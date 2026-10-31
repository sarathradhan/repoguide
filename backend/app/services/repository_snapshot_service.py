"""Persist ingested source snapshots so analysis can reuse files without refetching."""
from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Optional

from app.core.config import settings
from app.models.repository import RepositoryFile, RepositoryResponse


class RepositorySnapshotService:
    """Store the latest bounded GitHub ingestion snapshot per repository."""

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        database = Path(settings.CHROMA_PERSIST_DIRECTORY) / "repository_snapshots.sqlite3"
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(database), timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS repository_snapshots (
                owner TEXT NOT NULL,
                repository TEXT NOT NULL,
                description TEXT,
                default_branch TEXT NOT NULL,
                stars INTEGER NOT NULL,
                total_source_files_found INTEGER NOT NULL,
                files_truncated INTEGER NOT NULL,
                truncation_reason TEXT,
                PRIMARY KEY(owner, repository)
            );
            CREATE TABLE IF NOT EXISTS repository_snapshot_files (
                owner TEXT NOT NULL,
                repository TEXT NOT NULL,
                path TEXT NOT NULL,
                language TEXT NOT NULL,
                content TEXT NOT NULL,
                size INTEGER NOT NULL,
                PRIMARY KEY(owner, repository, path),
                FOREIGN KEY(owner, repository)
                    REFERENCES repository_snapshots(owner, repository) ON DELETE CASCADE
            );
            """
        )
        return connection

    @classmethod
    def save(cls, snapshot: RepositoryResponse) -> None:
        owner, repository = snapshot.owner.lower(), snapshot.repository.lower()
        with closing(cls._connect()) as connection, connection:
            connection.execute(
                """INSERT INTO repository_snapshots
                   (owner, repository, description, default_branch, stars,
                    total_source_files_found, files_truncated, truncation_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(owner, repository) DO UPDATE SET
                     description=excluded.description,
                     default_branch=excluded.default_branch,
                     stars=excluded.stars,
                     total_source_files_found=excluded.total_source_files_found,
                     files_truncated=excluded.files_truncated,
                     truncation_reason=excluded.truncation_reason""",
                (
                    owner, repository, snapshot.description, snapshot.default_branch,
                    snapshot.stars, snapshot.total_source_files_found,
                    int(snapshot.files_truncated), snapshot.truncation_reason,
                ),
            )
            connection.execute(
                "DELETE FROM repository_snapshot_files WHERE owner = ? AND repository = ?",
                (owner, repository),
            )
            connection.executemany(
                """INSERT INTO repository_snapshot_files
                   (owner, repository, path, language, content, size)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (owner, repository, file.path, file.language, file.content, file.size)
                    for file in snapshot.files
                ],
            )

    @classmethod
    def get(cls, owner: str, repository: str) -> Optional[RepositoryResponse]:
        with closing(cls._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM repository_snapshots WHERE owner = ? AND repository = ?",
                (owner.lower(), repository.lower()),
            ).fetchone()
            if row is None:
                return None
            file_rows = connection.execute(
                """SELECT path, language, content, size FROM repository_snapshot_files
                   WHERE owner = ? AND repository = ? ORDER BY path""",
                (owner.lower(), repository.lower()),
            ).fetchall()
        return RepositoryResponse(
            owner=row["owner"],
            repository=row["repository"],
            description=row["description"],
            default_branch=row["default_branch"],
            stars=row["stars"],
            total_source_files_found=row["total_source_files_found"],
            files_returned=len(file_rows),
            files_truncated=bool(row["files_truncated"]),
            truncation_reason=row["truncation_reason"],
            files=[RepositoryFile(**dict(file_row)) for file_row in file_rows],
        )
