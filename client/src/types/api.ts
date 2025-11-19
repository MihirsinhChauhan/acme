/**
 * TypeScript type definitions for API requests and responses.
 * 
 * These types match the Pydantic schemas defined in the FastAPI backend.
 */

/**
 * Import job status enum matching backend ImportStatus.
 */
export enum ImportJobStatus {
  QUEUED = "queued",
  UPLOADING = "uploading",
  PARSING = "parsing",
  IMPORTING = "importing",
  DONE = "done",
  FAILED = "failed",
}

/**
 * Job type enum matching backend JobType.
 */
export enum JobType {
  IMPORT = "import",
  BULK_DELETE = "bulk_delete",
}

// ============================================================================
// Product Types
// ============================================================================

/**
 * Product base attributes.
 */
export interface Product {
  id: number;
  sku: string;
  name: string;
  description: string | null;
  active: boolean;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

/**
 * Product creation payload.
 */
export interface ProductCreate {
  sku: string;
  name: string;
  description?: string | null;
  active?: boolean;
}

/**
 * Product update payload (all fields optional).
 */
export interface ProductUpdate {
  sku?: string | null;
  name?: string | null;
  description?: string | null;
  active?: boolean | null;
}

/**
 * Paginated product list response.
 */
export interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
}

// ============================================================================
// Import/Upload Types
// ============================================================================

/**
 * Upload response after CSV file upload.
 */
export interface UploadResponse {
  job_id: string; // UUID as string
  sse_url: string;
  message: string;
}

/**
 * Progress event from SSE stream.
 */
export interface ProgressEvent {
  job_id: string; // UUID as string
  status: ImportJobStatus;
  stage?: string | null; // e.g., "uploading", "parsing", "batch info"
  total_rows?: number | null;
  processed_rows: number;
  progress_percent?: number | null; // 0-100
  error_message?: string | null;
  updated_at?: string | null; // ISO datetime string
}

// ============================================================================
// Bulk Delete Types
// ============================================================================

/**
 * Bulk delete response after initiating bulk delete operation.
 */
export interface BulkDeleteResponse {
  job_id: string; // UUID as string
  sse_url: string;
  message: string;
}

// ============================================================================
// Webhook Types
// ============================================================================

/**
 * Webhook response model.
 */
export interface Webhook {
  id: number;
  url: string;
  events: string[];
  enabled: boolean;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

/**
 * Webhook creation payload.
 */
export interface WebhookCreate {
  url: string;
  events: string[];
  enabled?: boolean;
}

/**
 * Webhook update payload (all fields optional).
 */
export interface WebhookUpdate {
  url?: string | null;
  events?: string[] | null;
  enabled?: boolean | null;
}

/**
 * Webhook test response.
 */
export interface WebhookTestResponse {
  success: boolean;
  response_code?: number | null;
  response_time_ms?: number | null;
  response_body?: string | null;
  error?: string | null;
}

/**
 * Webhook delivery response (for delivery history).
 */
export interface WebhookDeliveryResponse {
  id: number;
  webhook_id: number;
  event_type: string;
  status: string; // "pending", "success", "failed"
  response_code?: number | null;
  response_time_ms?: number | null;
  attempted_at: string; // ISO datetime string
  completed_at?: string | null; // ISO datetime string
}

