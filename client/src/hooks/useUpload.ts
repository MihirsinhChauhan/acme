/**
 * React hook for uploading CSV files and initiating import jobs.
 * 
 * Uses React Query's useMutation to handle file uploads with proper
 * error handling and success callbacks.
 */

import { useMutation } from "@tanstack/react-query";
import { postFormData } from "@/lib/api/client";
import type { UploadResponse } from "@/types/api";
import { API_BASE_URL, API_PREFIX } from "@/lib/api/config";

/**
 * Upload a CSV file and initiate an import job.
 * 
 * @param file - The CSV file to upload
 * @returns Promise that resolves to UploadResponse with job_id and sse_url
 */
async function uploadCsvFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return postFormData<UploadResponse>("upload", formData);
}

/**
 * Hook for uploading CSV files.
 * 
 * @example
 * ```tsx
 * const upload = useUpload({
 *   onSuccess: (response) => {
 *     console.log('Upload successful, job ID:', response.job_id);
 *   },
 *   onError: (error) => {
 *     console.error('Upload failed:', error);
 *   },
 * });
 * 
 * // Later, trigger upload:
 * upload.mutate(file);
 * ```
 */
export function useUpload(
  options?: {
    onSuccess?: (data: UploadResponse) => void;
    onError?: (error: Error) => void;
  }
) {
  return useMutation({
    mutationFn: uploadCsvFile,
    onSuccess: (data) => {
      options?.onSuccess?.(data);
    },
    onError: (error) => {
      options?.onError?.(
        error instanceof Error ? error : new Error(String(error))
      );
    },
  });
}

/**
 * Get the SSE URL for a job ID.
 * 
 * @param jobId - The job ID to get the SSE URL for
 * @returns The full SSE URL for progress tracking
 */
export function getProgressSseUrl(jobId: string): string {
  return `${API_BASE_URL}${API_PREFIX}/progress/${jobId}`;
}

