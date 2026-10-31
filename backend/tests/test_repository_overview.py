"""Repository-level RAG context extraction, persistence, and intent routing tests."""
from pathlib import Path
import asyncio
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.models.repository import RepositoryFile, RepositoryResponse
from app.services.indexing_service import IndexingService
from app.services.question_intent_service import QuestionIntentService
from app.services.repository_overview_service import RepositoryOverviewService
from app.services.code_parser import CodeParser


def snapshot(readme="A small API for analyzing images.\n\n## Features\n- Detects objects\n"):
    files = [
        RepositoryFile(path="README.md", language="Markdown", content=readme, size=len(readme)),
        RepositoryFile(path="pyproject.toml", language="TOML", content=(
            '[project]\nname = "fall-detection"\ndescription = "Detects falls"\n'
            'dependencies = ["fastapi>=0.100", "pydantic>=2"]\n'
        ), size=100),
        RepositoryFile(path="app/main.py", language="Python", content=(
            "from fastapi import FastAPI\napp = FastAPI()\n"
        ), size=50),
        RepositoryFile(path="app/db.py", language="Python", content="def connect(): pass\n", size=20),
    ]
    return RepositoryResponse(
        owner="example", repository="falls", description="Fall detection service",
        default_branch="main", stars=0, total_source_files_found=len(files),
        files_returned=len(files), files_truncated=False, truncation_reason=None, files=files,
    )


