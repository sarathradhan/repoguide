/**
 * API Service for RepoGuide AI.
 * Centralized Axios configuration and endpoint handlers.
 */
import axios from 'axios';

// Base URL defaults to localhost:8000 if not specified in environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Format Axios errors into clean user-facing strings.
 */
function extractErrorMessage(error, defaultMsg = 'An unexpected error occurred') {
  if (error.response) {
    const statusCode = error.response.status;
    const detail = error.response.data?.detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d.msg || d.message).join(', ');
    }
    if (typeof detail === 'string') {
      return detail;
    }
    return error.response.data?.error || `HTTP ${statusCode} Error`;
  }
  if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
    return 'Operation timed out. The server or AI model is processing a heavy load.';
  }
  if (error.request) {
    return `Cannot connect to backend at ${API_BASE_URL}. Ensure FastAPI is running.`;
  }
  return error.message || defaultMsg;
}

/**
 * Perform a health check against the backend.
 */
export async function checkBackendHealth() {
  const startTime = performance.now();
  try {
    const response = await apiClient.get('/api/health');
    const latencyMs = Math.round(performance.now() - startTime);
    return {
      success: true,
      data: response.data,
      latencyMs,
      status: response.status,
    };
  } catch (error) {
    const latencyMs = Math.round(performance.now() - startTime);
    return {
      success: false,
      error: extractErrorMessage(error, 'Failed to connect to backend server'),
      latencyMs,
      status: error.response?.status || null,
    };
  }
}

/**
 * Fetch application welcome details from root endpoint.
 */
export async function getRootWelcome() {
  try {
    const response = await apiClient.get('/');
    return {
      success: true,
      data: response.data,
    };
  } catch (error) {
    return {
      success: false,
      error: extractErrorMessage(error),
    };
  }
}

/**
 * Ingest a public GitHub repository and retrieve filtered source files.
 */
export async function ingestRepository(repoUrl) {
  try {
    const response = await apiClient.post(
      '/api/repositories/ingest',
      { repo_url: repoUrl },
      { timeout: 90000 }
    );
    return {
      success: true,
      data: response.data,
      status: response.status,
    };
  } catch (error) {
    return {
      success: false,
      error: extractErrorMessage(error, 'Failed to ingest repository'),
      status: error.response?.status || null,
    };
  }
}

/**
 * Trigger full repository indexing pipeline:
 * Ingest -> Chunk -> HuggingFace Embeddings -> ChromaDB.
 */
export async function indexRepository(repoUrl) {
  try {
    const response = await apiClient.post(
      '/api/repositories/index',
      { repo_url: repoUrl },
      { timeout: 600000 } // First run may download the embedding model.
    );
    return {
      success: true,
      data: response.data,
      status: response.status,
    };
  } catch (error) {
    return {
      success: false,
      error: extractErrorMessage(error, 'Failed to index repository'),
      status: error.response?.status || null,
    };
  }
}

/**
 * Perform dense semantic search over repository code chunks in ChromaDB.
 */
export async function searchRepository(repoUrl, query, topK = 5) {
  try {
    const response = await apiClient.post(
      '/api/repositories/search',
      { repo_url: repoUrl, query, top_k: topK },
      { timeout: 30000 }
    );
    return {
      success: true,
      data: response.data,
      status: response.status,
    };
  } catch (error) {
    return {
      success: false,
      error: extractErrorMessage(error, 'Semantic search query failed'),
      status: error.response?.status || null,
    };
  }
}

/** Ask a grounded question about an indexed repository. */
export async function askRepository(repoUrl, question, topK = 5, conversation = {}) {
  try {
    const response = await apiClient.post(
      '/api/repositories/ask',
      {
        repo_url: repoUrl,
        question,
        top_k: topK,
        ...(conversation.sessionId && conversation.conversationId
          ? { session_id: conversation.sessionId, conversation_id: conversation.conversationId }
          : { conversation_history: conversation.history || [] }),
      },
      { timeout: 90000 }
    );
    return { success: true, data: response.data, status: response.status };
  } catch (error) {
    return {
      success: false,
      error: extractErrorMessage(error, 'Failed to answer repository question'),
      status: error.response?.status || null,
    };
  }
}

