"""Pydantic data models for GitHub repository ingestion and vector indexing."""
import re
from typing import Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator


class RepositoryRequest(BaseModel):
    """Schema for repository ingestion request."""

    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL (e.g. https://github.com/psf/requests)",
        examples=["https://github.com/psf/requests"],
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Validate that the provided string is a valid GitHub repository URL."""
        v = v.strip()
        if not v:
            raise ValueError("Repository URL cannot be empty.")

        # Normalize URL by prepending https:// if missing
        if not v.startswith("http://") and not v.startswith("https://"):
            v = f"https://{v}"

        pattern = r"^https?://(?:www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
        match = re.match(pattern, v, re.IGNORECASE)
        if not match:
            raise ValueError(
                "Invalid GitHub URL format. Please provide a URL like https://github.com/owner/repository"
            )

        owner, repo = match.group(1), match.group(2)
        if owner in [".", ".."] or repo in [".", ".."]:
            raise ValueError("Invalid repository owner or repository name.")

        return v


class RepositoryFile(BaseModel):
    """Schema representing an individual retrieved source code file."""

    path: str = Field(..., description="Relative file path in repository")
    language: str = Field(..., description="Detected programming language")
    content: str = Field(..., description="Text content of the file")
    size: int = Field(..., description="File size in bytes")


class RepositoryResponse(BaseModel):
    """Schema for repository ingestion response."""

    owner: str = Field(..., description="Repository owner username or organization")
    repository: str = Field(..., description="Repository name")
    description: Optional[str] = Field(None, description="Repository description from GitHub")
    default_branch: str = Field(..., description="Default git branch, e.g. main or master")
    stars: int = Field(..., description="GitHub stargazer count")
    total_source_files_found: int = Field(
        ..., description="Total number of valid source code files discovered in the tree"
    )
    files_returned: int = Field(
        ..., description="Number of source code files actually downloaded and returned"
    )
    files_truncated: bool = Field(
        ..., description="True if files were omitted due to limits (count or total byte size)"
    )
    truncation_reason: Optional[str] = Field(
        None, description="Detailed explanation if results were truncated"
    )
    files: List[RepositoryFile] = Field(
        ..., description="List of downloaded source code files"
    )


# Milestone 3 Models: Chunking, Indexing, and Semantic Search


class CodeChunk(BaseModel):
    """Schema representing a segmented chunk of source code."""

    chunk_id: str = Field(..., description="Unique deterministic identifier for the chunk")
    owner: str = Field(..., description="Repository owner")
    repository: str = Field(..., description="Repository name")
    path: str = Field(..., description="Relative file path")
    language: str = Field(..., description="Programming language of chunk")
    content: str = Field(..., description="Code snippet content")
    chunk_index: int = Field(..., description="0-based sequence index within file")
    start_line: int = Field(..., description="1-based starting line number in source file")
    end_line: int = Field(..., description="1-based ending line number in source file")


class RepositoryIndexRequest(BaseModel):
    """Schema for repository vector indexing request."""

    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL to index",
        examples=["https://github.com/psf/requests"],
    )

    @field_validator("repo_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return RepositoryRequest.validate_github_url(v)


class RepositoryIndexResponse(BaseModel):
    """Schema returned after indexing a repository into vector storage."""

    success: bool = Field(..., description="Whether indexing completed successfully")
    repository: str = Field(..., description="Repository name")
    files_processed: int = Field(..., description="Number of source files ingested and processed")
    chunks_created: int = Field(..., description="Total code chunks created from files")
    vectors_stored: int = Field(..., description="Total vector embeddings persisted in ChromaDB")


class SearchRequest(BaseModel):
    """Schema for semantic code search request."""

    repo_url: str = Field(
        ...,
        description="Public GitHub repository URL to search within",
        examples=["https://github.com/psf/requests"],
    )
    query: str = Field(
        ...,
        min_length=2,
        description="Natural language query or code concept to search for",
        examples=["Where is the HTTP request logic implemented?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of relevant code chunks to return",
    )

    @field_validator("repo_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return RepositoryRequest.validate_github_url(v)


class SearchResultChunk(BaseModel):
    """Individual code chunk match in semantic search results."""

    chunk_id: str = Field(..., description="Unique chunk ID")
    path: str = Field(..., description="Source file path")
    language: str = Field(..., description="Programming language")
    start_line: int = Field(..., description="Starting line in source file")
    end_line: int = Field(..., description="Ending line in source file")
    content: str = Field(..., description="Matched code text")
    similarity_score: float = Field(..., description="Calculated cosine similarity score (0.0 to 1.0)")
    distance: float = Field(..., description="ChromaDB vector distance")


class SearchResponse(BaseModel):
    """Schema returned from semantic search query."""

    repository: str = Field(..., description="Repository name")
    query: str = Field(..., description="Original search query")
    results_count: int = Field(..., description="Number of results found")
    results: List[SearchResultChunk] = Field(..., description="Ranked list of matching code chunks")


class ConversationTurn(BaseModel):
    """A recent chat turn used only to resolve follow-up wording."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class RepositoryAskRequest(BaseModel):
    """Request for a grounded answer based on one indexed repository."""

    repo_url: str = Field(..., description="Public GitHub repository URL")
    question: str = Field(..., min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)
    conversation_history: List[ConversationTurn] = Field(default_factory=list, max_length=6)
    session_id: Optional[UUID] = Field(default=None, description="Browser session identifier")
    conversation_id: Optional[UUID] = Field(default=None, description="Persistent conversation identifier")

    @model_validator(mode="after")
    def validate_conversation_scope(self):
        if (self.session_id is None) != (self.conversation_id is None):
            raise ValueError("session_id and conversation_id must be provided together.")
        return self

    @field_validator("repo_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return RepositoryRequest.validate_github_url(value)


class RepositorySourceReference(BaseModel):
    """A source chunk used to ground a generated answer."""

    citation_id: str = Field(..., description="Inline citation token such as [S1]")
    chunk_id: str
    path: str
    language: str
    start_line: int
    end_line: int
    similarity_score: Optional[float] = None
    distance: Optional[float] = None
    url: Optional[str] = Field(default=None, description="GitHub file URL for this line range")
    context_type: Literal["code", "overview", "architecture"] = "code"


class RepositoryOverviewEvidence(BaseModel):
    """Source excerpt supporting a structured repository overview fact."""

    evidence_id: str
    category: Literal["readme", "manifest", "language", "entry_point", "module"]
    path: str
    language: str
    start_line: int
    end_line: int
    content: str
    evidence_type: Literal["detected", "inferred"] = "detected"


class RepositoryOverview(BaseModel):
    """Deterministic, repository-specific summary extracted from a saved snapshot."""

    owner: str
    repository: str
    fingerprint: str
    description: Optional[str] = None
    readme_paths: List[str] = Field(default_factory=list)
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    languages: Dict[str, int] = Field(default_factory=dict)
    frameworks: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    feature_headings: List[str] = Field(default_factory=list)
    entry_points: List[str] = Field(default_factory=list)
    important_modules: List[str] = Field(default_factory=list)
    manifest_paths: List[str] = Field(default_factory=list)
    evidence: List[RepositoryOverviewEvidence] = Field(default_factory=list)


class RepositoryContextChunk(BaseModel):
    """Citable context passed to the LLM from code, overview, or architecture."""

    chunk_id: str
    path: str
    language: str
    start_line: int
    end_line: int
    content: str
    context_type: Literal["code", "overview", "architecture"] = "code"
    similarity_score: Optional[float] = None
    distance: Optional[float] = None


class RetrievedContextMetadata(BaseModel):
    """Summary of the ChromaDB context supplied to answer generation."""

    chunks_retrieved: int
    top_k: int
    top_similarity: float
    minimum_similarity: float
    context_sufficient: bool
    question_intent: str = "implementation"
    repository_overview_used: bool = False
    architecture_context_used: bool = False


class RepositoryAskResponse(BaseModel):
    """Grounded repository answer and its retrievable source references."""

    answer: str
    repository: str
    question: str
    sources: List[RepositorySourceReference]
    retrieved_context: RetrievedContextMetadata
    conversation_id: Optional[UUID] = None


class ConversationCreateRequest(BaseModel):
    """Create a new private-to-session conversation for a repository."""

    repo_url: str
    session_id: UUID

    @field_validator("repo_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return RepositoryRequest.validate_github_url(value)


class ConversationSummary(BaseModel):
    conversation_id: UUID
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationListResponse(BaseModel):
    repository: str
    conversations: List[ConversationSummary]


class ConversationMessage(BaseModel):
    message_id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    sources: List[RepositorySourceReference] = Field(default_factory=list)
    retrieved_context: Optional[RetrievedContextMetadata] = None


class ConversationDetailResponse(BaseModel):
    conversation_id: UUID
    repository: str
    title: str
    created_at: str
    updated_at: str
    messages: List[ConversationMessage]


class SuggestedQuestionsResponse(BaseModel):
    repository: str
    suggestions: List[str]


class RepositoryArchitectureRequest(BaseModel):
    repo_url: str = Field(..., description="Public GitHub repository to inspect")
    refresh: bool = Field(default=False, description="Fetch the latest repository files before analyzing")

    @field_validator("repo_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return RepositoryRequest.validate_github_url(value)


class ArchitectureComponent(BaseModel):
    id: str
    label: str
    component_type: Literal[
        "repository", "directory", "module", "entry_point", "route",
        "controller", "service", "database", "integration",
    ]
    evidence_type: Literal["detected", "inferred"]
    description: str
    path: Optional[str] = None
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    details: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class ArchitectureRelationship(BaseModel):
    id: str
    source: str
    target: str
    label: str
    evidence_type: Literal["detected", "inferred"]
    source_path: Optional[str] = None
    source_line: Optional[int] = None


class RepositoryArchitectureResponse(BaseModel):
    owner: str
    repository: str
    default_branch: str
    components: List[ArchitectureComponent]
    relationships: List[ArchitectureRelationship]
    files_analyzed: int
    directories_detected: int
    entry_points_detected: int
    entry_point_candidates: int
    routes_detected: int
    files_truncated: bool
    truncation_reason: Optional[str] = None
    supported_languages: List[str]
    unsupported_files: List[str]


class RepositoryDependenciesRequest(BaseModel):
    repo_url: str = Field(..., description="Public GitHub repository to analyze")
    refresh: bool = Field(default=False, description="Fetch the latest repository files before analyzing")
    max_files: int = Field(default=250, ge=20, le=500, description="Maximum source files included in the graph")

    @field_validator("repo_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return RepositoryRequest.validate_github_url(value)


class DependencyNode(BaseModel):
    id: str
    path: str
    language: str
    incoming_count: int = 0
    outgoing_count: int = 0
    isolated: bool = False
    cycle_ids: List[str] = Field(default_factory=list)
    source_url: str


class DependencyEdge(BaseModel):
    id: str
    source: str
    target: str
    imported_name: str
    source_path: str
    source_line: int
    evidence_type: Literal["detected"] = "detected"
    source_url: str


class UnresolvedDependency(BaseModel):
    source_path: str
    language: str
    imported_name: str
    source_line: int
    reason: str
    source_url: str


class DependencyCycle(BaseModel):
    id: str
    paths: List[str]


class RepositoryDependenciesResponse(BaseModel):
    owner: str
    repository: str
    default_branch: str
    nodes: List[DependencyNode]
    edges: List[DependencyEdge]
    unresolved_imports: List[UnresolvedDependency]
    cycles: List[DependencyCycle]
    isolated_files: List[str]
    files_analyzed: int
    total_source_files: int
    files_truncated: bool
    graph_limit: int
    languages: List[str]


class DashboardLanguageStatistic(BaseModel):
    language: str
    files: int


class DashboardFileStatistic(BaseModel):
    path: str
    reference_count: int


class DashboardTopicStatistic(BaseModel):
    topic: str
    question_count: int


class DashboardQuestionDay(BaseModel):
    date: str
    question_count: int


class DashboardActivity(BaseModel):
    conversation_id: UUID
    conversation_title: str
    repository: str
    question: str
    answer_preview: Optional[str] = None
    created_at: str
    sources: List[RepositorySourceReference] = Field(default_factory=list)


class DashboardArchitectureOverview(BaseModel):
    files_analyzed: int
    directories_detected: int
    entry_points_detected: int
    routes_detected: int


class DashboardDependencyOverview(BaseModel):
    files_analyzed: int
    resolved_imports: int
    cycles: int
    unresolved_imports: int
    isolated_files: int


class RepositoryDashboardResponse(BaseModel):
    owner: str
    repository: str
    repo_url: str
    description: Optional[str] = None
    default_branch: Optional[str] = None
    indexing_status: Literal["not_indexed", "indexing", "indexed", "empty", "failed"]
    indexed_files: int
    indexed_chunks: int
    indexed_vectors: int
    languages: List[DashboardLanguageStatistic]
    last_indexed_at: Optional[str] = None
    snapshot_files: int
    total_questions: int
    questions_over_time: List[DashboardQuestionDay]
    frequently_referenced_files: List[DashboardFileStatistic]
    most_explored_modules: List[DashboardFileStatistic]
    most_explored_topics: List[DashboardTopicStatistic]
    recent_activity: List[DashboardActivity]
    conversations: List[ConversationSummary]
    architecture: Optional[DashboardArchitectureOverview] = None
    dependencies: Optional[DashboardDependencyOverview] = None
