"""Deterministic architecture extraction tests for several project layouts."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.core.config import settings
from app.main import app
from app.models.repository import RepositoryFile, RepositoryResponse
from app.services.architecture_service import ArchitectureService
from app.services.repository_snapshot_service import RepositorySnapshotService


def snapshot(owner, repository, files, branch="main"):
    models = [RepositoryFile(path=path, language=language, content=content, size=len(content.encode()))
              for path, language, content in files]
    return RepositoryResponse(
        owner=owner, repository=repository, description=None, default_branch=branch,
        stars=0, total_source_files_found=len(models), files_returned=len(models),
        files_truncated=False, truncation_reason=None, files=models,
    )


class ArchitectureExtractionTests(unittest.TestCase):
    def test_python_package_detects_routes_services_db_and_imports(self):
        project = snapshot("org", "py-api", [
            ("backend/app/main.py", "Python", """from fastapi import FastAPI
from app.services.user_service import UserService
import sqlite3
app = FastAPI()
@app.get('/health')
def health():
    return {'ok': True}
if __name__ == '__main__':
    pass
"""),
            ("backend/app/services/user_service.py", "Python", "class UserService:\n    pass\n"),
        ])
        result = ArchitectureService.analyze_files(project)
        types = [item.component_type for item in result.components]
        self.assertIn("entry_point", types)
        self.assertIn("route", types)
        self.assertIn("service", types)
        self.assertIn("database", types)
        self.assertTrue(any(edge.label == "imports" and edge.evidence_type == "detected" for edge in result.relationships))
        route = next(item for item in result.components if item.component_type == "route")
        self.assertIn("GET /health", route.label)
        self.assertIn("blob/main/backend/app/main.py#L", route.source_url)

    def test_javascript_service_layout_resolves_local_imports_and_external_db(self):
        project = snapshot("org", "web-api", [
            ("src/server.js", "JavaScript", """import express from 'express';
import { loadStatus } from './services/status';
const app = express();
app.get('/status', (req, res) => res.send(loadStatus()));
"""),
            ("src/services/status.js", "JavaScript", """import pg from 'pg';
class StatusService { load() {} }
"""),
        ])
        result = ArchitectureService.analyze_files(project)
        self.assertTrue(any(edge.label == "imports" and edge.source_path == "src/server.js" for edge in result.relationships))
        self.assertTrue(any(edge.label == "database integration" for edge in result.relationships))
        self.assertTrue(any(item.component_type == "route" and "GET /status" in item.label for item in result.components))
        entrypoint = next(item for item in result.components if item.path == "src/server.js")
        self.assertEqual(entrypoint.evidence_type, "inferred")

    def test_java_package_detects_controller_route_service_and_spring_data(self):
        project = snapshot("org", "java-api", [
            ("src/main/java/com/demo/CustomerController.java", "Java", """package com.demo;
import com.demo.CustomerService;
import org.springframework.data.repository.CrudRepository;
@RestController
class CustomerController {
  @GetMapping("/customers")
  public String list() { return "ok"; }
}
"""),
            ("src/main/java/com/demo/CustomerService.java", "Java", "class CustomerService { }\n"),
        ])
        result = ArchitectureService.analyze_files(project)
        self.assertTrue(any(item.component_type == "controller" for item in result.components))
        self.assertTrue(any(item.component_type == "service" for item in result.components))
        self.assertTrue(any(item.component_type == "route" and "/customers" in item.label for item in result.components))
        self.assertTrue(any(item.label == "Spring Data" for item in result.components))
        self.assertTrue(any(edge.label == "imports" and edge.source_path.endswith("CustomerController.java") for edge in result.relationships))

    def test_empty_repository_and_unsupported_files_are_explicit(self):
        empty = ArchitectureService.analyze_files(snapshot("org", "empty", []))
        self.assertEqual(empty.files_analyzed, 0)
        self.assertEqual(len(empty.components), 1)
        unsupported = ArchitectureService.analyze_files(snapshot("org", "data", [
            ("scripts/run.sh", "Shell", "#!/bin/sh\necho ok\n"),
        ]))
        self.assertEqual(unsupported.unsupported_files, ["scripts/run.sh"])
        self.assertEqual(unsupported.components[1].evidence_type, "detected")


class ArchitecturePersistenceAndApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(settings, "CHROMA_PERSIST_DIRECTORY", self.temp_dir.name)
        self.path_patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.path_patch.stop()
        self.temp_dir.cleanup()

    async def test_snapshot_round_trips_and_architecture_api_reuses_it(self):
        repo = snapshot("psf", "requests", [
            ("src/requests/api.py", "Python", "def get(url):\n    return url\n"),
        ])
        RepositorySnapshotService.save(repo)
        loaded = RepositorySnapshotService.get("PSF", "REQUESTS")
        self.assertEqual(loaded.files[0].content, repo.files[0].content)
        with patch("app.services.architecture_service.GitHubService.ingest_repository", new_callable=AsyncMock) as ingest:
            response = await self.client.post("/api/repositories/architecture", json={"repo_url": "https://github.com/psf/requests"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["files_analyzed"], 1)
        ingest.assert_not_awaited()

    async def test_architecture_api_validates_repo_url(self):
        response = await self.client.post("/api/repositories/architecture", json={"repo_url": "https://example.com/nope"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
