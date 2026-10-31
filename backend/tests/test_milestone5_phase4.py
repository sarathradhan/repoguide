"""Repository dashboard analytics tests using persisted conversation records."""
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.core.config import settings
from app.main import app
from app.models.repository import (
    RepositoryAskResponse, RepositoryFile, RepositoryResponse,
    RepositorySourceReference, RetrievedContextMetadata,
)
from app.services.conversation_service import ConversationService
from app.services.indexing_status_service import IndexingStatusService
from app.services.repository_snapshot_service import RepositorySnapshotService


def make_snapshot(owner="psf", repository="requests"):
    files = [
        RepositoryFile(path="src/requests/api.py", language="Python", content="def get(): pass\n", size=16),
        RepositoryFile(path="src/requests/sessions.py", language="Python", content="class Session: pass\n", size=21),
    ]
    return RepositoryResponse(owner=owner, repository=repository, description="HTTP library", default_branch="main",
                              stars=0, total_source_files_found=len(files), files_returned=len(files),
                              files_truncated=False, truncation_reason=None, files=files)


def answer_with_sources(repository, paths):
    sources = [RepositorySourceReference(
        citation_id=f"S{index}", chunk_id=f"chunk-{index}", path=path, language="Python",
        start_line=index, end_line=index + 3, similarity_score=0.9, distance=0.1,
        url=f"https://github.com/psf/{repository}/blob/main/{path}#L{index}-L{index + 3}",
    ) for index, path in enumerate(paths, 1)]
    return RepositoryAskResponse(
        answer="The request flow uses the session and API modules.", repository=repository,
        question="How does the request flow work?", sources=sources,
        retrieved_context=RetrievedContextMetadata(chunks_retrieved=2, top_k=5, top_similarity=0.9,
                                                   minimum_similarity=0.3, context_sufficient=True),
    )


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.conversation_patch = patch.object(settings, "CONVERSATIONS_DB_PATH", str(Path(self.temporary.name) / "conversations.sqlite3"))
        self.storage_patch = patch.object(settings, "CHROMA_PERSIST_DIRECTORY", str(Path(self.temporary.name) / "storage"))
        self.conversation_patch.start()
        self.storage_patch.start()
        self.vector_stats_patch = patch("app.services.dashboard_service.VectorStoreService.get_repository_index_stats", return_value={"vectors": 0, "files": 0, "languages": {}})
        self.indexed_files_patch = patch("app.services.dashboard_service.VectorStoreService.get_repository_files", return_value=[])
        self.vector_stats_patch.start()
        self.indexed_files_patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.session = uuid4()
        RepositorySnapshotService.save(make_snapshot())

    async def asyncTearDown(self):
        await self.client.aclose()
        self.indexed_files_patch.stop()
        self.vector_stats_patch.stop()
        self.storage_patch.stop()
        self.conversation_patch.stop()
        self.temporary.cleanup()

    async def test_dashboard_counts_questions_citations_topics_and_session_history(self):
        own = ConversationService.create("psf", "requests", self.session)
        self.assertTrue(ConversationService.append_exchange(
            own.conversation_id, "psf", "requests", self.session,
            "How does request authentication work?", answer_with_sources("requests", [
                "src/requests/api.py", "src/requests/sessions.py", "src/requests/api.py",
            ]),
        ))
        other_session = uuid4()
        other = ConversationService.create("psf", "requests", other_session)
        ConversationService.append_exchange(
            other.conversation_id, "psf", "requests", other_session,
            "How do cookies work?", answer_with_sources("requests", ["src/requests/cookies.py"]),
        )
        other_repo = ConversationService.create("pallets", "flask", self.session)
        ConversationService.append_exchange(
            other_repo.conversation_id, "pallets", "flask", self.session,
            "How do routes work?", answer_with_sources("flask", ["src/flask/app.py"]),
        )
        IndexingStatusService.mark_completed("psf", "requests", files=2, chunks=3, vectors=3)
        with patch("app.services.dashboard_service.VectorStoreService.get_repository_index_stats", return_value={
            "vectors": 3, "files": 2, "languages": {"Python": 2},
        }):
            response = await self.client.get("/api/repositories/dashboard", params={
                "repo_url": "https://github.com/psf/requests", "session_id": str(self.session),
            })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["indexing_status"], "indexed")
        self.assertEqual(body["indexed_files"], 2)
        self.assertEqual(body["indexed_chunks"], 3)
        self.assertIsNotNone(body["last_indexed_at"])
        self.assertEqual(body["total_questions"], 1)
        self.assertEqual(sum(day["question_count"] for day in body["questions_over_time"]), 1)
        self.assertEqual(body["frequently_referenced_files"][0]["path"], "src/requests/api.py")
        self.assertEqual(body["frequently_referenced_files"][0]["reference_count"], 1)
        self.assertIn("authentication", {topic["topic"] for topic in body["most_explored_topics"]})
        self.assertEqual(len(body["conversations"]), 1)
        self.assertEqual(body["recent_activity"][0]["repository"], "requests")
        self.assertEqual(body["recent_activity"][0]["sources"][0]["path"], "src/requests/api.py")
        self.assertTrue(body["architecture"])
        self.assertTrue(body["dependencies"])

    async def test_dashboard_isolates_repository_and_session_and_handles_empty_repo(self):
        ConversationService.create("psf", "requests", self.session)
        response = await self.client.get("/api/repositories/dashboard", params={
            "repo_url": "https://github.com/psf/requests", "session_id": str(uuid4()),
        })
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total_questions"], 0)
        self.assertEqual(body["conversations"], [])
        self.assertEqual(body["frequently_referenced_files"], [])

        empty_response = await self.client.get("/api/repositories/dashboard", params={
            "repo_url": "https://github.com/psf/empty", "session_id": str(self.session),
        })
        self.assertEqual(empty_response.status_code, 200, empty_response.text)
        empty = empty_response.json()
        self.assertEqual(empty["indexing_status"], "not_indexed")
        self.assertEqual(empty["indexed_files"], 0)
        self.assertEqual(empty["snapshot_files"], 0)
        self.assertIsNone(empty["architecture"])
        self.assertEqual(empty["conversations"], [])

    async def test_dashboard_rejects_invalid_repository_url(self):
        response = await self.client.get("/api/repositories/dashboard", params={
            "repo_url": "https://example.com/nope", "session_id": str(self.session),
        })
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
