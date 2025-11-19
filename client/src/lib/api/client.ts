/**
 * HTTP client utility for making API requests.
 * 
 * Provides typed request functions (get, post, put, delete, postFormData)
 * with automatic base URL configuration and error handling.
 */

import { API_URL } from "./config";

/**
 * Custom error class for API errors.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Options for API requests.
 */
interface RequestOptions {
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

/**
 * Parse JSON response or throw an error.
 */
async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type");
  
  // Handle empty responses (e.g., 204 No Content)
  if (response.status === 204 || response.statusText === "No Content") {
    return undefined as T;
  }

  // Try to parse JSON, but handle non-JSON responses gracefully
  if (contentType && contentType.includes("application/json")) {
    const data = await response.json();
    
    if (!response.ok) {
      throw new ApiError(
        data.detail || data.message || response.statusText,
        response.status,
        data
      );
    }
    
    return data as T;
  }

  // For non-JSON responses, throw error if not OK
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(
      text || response.statusText,
      response.status,
      text
    );
  }

  // Return empty object for successful non-JSON responses
  return {} as T;
}

/**
 * Build full URL from endpoint path.
 */
function buildUrl(endpoint: string): string {
  // If endpoint already includes the base URL, use it as-is
  if (endpoint.startsWith("http://") || endpoint.startsWith("https://")) {
    return endpoint;
  }
  
  // Remove leading slash if present to avoid double slashes
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint.slice(1) : endpoint;
  return `${API_URL}/${cleanEndpoint}`;
}

/**
 * Build headers for requests.
 */
function buildHeaders(customHeaders?: Record<string, string>, omitContentType = false): HeadersInit {
  const headers: Record<string, string> = { ...customHeaders };

  // Only add Content-Type if not omitted (e.g., for FormData)
  if (!omitContentType) {
    headers["Content-Type"] = "application/json";
  }

  return headers;
}

/**
 * Perform a GET request.
 */
export async function get<T>(
  endpoint: string,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(endpoint);
  const response = await fetch(url, {
    method: "GET",
    headers: buildHeaders(options?.headers),
    signal: options?.signal,
  });

  return parseResponse<T>(response);
}

/**
 * Perform a POST request with JSON body.
 */
export async function post<T>(
  endpoint: string,
  data?: unknown,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(endpoint);
  const response = await fetch(url, {
    method: "POST",
    headers: buildHeaders(options?.headers),
    body: data ? JSON.stringify(data) : undefined,
    signal: options?.signal,
  });

  return parseResponse<T>(response);
}

/**
 * Perform a PUT request with JSON body.
 */
export async function put<T>(
  endpoint: string,
  data?: unknown,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(endpoint);
  const response = await fetch(url, {
    method: "PUT",
    headers: buildHeaders(options?.headers),
    body: data ? JSON.stringify(data) : undefined,
    signal: options?.signal,
  });

  return parseResponse<T>(response);
}

/**
 * Perform a DELETE request.
 */
export async function del<T>(
  endpoint: string,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(endpoint);
  const response = await fetch(url, {
    method: "DELETE",
    headers: buildHeaders(options?.headers),
    signal: options?.signal,
  });

  return parseResponse<T>(response);
}

/**
 * Perform a POST request with FormData (for file uploads).
 * Note: Content-Type is omitted to let the browser set it with the boundary.
 */
export async function postFormData<T>(
  endpoint: string,
  formData: FormData,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(endpoint);
  
  // Don't set Content-Type for FormData - browser will set it with boundary
  const response = await fetch(url, {
    method: "POST",
    headers: buildHeaders(options?.headers, true), // omit Content-Type
    body: formData,
    signal: options?.signal,
  });

  return parseResponse<T>(response);
}

