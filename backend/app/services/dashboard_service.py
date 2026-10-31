"""Repository dashboard assembled exclusively from persisted indexing and Q&A data."""
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import PurePosixPath
from typing import Dict, Optional

from app.models.repository import (
    DashboardActivity, DashboardArchitectureOverview, DashboardDependencyOverview,
    DashboardFileStatistic, DashboardLanguageStatistic, DashboardQuestionDay,
    DashboardTopicStatistic, RepositoryDashboardResponse, RepositoryResponse,
    RepositorySourceReference,
)
from app.services.architecture_service import ArchitectureService
from app.services.conversation_service import ConversationService
from app.services.dependency_service import DependencyAnalysisService
from app.services.github_service import GitHubService
from app.services.indexing_status_service import IndexingStatusService
from app.services.repository_snapshot_service import RepositorySnapshotService
from app.services.vector_store import VectorStoreService

TOPIC_STOP_WORDS = {
    "about", "after", "also", "any", "are", "does", "file", "from", "how", "into",
    "is", "its", "that", "the", "this", "was", "what", "when", "where", "which",
    "with", "work", "would", "you", "your", "repo", "repository", "code", "explain",
}


class DashboardService:
    """Build repository stats and session-scoped conversation analytics."""

    @classmethod
    def get_dashboard(cls, repo_url: str, session_id) -> RepositoryDashboardResponse:
        owner, repository = GitHubService.parse_repo_url(repo_url)
        snapshot = RepositorySnapshotService.get(owner, repository)
        index_stats = VectorStoreService.get_repository_index_stats(owner, repository)
        index_state = IndexingStatusService.get(owner, repository)
        if index_state:
            status = index_state["status"]
            last_indexed_at = index_state.get("last_indexed_at")
        elif index_stats["vectors"]:
            status = "indexed"
            last_indexed_at = None
        else:
            status = "not_indexed"
            last_indexed_at = None

        languages = index_stats["languages"]
        if not languages and snapshot:
            languages = cls._snapshot_languages(snapshot)
        conversation_data = cls._conversation_data(owner, repository, session_id)

        architecture = None
        dependencies = None
        analysis_snapshot = snapshot
        if analysis_snapshot is None:
            files = VectorStoreService.get_repository_files(owner, repository)
            if files:
                analysis_snapshot = RepositoryResponse(
                    owner=owner, repository=repository, description=None,
                    default_branch=VectorStoreService.get_repository_default_branch(owner, repository),
                    stars=0, total_source_files_found=len(files), files_returned=len(files),
                    files_truncated=False, truncation_reason=None, files=files,
                )
        if analysis_snapshot is not None:
            arch = ArchitectureService.analyze_files(analysis_snapshot)
            architecture = DashboardArchitectureOverview(
                files_analyzed=arch.files_analyzed,
                directories_detected=arch.directories_detected,
                entry_points_detected=arch.entry_points_detected,
                routes_detected=arch.routes_detected,
            )
            deps = DependencyAnalysisService.analyze_files(analysis_snapshot)
            dependencies = DashboardDependencyOverview(
                files_analyzed=deps.files_analyzed,
                resolved_imports=len(deps.edges),
                cycles=len(deps.cycles),
                unresolved_imports=len(deps.unresolved_imports),
                isolated_files=len(deps.isolated_files),
            )

        return RepositoryDashboardResponse(
            owner=owner,
            repository=repository,
            repo_url=f"https://github.com/{owner}/{repository}",
            description=snapshot.description if snapshot else None,
            default_branch=(snapshot.default_branch if snapshot else VectorStoreService.get_repository_default_branch(owner, repository) if index_stats["vectors"] else None),
            indexing_status=status,
            indexed_files=index_stats["files"],
            indexed_chunks=index_stats["vectors"],
            indexed_vectors=index_stats["vectors"],
            languages=[DashboardLanguageStatistic(language=name, files=count) for name, count in sorted(languages.items())],
            last_indexed_at=last_indexed_at,
            snapshot_files=snapshot.files_returned if snapshot else index_stats["files"],
            architecture=architecture,
            dependencies=dependencies,
            **conversation_data,
        )

    @staticmethod
    def _snapshot_languages(snapshot: RepositoryResponse) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for file in snapshot.files:
            counts[file.language] = counts.get(file.language, 0) + 1
        return counts

    @classmethod
    def _conversation_data(cls, owner: str, repository: str, session_id):
        session = str(session_id).lower()
        scope = (owner.lower(), repository.lower(), session)
        with closing(ConversationService._connect()) as connection:
            question_rows = connection.execute(
                """SELECT m.content, m.created_at FROM conversation_messages m
                   JOIN conversations c USING(conversation_id)
                   WHERE c.owner=? AND c.repository=? AND c.session_id=? AND m.role='user'""",
                scope,
            ).fetchall()
            answer_rows = connection.execute(
                """SELECT m.sources_json FROM conversation_messages m
                   JOIN conversations c USING(conversation_id)
                   WHERE c.owner=? AND c.repository=? AND c.session_id=? AND m.role='assistant'""",
                scope,
            ).fetchall()
            recent_rows = connection.execute(
                """SELECT q.conversation_id, c.title, c.repository, q.content AS question, q.created_at,
                          (SELECT a.content FROM conversation_messages a
                           WHERE a.conversation_id=q.conversation_id AND a.role='assistant'
                             AND a.message_id>q.message_id ORDER BY a.message_id LIMIT 1) AS answer,
                          (SELECT a.sources_json FROM conversation_messages a
                           WHERE a.conversation_id=q.conversation_id AND a.role='assistant'
                             AND a.message_id>q.message_id ORDER BY a.message_id LIMIT 1) AS sources_json
                   FROM conversation_messages q JOIN conversations c USING(conversation_id)
                   WHERE c.owner=? AND c.repository=? AND c.session_id=? AND q.role='user'
                   ORDER BY q.message_id DESC LIMIT 12""",
                scope,
            ).fetchall()

        question_rows = [dict(row) for row in question_rows]
        recent_questions = question_rows
        files = Counter()
        modules = Counter()
        for row in answer_rows:
            try:
                sources = json.loads(row["sources_json"] or "[]")
            except (TypeError, json.JSONDecodeError):
                sources = []
            seen_paths = set()
            for source in sources:
                path = source.get("path")
                if not path or path in seen_paths:
                    continue
                seen_paths.add(path)
                files[path] += 1
                parent = str(PurePosixPath(path).parent)
                if parent not in ("", "."):
                    modules[parent] += 1

        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=29)
        daily = Counter()
        topics = Counter()
        for row in recent_questions:
            try:
                created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                if start_date <= created.date() <= today:
                    daily[created.date().isoformat()] += 1
            except (TypeError, ValueError):
                pass
            words = set(re.findall(r"[a-z][a-z0-9_]{2,}", row["content"].lower())) - TOPIC_STOP_WORDS
            topics.update(words)

        summaries = ConversationService.list_for_session(owner, repository, session_id)
        activity = []
        for row in recent_rows:
            try:
                raw_sources = json.loads(row["sources_json"] or "[]") if row["sources_json"] else []
                sources = [RepositorySourceReference(**source) for source in raw_sources]
            except (TypeError, ValueError, json.JSONDecodeError):
                sources = []
            answer = row["answer"] or ""
            activity.append(DashboardActivity(
                conversation_id=row["conversation_id"],
                conversation_title=row["title"],
                repository=row["repository"],
                question=row["question"],
                answer_preview=(answer[:260] + ("…" if len(answer) > 260 else "")) or None,
                created_at=row["created_at"],
                sources=sources,
            ))

        return {
            "total_questions": len(question_rows),
            "questions_over_time": [
                DashboardQuestionDay(date=day, question_count=count)
                for day, count in sorted(daily.items())
            ],
            "frequently_referenced_files": [
                DashboardFileStatistic(path=path, reference_count=count)
                for path, count in files.most_common(8)
            ],
            "most_explored_modules": [
                DashboardFileStatistic(path=path, reference_count=count)
                for path, count in modules.most_common(6)
            ],
            "most_explored_topics": [
                DashboardTopicStatistic(topic=topic, question_count=count)
                for topic, count in topics.most_common(8)
            ],
            "recent_activity": activity,
            "conversations": summaries[:20],
        }
