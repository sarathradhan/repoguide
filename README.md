# RepoGuide AI 🧭⚡

> **AI-Powered GitHub Repository Understanding Assistant**
> Accelerate codebase onboarding, trace complex architecture, and query repository semantics.

---

## 📋 Table of Contents
- [Overview](#overview)
- [Milestones Completed](#milestones-completed)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Roadmap](#roadmap)

---

## 🌟 Overview

**RepoGuide AI** is an intelligent assistant designed to help developers inspect, comprehend, and navigate complex GitHub repositories. By integrating modern LLM reasoning with repository AST parsing and semantic vector search (RAG), RepoGuide AI acts as an interactive code companion.

### Completed Milestones
- **Milestone 1**: Foundation setup with FastAPI backend, React + Vite frontend, Tailwind CSS, Axios health diagnostics, and environment configuration.
- **Milestone 2**: Public GitHub repository ingestion, URL parsing, recursive Git tree retrieval via GitHub REST API, intelligent source code classification/filtering, concurrent raw file downloading with rate-limit handling, and an interactive developer code explorer dashboard.
- **Milestone 3**: Language-aware code chunking with source line ranges, all-MiniLM-L6-v2 embeddings, persistent repository-specific ChromaDB indexes, and semantic code search.
- **Milestone 4**: Grounded repository Q&A using ChromaDB retrieval and Groq chat completions, with follow-up context and source citations.
- **Milestone 5, Phase 1**: Persistent repository conversations, contextual follow-ups, indexed-code suggestions, and clickable GitHub file/line citations.
- **Milestone 5, Phase 2**: Deterministic architecture maps with repository/module structure, entry point candidates, routes, services/controllers, detected integrations, and source-backed relationships.
- **Milestone 5, Phase 3**: Source-backed local dependency graphs for Python, JavaScript/TypeScript, and Java, with unresolved imports, cycle detection, isolated files, and interactive dependency/path exploration.
- **Milestone 5, Phase 4**: Repository Q&A dashboard with persisted indexing status, repository statistics, session-scoped conversation analytics/history, and architecture/dependency summaries.

---

## 🛠 Technology Stack

### Backend
- **Python 3.13+**
- **FastAPI**: Modern, fast web framework for building APIs.
- **Uvicorn**: Lightning-fast ASGI server.
- **HTTPX**: High-performance async HTTP client for communicating with GitHub REST and Raw APIs.
- **Pydantic v2**: High-performance data validation and settings management.
- **Python-dotenv**: Environment variable management.

### Frontend
- **React 19**: Component-driven UI library.
- **Vite 8**: Next-generation frontend tooling and bundler.
- **Tailwind CSS v4**: Utility-first CSS framework with Vite integration.
- **Axios**: Promise-based HTTP client with custom service layer.
- **Lucide React**: Clean, modern developer iconography.
- **React Flow (@xyflow/react)**: Interactive architecture and dependency graphs with node selection, filtering, zoom, and pan (Milestone 5, Phases 2–3).

### Semantic Search and RAG
- **LangChain text splitters**: Language-aware code chunking (Milestone 3).
- **HuggingFace sentence-transformers**: all-MiniLM-L6-v2 code embeddings (Milestone 3).
- **ChromaDB**: Persistent repository-specific vector indexes (Milestone 3).
- **Groq API**: Grounded repository answers using a configurable chat-completions model (Milestone 4).

---

## 📂 Project Structure

```
repoguide-ai/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py              # Environment configuration & limits
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── health.py              # Health, Welcome, Error schemas
│   │   │   └── repository.py          # RepositoryRequest, RepositoryFile, RepositoryResponse
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py              # GET /api/health
│   │   │   ├── root.py                # GET /
│   │   │   └── repository.py          # Ingestion, indexing & semantic search APIs
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── health_service.py      # Health & uptime diagnostics
│   │   │   ├── code_parser.py         # File extension classification & filtering
│   │   │   ├── github_service.py      # GitHub API client, tree fetch & concurrent file download
│   │   │   ├── chunking_service.py    # Language-aware chunking and source line ranges
│   │   │   ├── embedding_service.py   # SentenceTransformer embedding generation
│   │   │   ├── indexing_service.py    # Repository indexing and search orchestration
│   │   │   ├── vector_store.py        # Persistent, repository-isolated ChromaDB store
│   │   │   ├── repository_snapshot_service.py # Cached source snapshots for reuse
│   │   │   ├── architecture_service.py # Deterministic structure and relationship analysis
│   │   │   ├── dependency_service.py   # Local imports, graph edges, and cycles
│   │   │   ├── indexing_status_service.py # Repository-specific indexing lifecycle
│   │   │   └── dashboard_service.py    # Repository metrics and session analytics
│   │   ├── __init__.py
│   │   └── main.py                    # FastAPI application initialization & middleware
│   ├── tests/
│   │   └── test_milestone2.py         # Integration test suite
│   ├── requirements.txt               # Backend dependencies
│   ├── .env.example                   # Backend environment template
│   ├── .env                           # Local environment config (git-ignored)
│   └── .gitignore                     # Python-specific git ignore
│
├── frontend/
│   ├── public/                        # Static assets
│   ├── src/
│   │   ├── components/
│   │   │   ├── ConnectionCard.jsx     # Live backend connection test widget
│   │   │   ├── RepoIngestionCard.jsx  # Repository URL ingestion & code explorer dashboard
│   │   │   ├── ArchitectureVisualizer.jsx # Interactive architecture graph
│   │   │   ├── DependencyExplorer.jsx # Interactive dependency graph
│   │   │   ├── RepositoryDashboard.jsx # Q&A activity and repository overview
│   │   │   ├── Footer.jsx             # Dashboard footer
│   │   │   ├── Hero.jsx               # Headline and value proposition
│   │   │   ├── Navbar.jsx             # Top bar navigation & Swagger link
│   │   │   └── RoadmapCard.jsx        # Project phase tracker
│   │   ├── pages/
│   │   │   └── Home.jsx               # Main landing page view
│   │   ├── services/
│   │   │   └── api.js                 # Centralized Axios client & API endpoints
│   │   ├── App.jsx                    # Root application component
│   │   ├── index.css                  # Tailwind CSS imports & global styles
│   │   └── main.jsx                   # Vite React DOM entry point
│   ├── index.html                     # HTML shell
│   ├── package.json                   # Frontend dependencies & scripts
│   ├── vite.config.js                 # Vite + Tailwind CSS plugin configuration
│   ├── .env.example                   # Frontend environment template
│   ├── .env                           # Local environment config (git-ignored)
│   └── .gitignore                     # Node-specific git ignore
│
├── .gitignore                         # Repository-level git ignore
└── README.md                          # Documentation
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+** (Python 3.13 tested)
- **Node.js 18+** (Node.js 24 tested) & **npm**

---

### Backend Setup

1. Open a terminal and navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   - **Windows:**
     ```bash
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. Install required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   *(Optional)* Add a `GITHUB_TOKEN` to `.env` to raise the GitHub rate limit from 60 to 5,000 requests/hour.

---

### Frontend Setup

1. Open a separate terminal and navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Install npm dependencies:
   ```bash
   npm install
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

---

## 💻 Running the Application

### 1. Start the Backend Server
From the `backend/` folder (with virtual environment active):
```bash
  uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
```
- API is available at: [http://localhost:8000](http://localhost:8000)
- Swagger Interactive Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Alternative ReDoc Documentation: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 2. Start the Frontend Server
From the `frontend/` folder:
```bash
npm run dev
```
- Frontend application will run at: [http://localhost:5173](http://localhost:5173)

---

## 📡 API Documentation

| Method | Endpoint | Description | Request Body | Response Schema |
|---|---|---|---|---|
| `GET` | `/` | Application welcome message & route index | None | `WelcomeResponse` |
| `GET` | `/api/health` | Backend status, uptime, and timestamp | None | `HealthResponse` |
| `POST` | `/api/repositories/ingest` | Ingest public GitHub repository & download source files | `RepositoryRequest` | `RepositoryResponse` |
| `POST` | `/api/repositories/index` | Chunk, embed, and persist a repository code index | `RepositoryIndexRequest` | `RepositoryIndexResponse` |
| `POST` | `/api/repositories/search` | Semantic search within one indexed repository | `SearchRequest` | `SearchResponse` |
| `POST` | `/api/repositories/ask` | Generate a cited, context-grounded answer | `RepositoryAskRequest` | `RepositoryAskResponse` |
| `POST` | `/api/repositories/conversations` | Create a session-scoped repository conversation | `ConversationCreateRequest` | `ConversationDetailResponse` |
| `GET` | `/api/repositories/conversations?repo_url=…&session_id=…` | List conversations for this repository and browser session | Query parameters | `ConversationListResponse` |
| `GET` | `/api/repositories/conversations/{conversation_id}?repo_url=…&session_id=…` | Load a conversation transcript and citations | Query parameters | `ConversationDetailResponse` |
| `GET` | `/api/repositories/suggestions?repo_url=…` | Suggest questions using indexed paths and declarations | Query parameter | `SuggestedQuestionsResponse` |
| `POST` | `/api/repositories/architecture` | Analyze a cached source snapshot into architecture components and relationships | `RepositoryArchitectureRequest` | `RepositoryArchitectureResponse` |
| `POST` | `/api/repositories/dependencies` | Extract repository-local file dependencies from a cached snapshot | `RepositoryDependenciesRequest` | `RepositoryDependenciesResponse` |
| `GET` | `/api/repositories/dashboard?repo_url=…&session_id=…` | Repository indexing metrics and this session’s Q&A analytics | Query parameters | `RepositoryDashboardResponse` |
| `GET` | `/docs` | OpenAPI / Swagger interactive test interface | None | HTML / UI |
| `GET` | `/openapi.json` | Raw OpenAPI 3.1 specification schema | None | JSON |

### Sample `POST /api/repositories/ingest` Request
```json
{
  "repo_url": "https://github.com/psf/requests"
}
```

### Milestone 3 requests
```json
{"repo_url": "https://github.com/psf/requests"}
```
Send that body to `POST /api/repositories/index`. Search with:
```json
{"repo_url": "https://github.com/psf/requests", "query": "Where is HTTP request logic implemented?", "top_k": 5}
```
The local ChromaDB index is stored in `backend/storage/` by default. The first indexing run may download the embedding model.

### Milestone 4: Ask RepoGuide
Set `GROQ_API_KEY` in `backend/.env` before starting the backend. The key is only read by FastAPI and is never included in frontend configuration or responses. `GROQ_MODEL` defaults to `openai/gpt-oss-120b` and can be changed for a chat-completions model enabled on your Groq account. An empty key returns HTTP 503; a repository without an index returns HTTP 404. Answers include inline `[S1]` citations and matching file/line references. Follow-up turns are passed only to resolve references; factual claims must still be grounded in the latest retrieved source chunks.

Example request:
```json
{
  "repo_url": "https://github.com/psf/requests",
  "question": "How does authentication work?"
}
```

The response includes the answer, repository, source references, and retrieval metadata such as chunk count and top similarity. Set `RAG_MIN_SIMILARITY` in `backend/.env` to adjust when retrieved context is considered sufficient.

For persistent conversations, create one with a browser-generated `session_id`, then send both `session_id` and `conversation_id` with each `/ask` request. The backend reloads recent turns from SQLite and saves each answer with its source citations and retrieval metadata. The session identifier is a browser continuity key, not an authentication credential. Conversation data is stored at `backend/storage/conversations.sqlite3` by default and is excluded from Git. Requests omitting both identifiers retain the stateless Milestone 4 behavior. Suggested questions come from indexed declarations and paths; they are unavailable until indexing completes.

### Milestone 5, Phase 2: Architecture Visualizer

Call `POST /api/repositories/architecture` with `{"repo_url":"https://github.com/psf/requests"}`. The optional `refresh: true` flag fetches the latest bounded ingestion snapshot; otherwise the service reuses the last files saved by `/ingest` or `/index`. If an older repository has an index but no snapshot yet, source is reconstructed from its existing Chroma chunks before any GitHub fetch. Source snapshots are repository-isolated in `backend/storage/repository_snapshots.sqlite3` and excluded from Git.

The response contains repository and directory nodes, source modules, filename-based entry point candidates, detected route declarations, service/controller classes, recognized database or external integrations, and directed relationships. Resolved imports and source declarations are marked `detected`; filename-convention entry points and path-named service/controller roles are marked `inferred`. Unresolved imports do not become edges. Supported source parsers include Python, JavaScript/JSX, TypeScript/TSX, Java, C#, and C++; other ingested files are listed as unsupported for architecture parsing. File-count/size truncation is surfaced in the response so the graph is understood to cover the saved snapshot rather than necessarily the full repository. Groq is not used to create architecture facts.

### Milestone 5, Phase 3: Dependency Graph

Call `POST /api/repositories/dependencies` with `{"repo_url":"https://github.com/psf/requests"}`. By default, the graph includes at most 250 supported files; `max_files` can be set from 20 to 500. The endpoint reuses the saved repository snapshot (or existing Chroma chunks for older indexed repositories) and only fetches GitHub when no local source is available. Set `refresh: true` to request a fresh snapshot.

The response lists file nodes, directed local-import edges with the importing source line and GitHub link, unresolved local imports as separate records, strongly connected cycle groups, isolated files, and truncation statistics. External package imports are not represented as file edges or unresolved local imports. Parsers cover Python, JavaScript/JSX, TypeScript/TSX, and Java; Python syntax errors are skipped. The frontend supports search/language filtering, incoming/outgoing highlighting, cycle highlighting, node details, source links, and directed shortest-path exploration. Dependency facts are parsed from source; no LLM is used to infer edges.

### Milestone 5, Phase 4: Repository Q&A Dashboard

Call `GET /api/repositories/dashboard?repo_url=https://github.com/psf/requests&session_id=<browser-session-uuid>`. Repository indexing counts and status are stored independently per owner/repository; the last-indexed timestamp records successful indexing. Legacy Chroma collections still report their actual file, chunk, and language totals, but do not have a historical timestamp until indexed by a version that stores that status.

Conversation totals, daily question counts, topics, cited files, activity, and conversation history are scoped to both repository and browser session. Topics are deterministic frequent terms from stored questions; file/module activity comes from saved answer citations. Architecture and dependency counts are computed from the existing saved snapshot or Chroma-reconstructed source; the dashboard does not download a repository to calculate these summaries. Empty repositories and sessions return zero/empty analytics rather than sample values.

### Sample `POST /api/repositories/ingest` Response
```json
{
  "owner": "psf",
  "repository": "requests",
  "description": "A simple, yet elegant, HTTP library.",
  "default_branch": "main",
  "stars": 54568,
  "total_source_files_found": 40,
  "files_returned": 40,
  "files_truncated": false,
  "truncation_reason": null,
  "files": [
    {
      "path": "src/requests/api.py",
      "language": "Python",
      "size": 5837,
      "content": "..."
    }
  ]
}
```

---

## 🗺️ Roadmap

- [x] **Milestone 1:** Project Setup, Modular Backend Architecture & React-FastAPI Integration.
- [x] **Milestone 2:** GitHub Repository Ingestion, File Filtering & Concurrent Downloader.
- [x] **Milestone 3:** HuggingFace Embeddings & ChromaDB Vector Store.
- [x] **Milestone 4:** RAG Pipeline with ChromaDB retrieval, Groq chat completions, conversation history, and cited answers.
- [x] **Milestone 5, Phase 1:** Persistent conversational codebase assistant.
- [x] **Milestone 5, Phase 2:** Deterministic repository architecture visualizer.
- [x] **Milestone 5, Phase 3:** Source-backed dependency graph and interactive dependency explorer.
- [x] **Milestone 5, Phase 4:** Repository Q&A dashboard and session-scoped activity analytics.
