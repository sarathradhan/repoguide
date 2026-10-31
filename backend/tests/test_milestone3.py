"""Comprehensive test suite for Milestone 3: Chunking, Embeddings, ChromaDB, and Search."""
import os
import shutil
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.models.repository import RepositoryFile
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService, _chroma_client


def run_milestone3_tests():
    print("\n========================================================")
    print(">>> RUNNING MILESTONE 3 AUTOMATED TEST SUITE (11 TESTS) <<<")
    print("========================================================")

    # -------------------------------------------------------------------------
    # TEST 1: Chunking a Python file
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Chunking a Python file...")
    py_code = """import os
import sys

class RequestHandler:
    def __init__(self, timeout=30):
        self.timeout = timeout

    def send(self, url, headers=None):
        \"\"\"Send an HTTP request to the target url.\"\"\"
        if not url:
            raise ValueError("URL cannot be empty")
        return {"status": 200, "url": url}

def helper():
    return True
"""
    py_file = RepositoryFile(
        path="src/network/handler.py",
        language="Python",
        content=py_code,
        size=len(py_code.encode("utf-8")),
    )
    py_chunks = ChunkingService.chunk_file("test_owner", "test_repo", py_file)
    assert len(py_chunks) >= 1, "Expected at least 1 Python chunk"
    assert py_chunks[0].language == "Python"
    assert py_chunks[0].path == "src/network/handler.py"
    assert py_chunks[0].start_line == 1
    assert py_chunks[0].end_line >= 10
    print(f"  PASS: Generated {len(py_chunks)} Python chunk(s), lines {py_chunks[0].start_line}-{py_chunks[0].end_line}")

    # -------------------------------------------------------------------------
    # TEST 3: Accurate source line ranges across multiple overlapping chunks
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Checking source line ranges across overlapping chunks...")
    source = "\n".join(
        f"def function_{i}():\n    return 'value_{i}'" for i in range(45)
    ) + "\n"
    line_file = RepositoryFile(
        path="src/line_ranges.py",
        language="Python",
        content=source,
        size=len(source.encode("utf-8")),
    )
    original_size, original_overlap = settings.CHUNK_SIZE, settings.CHUNK_OVERLAP
    try:
        settings.CHUNK_SIZE, settings.CHUNK_OVERLAP = 180, 30
        line_chunks = ChunkingService.chunk_file("test_owner", "test_repo", line_file)
    finally:
        settings.CHUNK_SIZE, settings.CHUNK_OVERLAP = original_size, original_overlap
    assert len(line_chunks) > 2, "Expected multiple chunks for line-range validation"
    cursor = 0
    for chunk in line_chunks:
        position = source.find(chunk.content, cursor)
        assert position >= 0, f"Could not locate chunk in source: {chunk.chunk_index}"
        expected_start = source[:position].count("\n") + 1
        end_position = position + len(chunk.content)
        expected_end = source[:end_position].count("\n") + (
            0 if source[end_position - 1:end_position] == "\n" else 1
        )
        assert (chunk.start_line, chunk.end_line) == (expected_start, expected_end), (
            f"Incorrect line range for chunk {chunk.chunk_index}: "
            f"got {chunk.start_line}-{chunk.end_line}, expected {expected_start}-{expected_end}"
        )
        cursor = position + 1
    print(f"  PASS: Verified exact source lines for {len(line_chunks)} overlapping chunks")

    # -------------------------------------------------------------------------
    # TEST 2: Chunking a Java file
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Chunking a Java file...")
    java_code = """package com.repoguide.service;

import java.util.List;

public class CodeProcessor {
    private final String model;

    public CodeProcessor(String model) {
        this.model = model;
    }

    public int processTokens(List<String> tokens) {
        int count = 0;
        for (String token : tokens) {
            count += token.length();
        }
        return count;
    }
}
"""
    java_file = RepositoryFile(
        path="src/main/java/com/repoguide/CodeProcessor.java",
        language="Java",
        content=java_code,
        size=len(java_code.encode("utf-8")),
    )
    java_chunks = ChunkingService.chunk_file("test_owner", "test_repo", java_file)
    assert len(java_chunks) >= 1, "Expected at least 1 Java chunk"
    assert java_chunks[0].language == "Java"
    assert "CodeProcessor" in java_chunks[0].content
    print(f"  PASS: Generated {len(java_chunks)} Java chunk(s), lines {java_chunks[0].start_line}-{java_chunks[0].end_line}")

    # -------------------------------------------------------------------------
    # TEST 4: Embedding generation (all-MiniLM-L6-v2)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Generating embeddings with all-MiniLM-L6-v2...")
    sample_texts = [
        "def send_http_request(url, headers): return 200",
        "public class DatabaseConnector { void connect() {} }",
    ]
    embeddings = EmbeddingService.embed_texts(sample_texts)
    assert len(embeddings) == 2, "Expected 2 embeddings"
    assert len(embeddings[0]) == 384, f"Expected 384 dimensions, got {len(embeddings[0])}"
    assert len(embeddings[1]) == 384, f"Expected 384 dimensions, got {len(embeddings[1])}"

    query_vec = EmbeddingService.embed_query("How to make an HTTP request?")
    assert len(query_vec) == 384, "Query vector must match 384 dimensions"
    print("  PASS: Generated 384-dimensional dense vectors for chunks and query")

    # -------------------------------------------------------------------------
    # TEST 4: ChromaDB persistence on disk
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing ChromaDB local persistence on disk...")
    test_owner = "org_alpha"
    test_repo = "demo_project"
    chunks = py_chunks + java_chunks
    chunk_embeddings = EmbeddingService.embed_texts([c.content for c in chunks])

    stored_count = VectorStoreService.store_chunks(test_owner, test_repo, chunks, chunk_embeddings)
    assert stored_count == len(chunks), f"Expected {len(chunks)} vectors stored, got {stored_count}"

    persist_dir = Path(settings.CHROMA_PERSIST_DIRECTORY)
    assert persist_dir.exists(), f"ChromaDB directory '{persist_dir}' does not exist on disk"
    print(f"  PASS: Persisted {stored_count} vectors into ChromaDB directory: {persist_dir}")

    # -------------------------------------------------------------------------
    # TEST 5: Duplicate indexing prevention (idempotent / clean replacement)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Duplicate indexing prevention...")
    # Re-store the exact same chunks
    stored_again = VectorStoreService.store_chunks(test_owner, test_repo, chunks, chunk_embeddings)
    col_name = VectorStoreService.get_collection_name(test_owner, test_repo)
    client = VectorStoreService.get_client()
    col = client.get_collection(col_name)
    assert col.count() == len(chunks), f"Expected count {len(chunks)}, but found {col.count()} (duplicated vectors!)"
    print(f"  PASS: Re-indexing replaced collection cleanly; total count remains {col.count()}")

    # -------------------------------------------------------------------------
    # TEST 6: Repository-specific search isolation
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Repository-specific search isolation...")
    # Index a separate repository "org_beta/secret_repo"
    secret_code = "def authenticate_admin_secret_key(): return 'SECRET_12345'"
    secret_file = RepositoryFile(path="secret.py", language="Python", content=secret_code, size=len(secret_code))
    secret_chunks = ChunkingService.chunk_file("org_beta", "secret_repo", secret_file)
    secret_emb = EmbeddingService.embed_texts([c.content for c in secret_chunks])
    VectorStoreService.store_chunks("org_beta", "secret_repo", secret_chunks, secret_emb)

    # Search in org_alpha/demo_project for "secret key"
    query_secret = EmbeddingService.embed_query("authenticate admin secret key")
    alpha_results = VectorStoreService.search_repository(test_owner, test_repo, query_secret, top_k=5)

    # Verify no leaks from org_beta
    for res in alpha_results:
        assert "secret_repo" not in res.chunk_id
        assert "SECRET_12345" not in res.content
    print("  PASS: Search results isolated strictly to requested repository collection")

    # -------------------------------------------------------------------------
    # TEST 7: Empty repository handling
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Handling empty files and empty repository...")
    empty_file = RepositoryFile(path="empty.py", language="Python", content="", size=0)
    empty_chunks = ChunkingService.chunk_file("org_empty", "empty_repo", empty_file)
    assert len(empty_chunks) == 0, "Empty file should yield 0 chunks"

    empty_stored = VectorStoreService.store_chunks("org_empty", "empty_repo", [], [])
    assert empty_stored == 0, "Empty list should return 0 vectors stored"
    print("  PASS: Gracefully handled empty files and empty repository")

    # -------------------------------------------------------------------------
    # TEST 8: Re-indexing an updated repository with fewer files
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Re-indexing an updated repository (old chunks removed)...")
    single_file = RepositoryFile(path="new_only.py", language="Python", content="def new_feature(): pass", size=24)
    new_chunks = ChunkingService.chunk_file(test_owner, test_repo, single_file)
    new_emb = EmbeddingService.embed_texts([c.content for c in new_chunks])
    VectorStoreService.store_chunks(test_owner, test_repo, new_chunks, new_emb)

    col = client.get_collection(col_name)
    assert col.count() == len(new_chunks), f"Expected {len(new_chunks)} vectors after update, found {col.count()}"
    print(f"  PASS: Obsolete chunks purged; updated collection count is {col.count()}")

    # -------------------------------------------------------------------------
    # TEST 9: Semantic search accuracy (retrieval of expected code)
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Semantic search accuracy and ranking...")
    # Re-index demo_project with py_chunks
    VectorStoreService.store_chunks(test_owner, test_repo, py_chunks, EmbeddingService.embed_texts([c.content for c in py_chunks]))

    q_vec = EmbeddingService.embed_query("Send an HTTP request to a target url")
    search_results = VectorStoreService.search_repository(test_owner, test_repo, q_vec, top_k=3)
    assert len(search_results) > 0, "Expected search results"
    top_match = search_results[0]
    assert "send" in top_match.content.lower()
    assert top_match.path == "src/network/handler.py"
    assert top_match.similarity_score > 0.4
    print(f"  PASS: Top match: {top_match.path} (Similarity: {top_match.similarity_score * 100:.1f}%)")

    # -------------------------------------------------------------------------
    # TEST 10: Persistence across backend / client restart
    # -------------------------------------------------------------------------
    print("\n[TEST 11] ChromaDB persistence after simulating client restart...")
    # Reset in-memory client
    import app.services.vector_store as vs_module
    vs_module._chroma_client = None

    # Retrieve anew from disk
    new_client = VectorStoreService.get_client()
    reloaded_col = new_client.get_collection(col_name)
    assert reloaded_col.count() == len(py_chunks), "Vectors failed to persist on disk across reload"
    reloaded_results = VectorStoreService.search_repository(test_owner, test_repo, q_vec, top_k=1)
    assert len(reloaded_results) == 1
    assert reloaded_results[0].path == "src/network/handler.py"
    print("  PASS: Data persisted on disk and queryable after client restart")

    print("\n========================================================")
    print(">>> ALL 11 MILESTONE 3 TESTS COMPLETED AND PASSED! <<<")
    print("========================================================\n")


if __name__ == "__main__":
    run_milestone3_tests()

