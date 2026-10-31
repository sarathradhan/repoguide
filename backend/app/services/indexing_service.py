"""Indexing pipeline orchestrating ingestion, chunking, embedding, and vector storage."""
import logging
import re
from typing import List, Optional
from urllib.parse import quote

from app.core.config import settings
from app.models.repository import (
    RepositoryContextChunk,
    RepositoryAskResponse,
    RepositorySourceReference,
    RetrievedContextMetadata,
    ConversationTurn,
    RepositoryIndexResponse,
    SearchResponse,
    SearchResultChunk,
)
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.groq_service import GroqService
from app.services.github_service import GitHubService
from app.services.vector_store import VectorStoreService
from app.services.repository_snapshot_service import RepositorySnapshotService
from app.services.indexing_status_service import IndexingStatusService
from app.services.repository_overview_service import RepositoryOverviewService
from app.services.question_intent_service import QuestionIntentService

logger = logging.getLogger("repoguide.indexing")

# These files remain in the persisted snapshot/overview but do not pollute the
# semantic code index; README and manifests are retrieved through overview context.
OVERVIEW_ONLY_LANGUAGES = {
    "Markdown", "reStructuredText", "TOML", "Text", "Configuration",
    "Properties", "XML", "Gradle",
}


class RepositoryNotIndexedError(LookupError):
    """Raised when a repository has no searchable ChromaDB chunks."""


