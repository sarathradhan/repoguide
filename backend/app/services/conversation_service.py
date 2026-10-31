"""Persistent conversations scoped to a repository and browser session."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.core.config import settings
from app.models.repository import (
    ConversationDetailResponse,
    ConversationMessage,
    ConversationSummary,
    RepositoryAskResponse,
    RepositorySourceReference,
    RetrievedContextMetadata,
)


class ConversationService:
    """SQLite-backed conversation lifecycle and transcript persistence."""

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        database = Path(settings.CONVERSATIONS_DB_PATH).expanduser().resolve()
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(database), timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                owner TEXT NOT NULL,
                repository TEXT NOT NULL,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conversations_scope
                ON conversations(owner, repository, session_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS conversation_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                sources_json TEXT NOT NULL DEFAULT '[]',
                retrieved_context_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conversation_messages_order
                ON conversation_messages(conversation_id, message_id);
            """
        )
        return connection

    @staticmethod
    def _normalize_scope(owner: str, repository: str, session_id: UUID | str) -> tuple[str, str, str]:
        return owner.lower(), repository.lower(), str(session_id).lower()

    @classmethod
    def create(
        cls, owner: str, repository: str, session_id: UUID | str
    ) -> ConversationDetailResponse:
        conversation_id = uuid4()
        now = cls._now()
        normalized_owner, normalized_repo, normalized_session = cls._normalize_scope(
            owner, repository, session_id
        )
        with closing(cls._connect()) as connection:
            with connection:
                connection.execute(
                    """INSERT INTO conversations
                       (conversation_id, owner, repository, session_id, title, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(conversation_id), normalized_owner, normalized_repo,
                        normalized_session, "New conversation", now, now,
                    ),
                )
        return ConversationDetailResponse(
            conversation_id=conversation_id,
            repository=repository,
            title="New conversation",
            created_at=now,
            updated_at=now,
            messages=[],
        )

    @classmethod
    def list_for_session(
        cls, owner: str, repository: str, session_id: UUID | str
    ) -> List[ConversationSummary]:
        scope = cls._normalize_scope(owner, repository, session_id)
        with closing(cls._connect()) as connection:
            rows = connection.execute(
                """SELECT c.conversation_id, c.title, c.created_at, c.updated_at,
                          COUNT(m.message_id) AS message_count
                   FROM conversations AS c
                   LEFT JOIN conversation_messages AS m USING (conversation_id)
                   WHERE c.owner = ? AND c.repository = ? AND c.session_id = ?
                   GROUP BY c.conversation_id
                   ORDER BY c.updated_at DESC, c.created_at DESC""",
                scope,
            ).fetchall()
        return [ConversationSummary(**dict(row)) for row in rows]

    @classmethod
    def get_for_session(
        cls,
        conversation_id: UUID | str,
        owner: str,
        repository: str,
        session_id: UUID | str,
    ) -> Optional[ConversationDetailResponse]:
        scope = cls._normalize_scope(owner, repository, session_id)
        with closing(cls._connect()) as connection:
            conversation = connection.execute(
                """SELECT conversation_id, repository, title, created_at, updated_at
                   FROM conversations
                   WHERE conversation_id = ? AND owner = ? AND repository = ? AND session_id = ?""",
                (str(conversation_id), *scope),
            ).fetchone()
            if conversation is None:
                return None
            rows = connection.execute(
                """SELECT message_id, role, content, created_at, sources_json,
                          retrieved_context_json
                   FROM conversation_messages
                   WHERE conversation_id = ? ORDER BY message_id""",
                (str(conversation_id),),
            ).fetchall()

        messages = []
        for row in rows:
            messages.append(
                ConversationMessage(
                    message_id=row["message_id"],
                    role=row["role"],
                    content=row["content"],
                    created_at=row["created_at"],
                    sources=[RepositorySourceReference(**source) for source in json.loads(row["sources_json"])],
                    retrieved_context=(
                        RetrievedContextMetadata(**json.loads(row["retrieved_context_json"]))
                        if row["retrieved_context_json"] else None
                    ),
                )
            )
        return ConversationDetailResponse(
            conversation_id=conversation["conversation_id"],
            repository=conversation["repository"],
            title=conversation["title"],
            created_at=conversation["created_at"],
            updated_at=conversation["updated_at"],
            messages=messages,
        )

    @classmethod
    def recent_turns(
        cls,
        conversation_id: UUID | str,
        owner: str,
        repository: str,
        session_id: UUID | str,
        limit: int = 6,
    ) -> Optional[List[Dict[str, str]]]:
        detail = cls.get_for_session(conversation_id, owner, repository, session_id)
        if detail is None:
            return None
        return [
            {"role": message.role, "content": message.content}
            for message in detail.messages[-limit:]
        ]

    @classmethod
    def append_exchange(
        cls,
        conversation_id: UUID | str,
        owner: str,
        repository: str,
        session_id: UUID | str,
        question: str,
        answer: RepositoryAskResponse,
    ) -> bool:
        scope = cls._normalize_scope(owner, repository, session_id)
        now = cls._now()
        sources = [source.model_dump(mode="json") for source in answer.sources]
        context = answer.retrieved_context.model_dump(mode="json")
        with closing(cls._connect()) as connection:
            with connection:
                row = connection.execute(
                    """SELECT title FROM conversations
                       WHERE conversation_id = ? AND owner = ? AND repository = ? AND session_id = ?""",
                    (str(conversation_id), *scope),
                ).fetchone()
                if row is None:
                    return False
                has_messages = connection.execute(
                    "SELECT 1 FROM conversation_messages WHERE conversation_id = ? LIMIT 1",
                    (str(conversation_id),),
                ).fetchone() is not None
                connection.execute(
                    """INSERT INTO conversation_messages
                       (conversation_id, role, content, sources_json, retrieved_context_json, created_at)
                       VALUES (?, 'user', ?, '[]', NULL, ?)""",
                    (str(conversation_id), question, now),
                )
                connection.execute(
                    """INSERT INTO conversation_messages
                       (conversation_id, role, content, sources_json, retrieved_context_json, created_at)
                       VALUES (?, 'assistant', ?, ?, ?, ?)""",
                    (str(conversation_id), answer.answer, json.dumps(sources), json.dumps(context), now),
                )
                title = row["title"]
                if not has_messages:
                    title = " ".join(question.split())[:80] or "New conversation"
                connection.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
                    (title, now, str(conversation_id)),
                )
        return True


class SuggestedQuestionService:
    """Derive prompt ideas from actual indexed paths and declarations."""

    DECLARATION_PATTERNS = {
        "Python": r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)",
        "JavaScript": r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)",
        "React JSX": r"^\s*(?:export\s+)?(?:default\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)",
        "TypeScript": r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(?:class|interface|enum|type|function)\s+([A-Za-z_$][\w$]*)",
        "React TSX": r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?(?:class|interface|enum|type|function)\s+([A-Za-z_$][\w$]*)",
        "Java": r"^\s*(?:public\s+|protected\s+|private\s+)?(?:abstract\s+)?(?:class|interface|enum|record)\s+([A-Za-z_]\w*)",
        "C#": r"^\s*(?:public\s+|internal\s+|private\s+)?(?:abstract\s+)?(?:class|interface|enum|record)\s+([A-Za-z_]\w*)",
        "C++": r"^\s*(?:class|struct|enum\s+class)\s+([A-Za-z_]\w*)",
    }

    @classmethod
    def from_chunks(cls, chunks: List[Dict[str, Any]], limit: int = 5) -> List[str]:
        import re

        suggestions: List[str] = []
        seen = set()
        for chunk in chunks:
            path = chunk.get("path", "")
            language = chunk.get("language", "")
            pattern = cls.DECLARATION_PATTERNS.get(language)
            if pattern:
                for name in re.findall(pattern, chunk.get("content", ""), flags=re.MULTILINE):
                    question = f"What does `{name}` do?"
                    if name.lower() not in {"init", "main", "self", "constructor"} and question not in seen:
                        seen.add(question)
                        suggestions.append(question)
                        if len(suggestions) >= limit:
                            return suggestions
            if path:
                question = f"What is implemented in `{path}`?"
                if question not in seen:
                    seen.add(question)
                    suggestions.append(question)
                    if len(suggestions) >= limit:
                        return suggestions
        return suggestions
