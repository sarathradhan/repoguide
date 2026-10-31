"""Route handlers for repository ingestion, vector indexing, and semantic search."""
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
import httpx

from app.models.repository import (
    RepositoryIndexRequest,
    RepositoryIndexResponse,
    RepositoryAskRequest,
    RepositoryAskResponse,
    RepositoryRequest,
    RepositoryResponse,
    SearchRequest,
    SearchResponse,
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    SuggestedQuestionsResponse,
    RepositoryArchitectureRequest,
    RepositoryArchitectureResponse,
    RepositoryDependenciesRequest,
    RepositoryDependenciesResponse,
    RepositoryDashboardResponse,
)
from app.services.github_service import GitHubService
from app.services.indexing_service import IndexingService
from app.services.indexing_service import RepositoryNotIndexedError
from app.services.groq_service import GroqAPIError, MissingGroqAPIKeyError
from app.services.conversation_service import ConversationService, SuggestedQuestionService
from app.services.vector_store import VectorStoreService
from app.services.repository_snapshot_service import RepositorySnapshotService
from app.services.architecture_service import ArchitectureService
from app.services.dependency_service import DependencyAnalysisService
from app.services.dashboard_service import DashboardService

logger = logging.getLogger("repoguide.routes.repository")

router = APIRouter(prefix="/api/repositories", tags=["Repositories"])


@router.post(
    "/ingest",
    response_model=RepositoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest Public GitHub Repository",
    description=(
        "Fetch metadata, parse recursive file tree, filter source code files, "
        "and download file contents from a public GitHub repository."
    ),
)
async def ingest_repository(request: RepositoryRequest) -> RepositoryResponse:
    """Ingest a public GitHub repository and return its source code tree."""
    try:
        logger.info("Starting ingestion for repository URL: %s", request.repo_url)
        response = await GitHubService.ingest_repository(request.repo_url)
        RepositorySnapshotService.save(response)
        logger.info(
            "Successfully ingested %s/%s (found %d files, returned %d)",
            response.owner,
            response.repository,
            response.total_source_files_found,
            response.files_returned,
        )
        return response
    except ValueError as val_err:
        logger.warning("Invalid repository request: %s", val_err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except HTTPException:
        raise
    except httpx.TimeoutException as timeout_err:
        logger.error("Timeout during ingestion: %s", timeout_err)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout communicating with GitHub servers. Please try again.",
        )
    except httpx.RequestError as req_err:
        logger.error("HTTP network error during ingestion: %s", req_err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Network error contacting GitHub: {str(req_err)}",
        )
    except Exception as exc:
        logger.error("Unexpected error ingesting repository: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during repository ingestion: {str(exc)}",
        )


@router.post(
    "/index",
    response_model=RepositoryIndexResponse,
    status_code=status.HTTP_200_OK,
    summary="Index Repository into Vector Store",
    description=(
        "Ingest repository files, split source code into language-aware chunks, "
        "generate dense vector embeddings, and persist in ChromaDB."
    ),
)
async def index_repository(request: RepositoryIndexRequest) -> RepositoryIndexResponse:
    """Index repository source code into persistent ChromaDB vector store."""
    try:
        logger.info("Indexing requested for repository: %s", request.repo_url)
        result = await IndexingService.index_repository(request.repo_url)
        return result
    except ValueError as val_err:
        logger.warning("Validation error during indexing: %s", val_err)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error during repository indexing: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index repository: {str(exc)}",
        )


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic Code Search",
    description="Search repository code chunks using dense semantic similarity in ChromaDB.",
)
async def search_repository(request: SearchRequest) -> SearchResponse:
    """Perform semantic code search over indexed repository chunks."""
    try:
        logger.info(
            "Searching repository '%s' with query: '%s' (top_k=%d)",
            request.repo_url,
            request.query,
            request.top_k,
        )
        result = IndexingService.search_repository(
            repo_url=request.repo_url,
            query=request.query,
            top_k=request.top_k,
        )
        return result
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error during semantic search: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(exc)}",
        )


