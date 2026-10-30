# RepoGuide AI 🧭⚡

> **AI-Powered GitHub Repository Understanding Assistant**
> Accelerate codebase onboarding, trace complex architecture, and query repository semantics.

---

## 📋 Table of Contents
- [Overview](#overview)
- [Milestone 1 Objectives](#milestone-1-objectives)
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

**Milestone 1** establishes the clean, modular foundation:
- A production-grade **FastAPI** backend with CORS middleware, centralized settings, and structured health diagnostics.
- A modern, developer-centric **React + Vite** frontend styled with **Tailwind CSS**.
- A decoupled **Axios** API integration layer with automated latency measurement and graceful error handling.

---

## 🛠 Technology Stack

### Backend
- **Python 3.13+**
- **FastAPI**: Modern, fast web framework for building APIs.
- **Uvicorn**: Lightning-fast ASGI server.
- **HTTPX**: Async HTTP client for future external API communications.
- **Pydantic v2**: High-performance data validation and settings management.
- **Python-dotenv**: Environment variable management.

### Frontend
- **React 19**: Component-driven UI library.
- **Vite 8**: Next-generation frontend tooling and bundler.
- **Tailwind CSS v4**: Utility-first CSS framework with Vite integration.
- **Axios**: Promise-based HTTP client for browser requests.
- **Lucide React**: Clean, modern developer iconography.

### Future AI Stack *(Milestones 2–5)*
- **LangChain**: Orchestration framework for RAG and LLM chains.
- **HuggingFace Embeddings**: Code semantic representation.
- **ChromaDB**: High-performance local vector database.
- **Groq API**: Ultra-fast LLM inference for code comprehension.

---

## 📂 Project Structure

```
repoguide-ai/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── config.py              # Environment configuration & CORS settings
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── health.py              # Pydantic schemas (Health, Welcome, Error)
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── health.py              # GET /api/health endpoint
│   │   │   └── root.py                # GET / root welcome endpoint
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── health_service.py      # Business logic & uptime tracking
│   │   ├── __init__.py
│   │   └── main.py                    # FastAPI application initialization & middleware
│   ├── requirements.txt               # Backend dependencies
│   ├── .env.example                   # Backend environment template
│   ├── .env                           # Local environment config (git-ignored)
│   └── .gitignore                     # Python-specific git ignore
│
├── frontend/
│   ├── public/                        # Static assets
│   ├── src/
│   │   ├── components/
│   │   │   ├── ConnectionCard.jsx     # Interactive backend connection test widget
│   │   │   ├── Footer.jsx             # Dashboard footer
│   │   │   ├── Hero.jsx               # Headline and value proposition
│   │   │   ├── Navbar.jsx             # Top bar navigation & Swagger link
│   │   │   └── RoadmapCard.jsx        # Project phase tracker
│   │   ├── pages/
│   │   │   └── Home.jsx               # Main landing page view
│   │   ├── services/
│   │   │   └── api.js                 # Centralized Axios client & health check API
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

| Method | Endpoint | Description | Response Schema |
|---|---|---|---|
| `GET` | `/` | Application welcome message & route index | `WelcomeResponse` |
| `GET` | `/api/health` | Backend status, uptime, and timestamp | `HealthResponse` |
| `GET` | `/docs` | OpenAPI / Swagger interactive test interface | HTML / UI |
| `GET` | `/openapi.json` | Raw OpenAPI 3.1 specification schema | JSON |

### Sample `GET /api/health` Response
```json
{
  "status": "healthy",
  "service": "RepoGuide AI",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-10-30T14:34:50.482756Z",
  "uptime_seconds": 12.45
}
```

---

## 🗺️ Roadmap

- [x] **Milestone 1:** Project Setup, Modular Backend Architecture & React-FastAPI Integration.
- [ ] **Milestone 2:** GitHub Repository Ingestion, File Filtering & Code Chunking.
- [ ] **Milestone 3:** HuggingFace Embeddings & ChromaDB Vector Store.
- [ ] **Milestone 4:** RAG Pipeline with LangChain & Groq API.
- [ ] **Milestone 5:** Interactive Repository Exploration UI & Code Chat.

