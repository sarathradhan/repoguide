"""Integration test suite for Milestone 2: GitHub Repository Ingestion."""
import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.main import app


async def run_tests():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=90.0
    ) as client:
        # TEST 1: Standard Repository Ingestion (psf/requests)
        print("=== TEST 1: Standard Repository Ingestion (psf/requests) ===")
        r1 = await client.post(
            "/api/repositories/ingest", json={"repo_url": "https://github.com/psf/requests"}
        )
        assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text}"
        d1 = r1.json()
        assert d1["owner"] == "psf"
        assert d1["repository"] == "requests"
        assert d1["files_returned"] > 0
        assert any("__init__.py" in f["path"] for f in d1["files"])

        # Check content integrity
        init_file = next(f for f in d1["files"] if f["path"].endswith("__init__.py"))
        assert len(init_file["content"]) > 50
        assert init_file["language"] == "Python"
        print(f"  [PASS] Owner: {d1['owner']}, Repo: {d1['repository']}, Branch: {d1['default_branch']}, Stars: {d1['stars']}")
        print(f"         Found: {d1['total_source_files_found']}, Returned: {d1['files_returned']}, Truncated: {d1['files_truncated']}")

        # TEST 2: Invalid GitHub URLs
        print("\n=== TEST 2: Invalid GitHub URL Validation ===")
        r2 = await client.post(
            "/api/repositories/ingest", json={"repo_url": "https://gitlab.com/not/github"}
        )
        assert r2.status_code in (400, 422), f"Expected 400/422, got {r2.status_code}"
        print(f"  [PASS] Non-GitHub domain rejected with HTTP {r2.status_code}")

        r2b = await client.post(
            "/api/repositories/ingest", json={"repo_url": "invalid_url_string"}
        )
        assert r2b.status_code in (400, 422), f"Expected 400/422, got {r2b.status_code}"
        print(f"  [PASS] Malformed string rejected with HTTP {r2b.status_code}")

        # TEST 3: Non-existent Repository
        print("\n=== TEST 3: Non-existent Repository ===")
        r3 = await client.post(
            "/api/repositories/ingest",
            json={"repo_url": "https://github.com/github-nonexistent-user-991823/repo-not-found-772819"},
        )
        assert r3.status_code == 404, f"Expected 404, got {r3.status_code}"
        d3 = r3.json()
        assert "not found" in d3["detail"].lower()
        print(f"  [PASS] Returned 404 Not Found: '{d3['detail']}'")

        # TEST 4: Large Repository Truncation Limits (pallets/flask)
        print("\n=== TEST 4: Repository Ingestion & Truncation (pallets/flask) ===")
        r4 = await client.post(
            "/api/repositories/ingest", json={"repo_url": "https://github.com/pallets/flask"}
        )
        assert r4.status_code == 200, f"Expected 200, got {r4.status_code}: {r4.text}"
        d4 = r4.json()
        print(f"  [PASS] Flask: Found {d4['total_source_files_found']} files, returned {d4['files_returned']}")
        print(f"         Truncated: {d4['files_truncated']}, Reason: {d4['truncation_reason']}")

        # TEST 5: Health check regression test (ensure existing endpoints still work)
        print("\n=== TEST 5: Regression Check on Health & Root Endpoints ===")
        rh = await client.get("/api/health")
        assert rh.status_code == 200
        assert rh.json()["status"] == "healthy"
        rw = await client.get("/")
        assert rw.status_code == 200
        print("  [PASS] Existing health and root endpoints unaffected.")

        print("\n========================================================")
        print(">>> ALL MILESTONE 2 INTEGRATION TESTS PASSED (5/5) <<<")
        print("========================================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