@router.post(
    "/ask",
    response_model=RepositoryAskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question about an indexed repository",
    description=(
        "Retrieve relevant code from the repository's ChromaDB index and generate "
        "a grounded answer with source citations using Groq."
    ),
)
async def ask_repository(request: RepositoryAskRequest) -> RepositoryAskResponse:
    """Answer a repository question using retrieved code as the only evidence."""
    try:
        history = request.conversation_history
        owner = repository = None
        if request.conversation_id is not None and request.session_id is not None:
            owner, repository = GitHubService.parse_repo_url(request.repo_url)
            stored_history = ConversationService.recent_turns(
                request.conversation_id, owner, repository, request.session_id
            )
            if stored_history is None:
                raise HTTPException(status_code=404, detail="Conversation not found for this repository and session.")
            history = stored_history

        response = await IndexingService.ask_repository(
            repo_url=request.repo_url,
            question=request.question,
            top_k=request.top_k,
            conversation_history=history,
        )
        if request.conversation_id is not None and request.session_id is not None:
            saved = ConversationService.append_exchange(
                request.conversation_id,
                owner,
                repository,
                request.session_id,
                request.question,
                response,
            )
            if not saved:
                raise HTTPException(status_code=404, detail="Conversation is no longer available in this session.")
            response = response.model_copy(update={"conversation_id": request.conversation_id})
        return response
    except RepositoryNotIndexedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except HTTPException:
        raise
    except MissingGroqAPIKeyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except GroqAPIError as exc:
        response_status = (
            status.HTTP_429_TOO_MANY_REQUESTS
            if exc.status_code == 429
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=response_status, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Error answering repository question: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to answer the repository question.",
        )


@router.post(
    "/conversations",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a repository conversation",
)
async def create_conversation(request: ConversationCreateRequest) -> ConversationDetailResponse:
    try:
        owner, repository = GitHubService.parse_repo_url(request.repo_url)
        return ConversationService.create(owner, repository, request.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    repo_url: str = Query(...), session_id: UUID = Query(...)
) -> ConversationListResponse:
    try:
        owner, repository = GitHubService.parse_repo_url(repo_url)
        conversations = ConversationService.list_for_session(owner, repository, session_id)
        return ConversationListResponse(repository=repository, conversations=conversations)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: UUID,
    repo_url: str = Query(...),
    session_id: UUID = Query(...),
) -> ConversationDetailResponse:
    try:
        owner, repository = GitHubService.parse_repo_url(repo_url)
        conversation = ConversationService.get_for_session(
            conversation_id, owner, repository, session_id
        )
        if conversation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return conversation
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/suggestions", response_model=SuggestedQuestionsResponse)
async def suggested_questions(repo_url: str = Query(...)) -> SuggestedQuestionsResponse:
    try:
        owner, repository = GitHubService.parse_repo_url(repo_url)
        chunks = VectorStoreService.get_repository_chunks(owner, repository)
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This repository has no indexed code yet. Index it to get repository-based question suggestions.",
            )
        return SuggestedQuestionsResponse(
            repository=repository,
            suggestions=SuggestedQuestionService.from_chunks(chunks),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/architecture", response_model=RepositoryArchitectureResponse)
async def repository_architecture(
    request: RepositoryArchitectureRequest,
) -> RepositoryArchitectureResponse:
    """Analyze cached repository files into a deterministic architecture map."""
    try:
        return await ArchitectureService.analyze_repository(request.repo_url, refresh=request.refresh)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Architecture analysis failed for %s", request.repo_url)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Architecture analysis failed. Retry the request or refresh the repository snapshot.",
        ) from exc


@router.post("/dependencies", response_model=RepositoryDependenciesResponse)
async def repository_dependencies(
    request: RepositoryDependenciesRequest,
) -> RepositoryDependenciesResponse:
    """Extract local source-file dependencies from the cached repository snapshot."""
    try:
        return await DependencyAnalysisService.analyze_repository(
            request.repo_url, refresh=request.refresh, max_files=request.max_files
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Dependency analysis failed for %s", request.repo_url)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dependency analysis failed. Retry the request or refresh the repository snapshot.",
        ) from exc


@router.get("/dashboard", response_model=RepositoryDashboardResponse)
async def repository_dashboard(
    repo_url: str = Query(...),
    session_id: UUID = Query(...),
) -> RepositoryDashboardResponse:
    """Return repository stats and conversation analytics for this browser session."""
    try:
        return DashboardService.get_dashboard(repo_url, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Dashboard query failed for %s", repo_url)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not load repository dashboard statistics.",
        ) from exc
