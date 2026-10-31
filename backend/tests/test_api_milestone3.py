"""API integration tests for Milestone 3 endpoints: /api/repositories/index & /api/repositories/search."""
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from app.main import app


async def test_api_milestone3():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=90.0
    ) as client:
        print("\n--- Testing POST /api/repositories/index (psf/requests) ---")
        index_res = await client.post(
            "/api/repositories/index", json={"repo_url": "https://github.com/psf/requests"}
        )
        assert index_res.status_code == 200, f"Index failed: {index_res.status_code} {index_res.text}"
        data = index_res.json()
        print("Index Response:", data)
        assert data["success"] is True
        assert data["repository"] == "requests"
        assert data["files_processed"] > 0
        assert data["chunks_created"] > 0
        assert data["vectors_stored"] == data["chunks_created"]
        print(f"  PASS: Indexed {data['files_processed']} files into {data['chunks_created']} chunks/vectors")

        print("\n--- Testing POST /api/repositories/search ---")
        search_res = await client.post(
            "/api/repositories/search",
            json={
                "repo_url": "https://github.com/psf/requests",
                "query": "Where is the HTTP request logic implemented?",
                "top_k": 3,
            },
        )
        assert search_res.status_code == 200, f"Search failed: {search_res.status_code} {search_res.text}"
        s_data = search_res.json()
        print("Search Results Count:", s_data["results_count"])
        assert s_data["results_count"] > 0
        top_match = s_data["results"][0]
        print(f"  Top Result: {top_match['path']} (Line {top_match['start_line']}-{top_match['end_line']}, Score: {top_match['similarity_score']})")
        assert "api.py" in top_match["path"] or "sessions.py" in top_match["path"] or "requests" in top_match["path"]
        assert top_match["similarity_score"] > 0.3
        print("  PASS: Semantic search returned relevant code chunks with line ranges and scores.")

        print("\n--- Testing Search in Non-Indexed Repository ---")
        empty_search = await client.post(
            "/api/repositories/search",
            json={
                "repo_url": "https://github.com/nonexistent-org/unindexed-repo",
                "query": "test query",
                "top_k": 3,
            },
        )
        assert empty_search.status_code == 200
        assert empty_search.json()["results_count"] == 0
        print("  PASS: Unindexed repository gracefully returns 0 results.")

        print("\n>>> ALL API TESTS PASSED! <<<\n")


if __name__ == "__main__":
    asyncio.run(test_api_milestone3())