class RepositoryOverviewTests(unittest.TestCase):
    def test_ingestion_keeps_readme_and_dependency_manifests_within_configured_file_limit(self):
        files = [
            {"type": "blob", "path": "README.md", "size": 500},
            {"type": "blob", "path": "pyproject.toml", "size": 200},
            {"type": "blob", "path": "requirements-dev.txt", "size": 100},
            *({"type": "blob", "path": f"src/module_{index}.py", "size": 100} for index in range(130)),
        ]
        with patch.object(settings, "MAX_SOURCE_FILES", 500):
            selected, total, truncated, _ = CodeParser.filter_tree(files)
        self.assertEqual(total, 133)
        self.assertEqual(len(selected), 133)
        self.assertFalse(truncated)

    def test_extracts_readme_metadata_languages_frameworks_and_entry_points(self):
        overview = RepositoryOverviewService.build(snapshot())
        self.assertIn("README.md", overview.readme_paths)
        self.assertEqual(overview.project_name, "fall-detection")
        self.assertEqual(overview.project_description, "Detects falls")
        self.assertEqual(overview.languages["Python"], 2)
        self.assertIn("FastAPI", overview.frameworks)
        self.assertIn("app/main.py", overview.entry_points)
        self.assertIn("README.md", [item.path for item in overview.evidence])
        self.assertIn("pyproject.toml", [item.path for item in overview.evidence])

    def test_overview_persists_by_repository_and_rebuilds_when_content_changes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(settings, "CHROMA_PERSIST_DIRECTORY", directory):
            first = RepositoryOverviewService.get_or_build(snapshot())
            second = RepositoryOverviewService.get_or_build(snapshot())
            changed = RepositoryOverviewService.get_or_build(snapshot("A different computer vision project.\n"))
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)

    def test_detects_all_requested_question_intents(self):
        cases = {
            "What is this project about?": "broad",
            "What are its main features?": "broad",
            "What technologies does it use?": "technology",
            "Explain the overall architecture": "architecture",
            "How does authentication work?": "implementation",
            "Where is the database connection implemented?": "implementation",
            "What does app/db.py implement?": "file_specific",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(QuestionIntentService.detect(question), expected)

    def test_broad_question_uses_overview_citations_without_semantic_threshold(self):
        from app.models.repository import RepositoryContextChunk

        data = snapshot()
        overview = RepositoryOverviewService.build(data)
        evidence = RepositoryContextChunk(
            chunk_id="readme_evidence", path="README.md", language="Markdown",
            start_line=1, end_line=4, content=data.files[0].content, context_type="overview",
        )
        async def run():
            with patch("app.services.indexing_service.VectorStoreService.has_repository_index", return_value=True), \
                 patch("app.services.indexing_service.VectorStoreService.get_repository_default_branch", return_value="main"), \
                 patch("app.services.indexing_service.VectorStoreService.search_repository") as search, \
                 patch("app.services.indexing_service.EmbeddingService.embed_query") as embed, \
                 patch("app.services.indexing_service.RepositorySnapshotService.get", return_value=data), \
                 patch("app.services.indexing_service.RepositoryOverviewService.get_or_build", return_value=overview), \
                 patch("app.services.indexing_service.RepositoryOverviewService.context_for_intent", return_value=[evidence]), \
                 patch("app.services.indexing_service.GroqService.fit_context", return_value=[evidence]), \
                 patch("app.services.indexing_service.GroqService.generate_answer", new_callable=AsyncMock, return_value="A fall detection service [S1]."):
                answer = await IndexingService.ask_repository(
                    "https://github.com/example/falls", "What is this project about?"
                )
                search.assert_not_called()
                embed.assert_not_called()
                return answer

        answer = asyncio.run(run())
        self.assertIn("[S1]", answer.answer)
        self.assertEqual(answer.sources[0].path, "README.md")
        self.assertEqual(answer.sources[0].context_type, "overview")
        self.assertTrue(answer.retrieved_context.context_sufficient)
        self.assertTrue(answer.retrieved_context.repository_overview_used)
        self.assertEqual(answer.retrieved_context.question_intent, "broad")

    def test_technology_question_uses_manifest_over_low_similarity_code_hits(self):
        from app.models.repository import RepositoryContextChunk, SearchResultChunk

        data = snapshot()
        overview = RepositoryOverviewService.build(data)
        manifest = RepositoryContextChunk(
            chunk_id="manifest", path="pyproject.toml", language="TOML",
            start_line=1, end_line=4, content=data.files[1].content, context_type="overview",
        )
        weak_code = SearchResultChunk(
            chunk_id="weak", path="app/db.py", language="Python", start_line=1, end_line=1,
            content="def connect(): pass", similarity_score=0.04, distance=0.96,
        )

        async def run():
            with patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1]), \
                 patch("app.services.indexing_service.VectorStoreService.search_repository", return_value=[weak_code]), \
                 patch("app.services.indexing_service.VectorStoreService.get_repository_default_branch", return_value="main"), \
                 patch("app.services.indexing_service.RepositorySnapshotService.get", return_value=data), \
                 patch("app.services.indexing_service.RepositoryOverviewService.get_or_build", return_value=overview), \
                 patch("app.services.indexing_service.RepositoryOverviewService.context_for_intent", return_value=[manifest]), \
                 patch("app.services.indexing_service.GroqService.fit_context", side_effect=lambda _q, items, _h: items), \
                 patch("app.services.indexing_service.GroqService.generate_answer", new_callable=AsyncMock, return_value="The manifest declares FastAPI [S1]."):
                return await IndexingService.ask_repository(
                    "https://github.com/example/falls", "What technologies does it use?"
                )

        answer = asyncio.run(run())
        self.assertTrue(answer.retrieved_context.context_sufficient)
        self.assertTrue(answer.retrieved_context.repository_overview_used)
        self.assertEqual(answer.retrieved_context.question_intent, "technology")
        self.assertEqual(answer.sources[0].path, "pyproject.toml")
        self.assertEqual(answer.sources[0].context_type, "overview")

    def test_architecture_question_uses_source_backed_architecture_facts(self):
        from app.models.repository import RepositoryContextChunk, SearchResultChunk

        data = snapshot()
        overview = RepositoryOverviewService.build(data)
        fact = RepositoryContextChunk(
            chunk_id="arch-entry", path="app/main.py", language="Python",
            start_line=1, end_line=2,
            content="Detected entry point component.\nfrom fastapi import FastAPI\napp = FastAPI()",
            context_type="architecture",
        )
        weak_code = SearchResultChunk(
            chunk_id="weak", path="app/db.py", language="Python", start_line=1, end_line=1,
            content="def connect(): pass", similarity_score=0.04, distance=0.96,
        )

        async def run():
            with patch("app.services.indexing_service.EmbeddingService.embed_query", return_value=[0.1]), \
                 patch("app.services.indexing_service.VectorStoreService.search_repository", return_value=[weak_code]), \
                 patch("app.services.indexing_service.VectorStoreService.get_repository_default_branch", return_value="main"), \
                 patch("app.services.indexing_service.RepositorySnapshotService.get", return_value=data), \
                 patch("app.services.indexing_service.RepositoryOverviewService.get_or_build", return_value=overview), \
                 patch("app.services.indexing_service.RepositoryOverviewService.context_for_intent", return_value=[]), \
                 patch("app.services.indexing_service.RepositoryOverviewService.architecture_context", return_value=[fact]), \
                 patch("app.services.indexing_service.GroqService.fit_context", side_effect=lambda _q, items, _h: items), \
                 patch("app.services.indexing_service.GroqService.generate_answer", new_callable=AsyncMock, return_value="The application entry point is app/main.py [S1]."):
                return await IndexingService.ask_repository(
                    "https://github.com/example/falls", "Explain the overall architecture."
                )

        answer = asyncio.run(run())
        self.assertTrue(answer.retrieved_context.context_sufficient)
        self.assertTrue(answer.retrieved_context.architecture_context_used)
        self.assertEqual(answer.sources[0].path, "app/main.py")
        self.assertEqual(answer.sources[0].context_type, "architecture")


if __name__ == "__main__":
    unittest.main()
