/**
 * API configuration for the Acme CSV Import Platform.
 * 
 * Defines the base URL for API requests, read from environment variables
 * with a fallback to localhost for development.
 */

/**
 * Base URL for the API server.
 * 
 * Reads from `VITE_API_BASE_URL` environment variable.
 * Defaults to `http://localhost:8000` if not set.
 */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * API prefix used by the backend (e.g., "/api").
 * This is prepended to all API routes.
 */
export const API_PREFIX = "/api";

/**
 * Full base URL including the API prefix.
 */
export const API_URL = `${API_BASE_URL}${API_PREFIX}`;