export async function createConversation(repoUrl, sessionId) {
  try {
    const response = await apiClient.post('/api/repositories/conversations', { repo_url: repoUrl, session_id: sessionId });
    return { success: true, data: response.data, status: response.status };
  } catch (error) {
    return { success: false, error: extractErrorMessage(error, 'Could not start a conversation'), status: error.response?.status || null };
  }
}

export async function listConversations(repoUrl, sessionId) {
  try {
    const response = await apiClient.get('/api/repositories/conversations', { params: { repo_url: repoUrl, session_id: sessionId } });
    return { success: true, data: response.data, status: response.status };
  } catch (error) {
    return { success: false, error: extractErrorMessage(error, 'Could not load conversations'), status: error.response?.status || null };
  }
}

export async function getConversation(repoUrl, sessionId, conversationId) {
  try {
    const response = await apiClient.get(`/api/repositories/conversations/${conversationId}`, { params: { repo_url: repoUrl, session_id: sessionId } });
    return { success: true, data: response.data, status: response.status };
  } catch (error) {
    return { success: false, error: extractErrorMessage(error, 'Could not load conversation'), status: error.response?.status || null };
  }
}

export async function getSuggestedQuestions(repoUrl) {
  try {
    const response = await apiClient.get('/api/repositories/suggestions', { params: { repo_url: repoUrl } });
    return { success: true, data: response.data };
  } catch (error) {
    return { success: false, error: extractErrorMessage(error, 'Index this repository to get suggested questions') };
  }
}

/** Analyze cached repository files into a deterministic component and relationship graph. */
export async function analyzeRepositoryArchitecture(repoUrl, refresh = false) {
  try {
    const response = await apiClient.post(
      '/api/repositories/architecture',
      { repo_url: repoUrl, refresh },
      { timeout: refresh ? 90000 : 30000 }
    );
    return { success: true, data: response.data, status: response.status };
  } catch (error) {
    return {
      success: false,
      error: extractErrorMessage(error, 'Could not analyze repository architecture'),
      status: error.response?.status || null,
    };
  }
}

/** Extract actual local file dependencies from the repository snapshot. */
export async function analyzeRepositoryDependencies(repoUrl, options = {}) {
  try {
    const response = await apiClient.post(
      '/api/repositories/dependencies',
      { repo_url: repoUrl, refresh: Boolean(options.refresh), max_files: options.maxFiles || 250 },
      { timeout: options.refresh ? 90000 : 30000 }
    );
    return { success: true, data: response.data, status: response.status };
  } catch (error) {
    return {
      success: false,
      error: extractErrorMessage(error, 'Could not analyze repository dependencies'),
      status: error.response?.status || null,
    };
  }
}

/** Load repository metrics and analytics for the active browser conversation session. */
export async function getRepositoryDashboard(repoUrl, sessionId) {
  try {
    const response = await apiClient.get('/api/repositories/dashboard', {
      params: { repo_url: repoUrl, session_id: sessionId },
      timeout: 60000,
    });
    return { success: true, data: response.data, status: response.status };
  } catch (error) {
    return { success: false, error: extractErrorMessage(error, 'Could not load repository dashboard'), status: error.response?.status || null };
  }
}

export default {
  checkBackendHealth,
  getRootWelcome,
  ingestRepository,
  indexRepository,
  searchRepository,
  askRepository,
  createConversation,
  listConversations,
  getConversation,
  getSuggestedQuestions,
  analyzeRepositoryArchitecture,
  analyzeRepositoryDependencies,
  getRepositoryDashboard,
  apiClient,
};
