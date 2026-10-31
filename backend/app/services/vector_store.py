"""Vector database service using persistent ChromaDB."""
import logging
import hashlib
from pathlib import Path
import re
import threading
from typing import Dict, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.models.repository import CodeChunk, RepositoryFile, SearchResultChunk

logger = logging.getLogger("repoguide.vector_store")

_client_lock = threading.Lock()
_chroma_client: Optional[chromadb.PersistentClient] = None


class VectorStoreService:
    """Manages persistent ChromaDB vector storage, chunk indexing, and similarity search."""

    @classmethod
    def get_client(cls) -> chromadb.PersistentClient:
        """
        Thread-safe singleton for persistent ChromaDB client.
        Data is persisted to disk under settings.CHROMA_PERSIST_DIRECTORY.
        """
        global _chroma_client
        if _chroma_client is None:
            with _client_lock:
                if _chroma_client is None:
                    persist_path = Path(settings.CHROMA_PERSIST_DIRECTORY).resolve()
                    persist_path.mkdir(parents=True, exist_ok=True)
                    logger.info("Initializing persistent ChromaDB client at: %s", persist_path)
                    _chroma_client = chromadb.PersistentClient(
                        path=str(persist_path),
                        settings=ChromaSettings(anonymized_telemetry=False),
                    )
        return _chroma_client

    @classmethod
    def get_collection_name(cls, owner: str, repository: str) -> str:
        """
        Derive a valid ChromaDB collection name for a given repository.
        ChromaDB collections require: 3-63 characters, [a-zA-Z0-9_-], start/end alphanumeric.
        """
        safe_owner = re.sub(r"[^a-zA-Z0-9_-]", "_", owner.lower()).strip("_")
        safe_repo = re.sub(r"[^a-zA-Z0-9_-]", "_", repository.lower()).strip("_")
        suffix = hashlib.sha256(f"{owner.lower()}/{repository.lower()}".encode()).hexdigest()[:12]
        prefix = f"repo_{safe_owner}_{safe_repo}"[:49].rstrip("_-")
        return f"{prefix}_{suffix}"

    @classmethod
    def delete_repository_index(cls, owner: str, repository: str) -> bool:
        """
        Delete an existing repository collection if it exists.
        Ensures a clean slate for re-indexing without leftover chunks.
        """
        client = cls.get_client()
        col_name = cls.get_collection_name(owner, repository)
        try:
            client.delete_collection(col_name)
            logger.info("Deleted existing ChromaDB collection '%s'", col_name)
            return True
        except Exception:
            # Collection may not exist yet, which is fine
            return False

    @classmethod
    def store_chunks(
        cls,
        owner: str,
        repository: str,
        chunks: List[CodeChunk],
        embeddings: List[List[float]],
        default_branch: str = "HEAD",
    ) -> int:
        """
        Store code chunks and their precomputed embeddings into ChromaDB.
        Replaces any prior index for the repository to avoid duplicates.

        Args:
            owner: Repository owner
            repository: Repository name
            chunks: List of CodeChunk objects
            embeddings: List of embedding vectors matching chunks

        Returns:
            Number of vectors stored
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: received {len(chunks)} chunks and {len(embeddings)} embeddings."
            )

        client = cls.get_client()
        col_name = cls.get_collection_name(owner, repository)

        # Delete prior collection if it already exists to avoid duplicate chunks
        cls.delete_repository_index(owner, repository)

        if not chunks:
            logger.info("Replaced index with an empty index for %s/%s", owner, repository)
            return 0

        # Create fresh collection using cosine similarity space
        collection = client.create_collection(
            name=col_name,
            metadata={
                "hnsw:space": "cosine",
                "owner": owner,
                "repository": repository,
                "default_branch": default_branch,
            },
        )

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = [
            {
                "owner": chunk.owner,
                "repository": chunk.repository,
                "path": chunk.path,
                "language": chunk.language,
                "chunk_index": chunk.chunk_index,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
            for chunk in chunks
        ]

        # Insert chunks in batches of 100 for stability
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end_idx = i + batch_size
            collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx],
            )

        logger.info(
            "Successfully stored %d code chunk vectors in ChromaDB collection '%s'",
            len(ids),
            col_name,
        )
        return len(ids)

    @classmethod
    def search_repository(
        cls,
        owner: str,
        repository: str,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[SearchResultChunk]:
        """
        Query repository vectors using semantic similarity.

        Args:
            owner: Repository owner
            repository: Repository name
            query_embedding: Query embedding vector
            top_k: Maximum number of results

        Returns:
            Ranked list of SearchResultChunk objects
        """
        client = cls.get_client()
        col_name = cls.get_collection_name(owner, repository)

        try:
            collection = client.get_collection(col_name)
        except Exception:
            logger.warning(
                "ChromaDB collection '%s' not found for %s/%s. Repository may not be indexed yet.",
                col_name,
                owner,
                repository,
            )
            return []

        total_vectors = collection.count()
        if total_vectors == 0:
            return []

        n_results = min(top_k, total_vectors)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        output: List[SearchResultChunk] = []

        if not results or not results.get("ids") or not results["ids"][0]:
            return output

        ids = results["ids"][0]
        documents = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []
        distances = results["distances"][0] if results.get("distances") else []

        for i in range(len(ids)):
            meta = metadatas[i] if i < len(metadatas) else {}
            dist = float(distances[i]) if i < len(distances) else 0.0

            # In cosine space, distance is 1 - cosine_similarity
            similarity = round(max(0.0, min(1.0, 1.0 - dist)), 4)

            output.append(
                SearchResultChunk(
                    chunk_id=ids[i],
                    path=meta.get("path", "unknown"),
                    language=meta.get("language", "Text"),
                    start_line=meta.get("start_line", 1),
                    end_line=meta.get("end_line", 1),
                    content=documents[i] if i < len(documents) else "",
                    similarity_score=similarity,
                    distance=round(dist, 4),
                )
            )

        return output

    @classmethod
    def get_repository_chunks(cls, owner: str, repository: str, limit: int = 5000) -> List[Dict]:
        """Return indexed documents and metadata for repository-derived UI suggestions."""
        collection_name = cls.get_collection_name(owner, repository)
        try:
            collection = cls.get_client().get_collection(collection_name)
        except Exception:
            return []
        count = collection.count()
        if count == 0:
            return []
        result = collection.get(
            limit=min(max(1, limit), count),
            include=["documents", "metadatas"],
        )
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        return [
            {
                "content": documents[index] if index < len(documents) else "",
                "path": (metadatas[index] or {}).get("path", ""),
                "language": (metadatas[index] or {}).get("language", ""),
            }
            for index in range(len(documents))
        ]

    @classmethod
    def get_repository_default_branch(cls, owner: str, repository: str) -> str:
        """Return the default branch captured during ingestion, if available."""
        try:
            collection = cls.get_client().get_collection(cls.get_collection_name(owner, repository))
            return str((collection.metadata or {}).get("default_branch") or "HEAD")
        except Exception:
            return "HEAD"

    @classmethod
    def get_repository_index_stats(cls, owner: str, repository: str) -> Dict:
        """Return true distinct-file, language, and vector counts from a repository collection."""
        try:
            collection = cls.get_client().get_collection(cls.get_collection_name(owner, repository))
        except Exception:
            return {"vectors": 0, "files": 0, "languages": {}}
        vectors = collection.count()
        if not vectors:
            return {"vectors": 0, "files": 0, "languages": {}}
        file_languages: Dict[str, str] = {}
        for offset in range(0, vectors, 1000):
            records = collection.get(limit=min(1000, vectors - offset), offset=offset, include=["metadatas"])
            for metadata in records.get("metadatas") or []:
                metadata = metadata or {}
                path = metadata.get("path")
                if path:
                    file_languages.setdefault(path, metadata.get("language") or "Unknown")
        languages: Dict[str, int] = {}
        for language in file_languages.values():
            languages[language] = languages.get(language, 0) + 1
        return {"vectors": vectors, "files": len(file_languages), "languages": languages}

    @classmethod
    def has_repository_index(cls, owner: str, repository: str) -> bool:
        """Check index presence without scanning vector metadata or embedding a query."""
        try:
            collection = cls.get_client().get_collection(cls.get_collection_name(owner, repository))
            return collection.count() > 0
        except Exception:
            return False

    @classmethod
    def get_repository_files(cls, owner: str, repository: str) -> List[RepositoryFile]:
        """Reconstruct source files from existing indexed chunks, avoiding another GitHub fetch."""
        try:
            collection = cls.get_client().get_collection(cls.get_collection_name(owner, repository))
        except Exception:
            return []
        count = collection.count()
        if count == 0:
            return []
        records = collection.get(
            limit=count,
            include=["documents", "metadatas"],
        )
        grouped: Dict[str, Dict] = {}
        for index, metadata in enumerate(records.get("metadatas") or []):
            metadata = metadata or {}
            path = metadata.get("path")
            if not path:
                continue
            group = grouped.setdefault(path, {"language": metadata.get("language", "Text"), "chunks": []})
            documents = records.get("documents") or []
            group["chunks"].append((
                int(metadata.get("chunk_index", index)),
                int(metadata.get("start_line", 1)),
                documents[index] if index < len(documents) else "",
            ))

        files = []
        for path, group in sorted(grouped.items()):
            source_lines: Dict[int, str] = {}
            for _, start_line, content in sorted(group["chunks"]):
                for offset, line in enumerate(content.splitlines()):
                    source_lines.setdefault(start_line + offset, line)
            if not source_lines:
                continue
            last_line = max(source_lines)
            content = "\n".join(source_lines.get(line, "") for line in range(1, last_line + 1))
            files.append(RepositoryFile(
                path=path,
                language=group["language"],
                content=content,
                size=len(content.encode("utf-8")),
            ))
        return files

