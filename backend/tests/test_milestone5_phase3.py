"""Dependency extraction tests across supported repository languages."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.main import app
from app.models.repository import RepositoryFile, RepositoryResponse
from app.services.dependency_service import DependencyAnalysisService


def snapshot(owner, repo, files):
    models = [RepositoryFile(path=path, language=language, content=content, size=len(content.encode()))
              for path, language, content in files]
    return RepositoryResponse(owner=owner, repository=repo, description=None, default_branch="main",
                              stars=0, total_source_files_found=len(models), files_returned=len(models),
                              files_truncated=False, truncation_reason=None, files=models)


class DependencyExtractionTests(unittest.TestCase):
    def test_python_relative_import_lines_cycles_and_unresolved(self):
        project = snapshot("org", "python", [
            ("pkg/__init__.py", "Python", ""),
            ("pkg/a.py", "Python", "from . import b\nfrom .missing import item\n"),
            ("pkg/b.py", "Python", "from .a import value\nvalue = 1\n"),
            ("standalone.py", "Python", "value = 2\n"),
        ])
        result = DependencyAnalysisService.analyze_files(project)
        self.assertEqual({(edge.source, edge.target, edge.source_line) for edge in result.edges}, {
            ("pkg/a.py", "pkg/__init__.py", 1), ("pkg/a.py", "pkg/b.py", 1),
            ("pkg/b.py", "pkg/a.py", 1),
        })
        self.assertEqual(result.unresolved_imports[0].imported_name, ".missing")
        self.assertEqual(result.unresolved_imports[0].source_line, 2)
        self.assertEqual(result.cycles[0].paths, ["pkg/a.py", "pkg/b.py"])
        self.assertIn("standalone.py", result.isolated_files)
        self.assertIn("#L1", result.edges[0].source_url)

    def test_python_absolute_import_resolves_under_source_root(self):
        project = snapshot("org", "python-roots", [
            ("backend/app/main.py", "Python", "from app.services.worker import run\n"),
            ("backend/app/services/worker.py", "Python", "def run(): pass\n"),
        ])
        result = DependencyAnalysisService.analyze_files(project)
        self.assertEqual([(edge.source, edge.target) for edge in result.edges], [
            ("backend/app/main.py", "backend/app/services/worker.py"),
        ])

    def test_javascript_and_typescript_relative_imports_resolve(self):
        project = snapshot("org", "web", [
            ("src/index.js", "JavaScript", "import view from './view';\nconst x = require('./util');\n"),
            ("src/view.tsx", "React TSX", "export default function View() {}\n"),
            ("src/util.ts", "TypeScript", "export const x = 1;\n"),
        ])
        result = DependencyAnalysisService.analyze_files(project)
        self.assertEqual({(edge.source, edge.target) for edge in result.edges}, {
            ("src/index.js", "src/view.tsx"), ("src/index.js", "src/util.ts"),
        })
        self.assertEqual(len(result.unresolved_imports), 0)

    def test_java_local_import_and_external_import_are_distinguished(self):
        project = snapshot("org", "java", [
            ("src/main/java/com/demo/A.java", "Java", "package com.demo;\nimport com.demo.B;\nimport java.util.List;\nclass A {}\n"),
            ("src/main/java/com/demo/B.java", "Java", "package com.demo;\nclass B {}\n"),
            ("src/main/java/com/demo/Unused.java", "Java", "class Unused {}\n"),
        ])
        result = DependencyAnalysisService.analyze_files(project)
        self.assertEqual([(edge.source, edge.target, edge.source_line) for edge in result.edges], [
            ("src/main/java/com/demo/A.java", "src/main/java/com/demo/B.java", 2),
        ])
        self.assertIn("src/main/java/com/demo/Unused.java", result.isolated_files)

    def test_unresolved_relative_js_and_missing_class_in_local_java_package(self):
        project = snapshot("org", "unresolved", [
            ("web/app.js", "JavaScript", "import x from './missing.js';\n"),
            ("java/com/demo/A.java", "Java", "package com.demo;\nimport com.demo.Missing;\n"),
        ])
        result = DependencyAnalysisService.analyze_files(project)
        self.assertEqual({item.imported_name for item in result.unresolved_imports}, {"./missing.js", "com.demo.Missing"})

    def test_large_graph_is_capped_and_repository_metadata_isolated(self):
        files = [(f"src/file_{number}.py", "Python", "pass\n") for number in range(30)]
        project = snapshot("org", "bounded", files)
        result = DependencyAnalysisService.analyze_files(project, max_files=20)
        self.assertEqual(result.files_analyzed, 20)
        self.assertEqual(result.total_source_files, 30)
        self.assertTrue(result.files_truncated)
        self.assertEqual(result.repository, "bounded")


class DependencyApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_endpoint_reads_snapshot_and_returns_repository_scoped_graph(self):
        project = snapshot("psf", "requests", [
            ("src/requests/a.py", "Python", "from . import b\n"),
            ("src/requests/b.py", "Python", "pass\n"),
        ])
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.services.dependency_service.RepositorySnapshotService.get", return_value=project), \
                 patch("app.services.dependency_service.VectorStoreService.get_repository_files", return_value=[]), \
                 patch("app.services.dependency_service.GitHubService.ingest_repository") as ingest:
                response = await client.post("/api/repositories/dependencies", json={
                    "repo_url": "https://github.com/psf/requests", "max_files": 20,
                })
                ingest.assert_not_called()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["repository"], "requests")
        self.assertEqual(body["edges"][0]["target"], "src/requests/b.py")
        self.assertEqual(body["edges"][0]["evidence_type"], "detected")

    async def test_endpoint_keeps_repository_graphs_isolated(self):
        projects = {
            ("psf", "requests"): snapshot("psf", "requests", [("requests/a.py", "Python", "from . import b\n"), ("requests/b.py", "Python", "pass\n")]),
            ("pallets", "flask"): snapshot("pallets", "flask", [("flask/app.py", "Python", "pass\n")]),
        }
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.services.dependency_service.RepositorySnapshotService.get", side_effect=lambda owner, repo: projects[(owner.lower(), repo.lower())]), \
                 patch("app.services.dependency_service.VectorStoreService.get_repository_files", return_value=[]):
                first = await client.post("/api/repositories/dependencies", json={"repo_url": "https://github.com/psf/requests"})
                second = await client.post("/api/repositories/dependencies", json={"repo_url": "https://github.com/pallets/flask"})
        self.assertEqual(first.json()["repository"], "requests")
        self.assertEqual(second.json()["repository"], "flask")
        self.assertEqual([node["path"] for node in second.json()["nodes"]], ["flask/app.py"])
        self.assertEqual(second.json()["edges"], [])


if __name__ == "__main__":
    unittest.main()