class IndexingService:
    """Orchestrates end-to-end repository indexing and semantic code search."""

    @classmethod
    async def index_repository(cls, repo_url: str) -> RepositoryIndexResponse:
        owner, repository = GitHubService.parse_repo_url(repo_url)
        IndexingStatusService.mark_started(owner, repository)
        try:
            result = await cls._run_indexing_pipeline(repo_url)
        except Exception:
            IndexingStatusService.mark_failed(owner, repository)
            raise
        IndexingStatusService.mark_completed(
            owner, repository, result.files_processed, result.chunks_created, result.vectors_stored
        )
        return result

    @classmethod
    async def _run_indexing_pipeline(cls, repo_url: str) -> RepositoryIndexResponse:
        """
        Execute full indexing pipeline:
        1. Ingest repository files via GitHubService
        2. Chunk source code via ChunkingService
        3. Compute embeddings via EmbeddingService
        4. Persist vectors and metadata in ChromaDB via VectorStoreService
        """
        logger.info("Starting indexing pipeline for: %s", repo_url)

        # 1. Ingest repository files
        repo_data = await GitHubService.ingest_repository(repo_url)
        files = repo_data.files
        owner = repo_data.owner
        repo = repo_data.repository
        RepositorySnapshotService.save(repo_data)
        # Rebuild the deterministic overview on each fresh snapshot/index run.
        RepositoryOverviewService.get_or_build(repo_data)

        if not files:
            logger.warning("No source files found to index for %s/%s", owner, repo)
            VectorStoreService.store_chunks(owner, repo, [], [], repo_data.default_branch)
            return RepositoryIndexResponse(
                success=True,
                repository=repo,
                files_processed=0,
                chunks_created=0,
                vectors_stored=0,
            )

        # 2. Chunk code/config formats that belong in semantic code search. Documentation
        # and primary manifests remain available through the persisted overview context.
        chunk_files = [file for file in files if file.language not in OVERVIEW_ONLY_LANGUAGES]
        chunks = ChunkingService.chunk_repository_files(owner, repo, chunk_files)
        if not chunks:
            logger.warning("0 chunks created for %s/%s", owner, repo)
            VectorStoreService.store_chunks(owner, repo, [], [], repo_data.default_branch)
            return RepositoryIndexResponse(
                success=True,
                repository=repo,
                files_processed=len(files),
                chunks_created=0,
                vectors_stored=0,
            )

        # 3. Generate dense vector embeddings
        chunk_texts = [chunk.content for chunk in chunks]
        logger.info("Generating embeddings for %d code chunks...", len(chunk_texts))
        embeddings = EmbeddingService.embed_texts(chunk_texts)

        # 4. Store into ChromaDB
        vectors_stored = VectorStoreService.store_chunks(
            owner, repo, chunks, embeddings, repo_data.default_branch
        )

        logger.info(
            "Indexing pipeline complete for %s/%s: %d files -> %d chunks -> %d vectors stored",
            owner,
            repo,
            len(files),
            len(chunks),
            vectors_stored,
        )

        return RepositoryIndexResponse(
            success=True,
            repository=repo,
            files_processed=len(files),
            chunks_created=len(chunks),
            vectors_stored=vectors_stored,
        )

    @classmethod
    def search_repository(
        cls,
        repo_url: str,
        query: str,
        top_k: int = 5,
    ) -> SearchResponse:
        """
        Semantic code search within a single repository collection.

        Args:
            repo_url: GitHub URL of target repository
            query: Natural language or code concept query
            top_k: Number of matches to return

        Returns:
            SearchResponse containing ranked SearchResultChunks
        """
        owner, repo = GitHubService.parse_repo_url(repo_url)

        # Generate query vector embedding using same model & normalization
        query_embedding = EmbeddingService.embed_query(query)

        # Query isolated repository collection in ChromaDB
        results = VectorStoreService.search_repository(
            owner=owner,
            repository=repo,
            query_embedding=query_embedding,
            top_k=top_k,
        )

        return SearchResponse(
            repository=repo,
            query=query,
            results_count=len(results),
            results=results,
        )

    @classmethod
    async def ask_repository(
        cls,
        repo_url: str,
        question: str,
        top_k: int = 5,
        conversation_history: Optional[List[ConversationTurn]] = None,
    ) -> RepositoryAskResponse:
        """Route each question to source-backed overview, architecture, or code context."""
        owner, repository = GitHubService.parse_repo_url(repo_url)
        intent = QuestionIntentService.detect(question)

        # Keep the established unindexed-repository behavior for all intents.
        chunks = []
        if intent == "broad":
            if not VectorStoreService.has_repository_index(owner, repository):
                raise RepositoryNotIndexedError(
                    f"{owner}/{repository} has no indexed code. Index the repository before asking questions."
                )
        else:
            query_embedding = EmbeddingService.embed_query(question)
            chunks = VectorStoreService.search_repository(
                owner=owner,
                repository=repository,
                query_embedding=query_embedding,
                top_k=top_k,
            )
        if intent != "broad" and not chunks:
            raise RepositoryNotIndexedError(
                f"{owner}/{repository} has no indexed code. Index the repository before asking questions."
            )

        threshold = settings.RAG_MIN_SIMILARITY
        default_branch = VectorStoreService.get_repository_default_branch(owner, repository)
        top_similarity = max((chunk.similarity_score for chunk in chunks), default=0.0)
        snapshot = RepositorySnapshotService.get(owner, repository)
        if snapshot is None:
            indexed_files = VectorStoreService.get_repository_files(owner, repository)
            if indexed_files:
                from app.models.repository import RepositoryResponse
                snapshot = RepositoryResponse(
                    owner=owner, repository=repository, description=None,
                    default_branch=default_branch, stars=0,
                    total_source_files_found=len(indexed_files), files_returned=len(indexed_files),
                    files_truncated=False, truncation_reason=None, files=indexed_files,
                )
                RepositorySnapshotService.save(snapshot)
        overview_context: List[RepositoryContextChunk] = []
        architecture_used = False
        overview_used = False
        if snapshot:
            overview = RepositoryOverviewService.get_or_build(snapshot)
            if intent in {"broad", "technology"}:
                overview_context = RepositoryOverviewService.context_for_intent(overview, intent)
                overview_used = bool(overview_context)
            elif intent == "architecture":
                overview_context = RepositoryOverviewService.context_for_intent(overview, "architecture")
                architecture_context = RepositoryOverviewService.architecture_context(snapshot)
                overview_context.extend(architecture_context)
                architecture_used = bool(architecture_context)
                overview_used = bool(overview_context)

        if intent == "broad":
            answer_context = overview_context
            sufficient = bool(
                overview_context
                and snapshot
                and (overview.readme_paths or overview.description or overview.project_description)
            )
        elif intent == "technology":
            answer_context = overview_context + chunks
            sufficient = bool(overview_context) or top_similarity >= threshold
        elif intent == "architecture":
            answer_context = overview_context + chunks
            sufficient = architecture_used or top_similarity >= threshold
        else:
            answer_context = chunks
            sufficient = top_similarity >= threshold

        normalized_history = []
        for turn in conversation_history or []:
            if isinstance(turn, dict):
                normalized_history.append(ConversationTurn(**turn).model_dump())
            elif isinstance(turn, ConversationTurn):
                normalized_history.append(turn.model_dump())
            else:
                raise TypeError("Conversation history entries must be ConversationTurn models or role/content mappings.")

        answer_context = GroqService.fit_context(question, answer_context, normalized_history)
        sources = [
            RepositorySourceReference(
                citation_id=f"S{index}",
                chunk_id=chunk.chunk_id,
                path=chunk.path,
                language=chunk.language,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                similarity_score=getattr(chunk, "similarity_score", None),
                distance=getattr(chunk, "distance", None),
                context_type=getattr(chunk, "context_type", "code"),
                url=(
                    f"https://github.com/{quote(owner)}/{quote(repository)}/blob/"
                    f"{quote(default_branch, safe='/')}/"
                    f"{quote(chunk.path, safe='/')}#L{chunk.start_line}-L{chunk.end_line}"
                ),
            )
            for index, chunk in enumerate(answer_context, start=1)
        ]

        if sufficient and answer_context:
            answer = await GroqService.generate_answer(question, answer_context, normalized_history)
            # Remove formatting marks and citations the model wasn't given.
            answer = re.sub(r"[\u200b-\u200f\u2060-\u206f\ufeff]", "", answer)
            valid_citations = {source.citation_id for source in sources}
            answer = re.sub(r"\[(S\d+)\]", lambda match: match.group(0) if match.group(1) in valid_citations else "", answer).strip()
            if not re.search(r"\[S\d+\]", answer):
                answer = f"{answer}\n\nSources: " + ", ".join(f"[{source.citation_id}]" for source in sources)
        else:
            answer = (
                "I couldn't find enough relevant information in the indexed repository "
                "context to answer this question reliably. Add or update the README or "
                "project manifests, then reindex the repository."
            )

        return RepositoryAskResponse(
            answer=answer,
            repository=repository,
            question=question,
            sources=sources,
            retrieved_context=RetrievedContextMetadata(
                chunks_retrieved=len(answer_context),
                top_k=top_k,
                top_similarity=round(top_similarity, 4),
                minimum_similarity=threshold,
                context_sufficient=sufficient,
                question_intent=intent,
                repository_overview_used=overview_used,
                architecture_context_used=architecture_used,
            ),
        )

