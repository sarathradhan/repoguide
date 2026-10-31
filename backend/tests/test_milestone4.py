"""Milestone 4 API and Groq integration tests using a deterministic mock provider."""
import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.core.config import settings
from app.main import app
from app.models.repository import SearchResultChunk
from app.services.groq_service import GroqAPIError, GroqService


class Milestone4Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    @staticmethod
    def chunk(similarity=0.82):
        return SearchResultChunk(
            chunk_id="psf_requests_auth_0",
            path="src/requests/auth.py",
            language="Python",
            start_line=12,
            end_line=28,
            content="class AuthBase:\n    def __call__(self, request):\n        return request",
            similarity_score=similarity,
            distance=round(1.0 - similarity, 4),
        )

    @patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1] * 384)
    @patch("app.services.indexing_service.VectorStoreService.search_repository")
    @patch("app.services.indexing_service.VectorStoreService.get_repository_default_branch", return_value="stable")
    @patch("app.services.indexing_service.GroqService.generate_answer", new_callable=AsyncMock)
    async def test_successful_answer_has_source_citations(self, generate, _branch, search, _embed):
        search.return_value = [self.chunk()]
        generate.return_value = "Authentication hooks are implemented by AuthBase [\u200bS1\u200b]."

        response = await self.client.post(
            "/api/repositories/ask",
            json={"repo_url": "https://github.com/psf/requests", "question": "How does authentication work?"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("[S1]", data["answer"])
        self.assertNotIn("Sources:", data["answer"])
        self.assertEqual(data["repository"], "requests")
        self.assertEqual(data["sources"][0]["path"], "src/requests/auth.py")
        self.assertEqual((data["sources"][0]["start_line"], data["sources"][0]["end_line"]), (12, 28))
        self.assertTrue(data["sources"][0]["url"].endswith("/blob/stable/src/requests/auth.py#L12-L28"))
        self.assertTrue(data["retrieved_context"]["context_sufficient"])
        self.assertEqual(data["retrieved_context"]["chunks_retrieved"], 1)
        generate.assert_awaited_once()

    @patch.object(settings, "GROQ_API_KEY", None)
    @patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1] * 384)
    @patch("app.services.indexing_service.VectorStoreService.search_repository")
    async def test_missing_api_key_returns_service_unavailable(self, search, _embed):
        search.return_value = [self.chunk()]
        response = await self.client.post(
            "/api/repositories/ask",
            json={"repo_url": "https://github.com/psf/requests", "question": "How does auth work?"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("GROQ_API_KEY", response.json()["detail"])

    @patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1] * 384)
    @patch("app.services.indexing_service.VectorStoreService.search_repository")
    @patch("app.services.indexing_service.GroqService.generate_answer", new_callable=AsyncMock)
    async def test_insufficient_context_returns_explicit_answer_without_groq(self, generate, search, _embed):
        search.return_value = [self.chunk(similarity=0.05)]
        response = await self.client.post(
            "/api/repositories/ask",
            json={"repo_url": "https://github.com/psf/requests", "question": "How does auth work?"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["retrieved_context"]["context_sufficient"])
        self.assertIn("couldn't find enough relevant information", data["answer"])
        generate.assert_not_awaited()

    async def test_invalid_repository_url_is_rejected(self):
        response = await self.client.post(
            "/api/repositories/ask",
            json={"repo_url": "https://example.com/not-a-repository", "question": "How does auth work?"},
        )
        self.assertEqual(response.status_code, 422)

    @patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1] * 384)
    @patch("app.services.indexing_service.VectorStoreService.search_repository", return_value=[])
    async def test_unindexed_repository_returns_not_found(self, _search, _embed):
        response = await self.client.post(
            "/api/repositories/ask",
            json={"repo_url": "https://github.com/psf/requests", "question": "How does auth work?"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("Index the repository", response.json()["detail"])

    @patch.object(settings, "GROQ_API_KEY", "unit-test-key")
    async def test_groq_request_uses_server_key_and_grounding_prompt(self):
        captured = {}

        class MockResponse:
            @staticmethod
            def raise_for_status():
                return None

            @staticmethod
            def json():
                return {"choices": [{"message": {"content": "AuthBase modifies the request [S1]."}}]}

        class MockClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def post(self, url, headers, json):
                captured.update(url=url, headers=headers, payload=json)
                return MockResponse()

        history = [
            {"role": "user", "content": "Where are auth hooks?"},
            {"role": "assistant", "content": "They are in AuthBase [S1]."},
        ]
        with patch("app.services.groq_service.httpx.AsyncClient", MockClient):
            answer = await GroqService.generate_answer(
                "How does auth work?", [self.chunk()], history
            )

        self.assertIn("[S1]", answer)
        self.assertEqual(captured["url"], f"{settings.GROQ_API_BASE_URL}/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer unit-test-key")
        self.assertEqual(captured["payload"]["model"], settings.GROQ_MODEL)
        self.assertIn("How does auth work?", captured["payload"]["messages"][1]["content"])
        self.assertIn("src/requests/auth.py:12-28", captured["payload"]["messages"][1]["content"])
        self.assertIn("Where are auth hooks?", captured["payload"]["messages"][1]["content"])
        self.assertNotIn("unit-test-key", answer)

    @patch.object(settings, "GROQ_API_KEY", "unit-test-key")
    async def test_unavailable_groq_model_returns_actionable_error(self):
        request = httpx.Request("POST", f"{settings.GROQ_API_BASE_URL}/chat/completions")
        response = httpx.Response(404, request=request)

        class MockClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def post(self, *_args, **_kwargs):
                raise httpx.HTTPStatusError("not found", request=request, response=response)

        with patch("app.services.groq_service.httpx.AsyncClient", MockClient):
            with self.assertRaises(GroqAPIError) as raised:
                await GroqService.generate_answer("question", [self.chunk()])
        self.assertIn("not enabled for this API key", str(raised.exception))

    @patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1] * 384)
    @patch("app.services.indexing_service.VectorStoreService.search_repository")
    @patch(
        "app.services.indexing_service.GroqService.generate_answer",
        new_callable=AsyncMock,
        side_effect=GroqAPIError(
            "Groq is rate limiting answer generation. Try again in about 9 seconds.",
            status_code=429,
        ),
    )
    async def test_groq_rate_limit_returns_actionable_http_429(self, _generate, search, _embed):
        search.return_value = [self.chunk()]
        response = await self.client.post(
            "/api/repositories/ask",
            json={
                "repo_url": "https://github.com/psf/requests",
                "question": "How does authentication work?",
            },
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn("rate limiting", response.json()["detail"])
        self.assertIn("9 seconds", response.json()["detail"])

    @patch.object(settings, "GROQ_API_KEY", "unit-test-key")
    async def test_groq_rate_limit_includes_retry_hint_without_leaking_provider_body(self):
        request = httpx.Request("POST", f"{settings.GROQ_API_BASE_URL}/chat/completions")
        response = httpx.Response(
            429,
            request=request,
            headers={"Retry-After": "12"},
            json={"error": {"code": "rate_limit_exceeded", "message": "Rate limit exceeded"}},
        )

        class MockClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return None

            async def post(self, *_args, **_kwargs):
                raise httpx.HTTPStatusError("rate limited", request=request, response=response)

        with patch("app.services.groq_service.httpx.AsyncClient", MockClient):
            with self.assertRaises(GroqAPIError) as raised:
                await GroqService.generate_answer("question", [self.chunk()])

        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("12 seconds", str(raised.exception))
        self.assertNotIn("unit-test-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
