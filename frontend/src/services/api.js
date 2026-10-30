/**
 * API Service for RepoGuide AI.
 * Centralized Axios configuration and endpoint handlers.
 */
import axios from 'axios';

// Base URL defaults to localhost:8000 if not specified in environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 8000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Perform a health check against the backend.
 * Measures roundtrip latency and standardizes response format.
 *
 * @returns {Promise<{success: boolean, data?: object, error?: string, latencyMs: number, status?: number}>}
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

    let errorMessage = 'Failed to connect to backend server';
    let statusCode = null;

    if (error.response) {
      // Server responded with non-2xx status
      statusCode = error.response.status;
      errorMessage = error.response.data?.detail || error.response.data?.message || `HTTP ${statusCode} Error`;
    } else if (error.request) {
      // Request made but no response received (e.g. server down, CORS error)
      errorMessage = `Cannot reach backend at ${API_BASE_URL}. Ensure FastAPI is running.`;
    } else {
      errorMessage = error.message;
    }

    return {
      success: false,
      error: errorMessage,
      latencyMs,
      status: statusCode,
    };
  }
}

/**
 * Fetch application welcome details from root endpoint.
 *
 * @returns {Promise<{success: boolean, data?: object, error?: string}>}
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
      error: error.response?.data?.detail || error.message,
    };
  }
}

export default {
  checkBackendHealth,
  getRootWelcome,
  apiClient,
};

