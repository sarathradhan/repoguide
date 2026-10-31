"""Milestone 5 Phase 1 conversation API tests."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.core.config import settings
from app.main import app
from app.models.repository import SearchResultChunk
from app.services.conversation_service import SuggestedQuestionService


class Milestone5Phase1Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(settings, "CONVERSATIONS_DB_PATH", str(Path(self.temp_dir.name) / "conversations.sqlite3"))
        self.db_patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.repo_url = "https://github.com/psf/requests"
        self.session_id = str(uuid4())

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    async def create_conversation(self):
        response = await self.client.post("/api/repositories/conversations", json={
            "repo_url": self.repo_url, "session_id": self.session_id,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["conversation_id"]

    async def test_conversation_persists_and_isolated_by_repo_and_session(self):
        conversation_id = await self.create_conversation()
        own = await self.client.get("/api/repositories/conversations", params={
            "repo_url": self.repo_url, "session_id": self.session_id,
        })
        other_session = await self.client.get("/api/repositories/conversations", params={
            "repo_url": self.repo_url, "session_id": str(uuid4()),
        })
        other_repo = await self.client.get("/api/repositories/conversations", params={
            "repo_url": "https://github.com/pallets/flask", "session_id": self.session_id,
        })
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()["conversations"][0]["conversation_id"], conversation_id)
        self.assertEqual(other_session.json()["conversations"], [])
        self.assertEqual(other_repo.json()["conversations"], [])
        hidden = await self.client.get(f"/api/repositories/conversations/{conversation_id}", params={
            "repo_url": self.repo_url, "session_id": str(uuid4()),
        })
        self.assertEqual(hidden.status_code, 404)

    async def test_followup_uses_persisted_history_and_saves_citations(self):
        conversation_id = await self.create_conversation()
        chunk = SearchResultChunk(
            chunk_id="chunk-1", path="src/requests/auth.py", language="Python",
            start_line=9, end_line=21,
            content="class AuthBase:\n    def __call__(self, request): return request",
            similarity_score=0.8, distance=0.2,
        )
        with patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1] * 384), \
             patch("app.services.indexing_service.VectorStoreService.search_repository", return_value=[chunk]), \
             patch("app.services.indexing_service.VectorStoreService.get_repository_default_branch", return_value="main"), \
             patch("app.services.indexing_service.GroqService.generate_answer", new_callable=AsyncMock) as generate:
            generate.side_effect = [
                "Authentication uses AuthBase [S1].",
                "AuthBase is called through the auth hook [S1].",
            ]
            for question in ("How does authentication work?", "Where is that hook called?"):
                response = await self.client.post("/api/repositories/ask", json={
                    "repo_url": self.repo_url,
                    "question": question,
                    "session_id": self.session_id,
                    "conversation_id": conversation_id,
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["conversation_id"], conversation_id)
                self.assertIn("[S1]", response.json()["answer"])
            second_history = generate.await_args_list[1].args[2]

        self.assertEqual([turn["role"] for turn in second_history], ["user", "assistant"])
        self.assertEqual(second_history[0]["content"], "How does authentication work?")
        detail = await self.client.get(f"/api/repositories/conversations/{conversation_id}", params={
            "repo_url": self.repo_url, "session_id": self.session_id,
        })
        messages = detail.json()["messages"]
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[1]["sources"][0]["path"], "src/requests/auth.py")
        self.assertEqual((messages[1]["sources"][0]["start_line"], messages[1]["sources"][0]["end_line"]), (9, 21))
        self.assertTrue(messages[1]["sources"][0]["url"].endswith("#L9-L21"))

    async def test_ask_rejects_conversation_from_other_session(self):
        conversation_id = await self.create_conversation()
        response = await self.client.post("/api/repositories/ask", json={
            "repo_url": self.repo_url,
            "question": "How does authentication work?",
            "session_id": str(uuid4()),
            "conversation_id": conversation_id,
        })
        self.assertEqual(response.status_code, 404)

    def test_suggestions_come_from_indexed_source_declarations(self):
        suggestions = SuggestedQuestionService.from_chunks([
            {"path": "src/auth.py", "language": "Python", "content": "class AuthHandler:\n    def apply_auth(self): pass"}
        ], limit=5)
        self.assertIn("What does `AuthHandler` do?", suggestions)
        self.assertIn("What is implemented in `src/auth.py`?", suggestions)

    @patch("app.routes.repository.VectorStoreService.get_repository_chunks")
    async def test_suggestions_api_uses_only_indexed_repo_content(self, get_chunks):
        get_chunks.return_value = [{
            "path": "src/auth.py", "language": "Python",
            "content": "class AuthHandler:\n    def apply_auth(self): pass",
        }]
        response = await self.client.get("/api/repositories/suggestions", params={"repo_url": self.repo_url})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("What does `AuthHandler` do?", response.json()["suggestions"])
        get_chunks.return_value = []
        empty = await self.client.get("/api/repositories/suggestions", params={"repo_url": self.repo_url})
        self.assertEqual(empty.status_code, 404)

if __name__ == "__main__":
    unittest.main()
