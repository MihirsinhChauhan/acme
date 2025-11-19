/**
 * React hook for tracking import progress via Server-Sent Events (SSE).
 * 
 * Subscribes to the SSE stream for a given job ID and provides real-time
 * progress updates. Automatically handles reconnection and cleanup.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import type { ProgressEvent, ImportJobStatus } from "@/types/api";
import { getProgressSseUrl } from "./useUpload";

/**
 * State of the progress tracking connection.
 */
export type ProgressConnectionState = "idle" | "connecting" | "connected" | "closed" | "error";

/**
 * Options for the useProgress hook.
 */
export interface UseProgressOptions {
  /**
   * Callback fired when progress is updated.
   */
  onProgress?: (event: ProgressEvent) => void;
  
  /**
   * Callback fired when the connection is established.
   */
  onConnect?: () => void;
  
  /**
   * Callback fired when the connection is closed.
   */
  onClose?: () => void;
  
  /**
   * Callback fired when an error occurs.
   */
  onError?: (error: Error) => void;
  
  /**
   * Whether to automatically connect when jobId is provided.
   * Defaults to true.
   */
  autoConnect?: boolean;
  
  /**
   * Reconnection configuration.
   * If enabled, the hook will attempt to reconnect on disconnect.
   */
  reconnect?: {
    enabled: boolean;
    maxAttempts?: number;
    delay?: number; // milliseconds
  };
}

/**
 * Return type for the useProgress hook.
 */
export interface UseProgressReturn {
  /**
   * Current progress event data, or null if not available.
   */
  progress: ProgressEvent | null;
  
  /**
   * Current connection state.
   */
  connectionState: ProgressConnectionState;
  
  /**
   * Whether the job has completed (status is 'done' or 'failed').
   */
  isComplete: boolean;
  
  /**
   * Whether the job has failed.
   */
  isFailed: boolean;
  
  /**
   * Manually connect to the SSE stream.
   */
  connect: () => void;
  
  /**
   * Manually disconnect from the SSE stream.
   */
  disconnect: () => void;
  
  /**
   * Error message if connection failed.
   */
  error: string | null;
}

/**
 * Hook for tracking import progress via SSE.
 * 
 * @param jobId - The job ID to track progress for
 * @param options - Configuration options
 * 
 * @example
 * ```tsx
 * const { progress, connectionState, isComplete } = useProgress(jobId, {
 *   onProgress: (event) => {
 *     console.log('Progress:', event.progress_percent);
 *   },
 * });
 * ```
 */
export function useProgress(
  jobId: string | null,
  options: UseProgressOptions = {}
): UseProgressReturn {
  const {
    onProgress,
    onConnect,
    onClose,
    onError,
    autoConnect = true,
    reconnect = { enabled: false },
  } = options;

  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [connectionState, setConnectionState] = useState<ProgressConnectionState>("idle");
  const [error, setError] = useState<string | null>(null);
  
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const isConnectingRef = useRef(false);
  const latestProgressRef = useRef<ProgressEvent | null>(null);

  /**
   * Parse SSE data from EventSource message.
   * 
   * Note: EventSource automatically strips the "data: " prefix,
   * so event.data is already just the JSON string.
   * 
   * Also normalizes field names from backend (e.g., "progress" -> "progress_percent").
   */
  const parseSseData = useCallback((dataStr: string): ProgressEvent | null => {
    // EventSource already provides just the data content (no "data: " prefix)
    if (!dataStr || dataStr.trim() === "") {
      return null;
    }

    try {
      const data = JSON.parse(dataStr);
      
      // Handle special events (close, error)
      if (data.event === "close") {
        return null;
      }
      if (data.event === "error") {
        throw new Error(data.message || "Unknown error from SSE stream");
      }

      // Normalize field names: backend sends "progress" but our type expects "progress_percent"
      const normalizedData: ProgressEvent = {
        job_id: data.job_id || "",
        status: data.status,
        stage: data.stage ?? null,
        total_rows: data.total_rows ?? null,
        processed_rows: data.processed_rows ?? 0,
        progress_percent: data.progress_percent ?? data.progress ?? null, // Support both field names
        error_message: data.error_message ?? null,
        // Handle updated_at: backend sends Unix timestamp, but we expect ISO string (optional)
        updated_at: data.updated_at 
          ? (typeof data.updated_at === "number" 
              ? new Date(data.updated_at * 1000).toISOString() 
              : data.updated_at)
          : null,
      };

      // Validate required fields
      if (!normalizedData.status || normalizedData.processed_rows === undefined) {
        console.warn("Received invalid progress event (missing required fields):", data);
        return null;
      }

      return normalizedData;
    } catch (err) {
      console.error("Failed to parse SSE data:", err, "Raw data:", dataStr);
      return null;
    }
  }, []);

  /**
   * Connect to the SSE stream.
   */
  const connect = useCallback(() => {
    if (!jobId) {
      return;
    }

    // Prevent multiple connections
    if (isConnectingRef.current || eventSourceRef.current?.readyState === EventSource.OPEN) {
      return;
    }

    // Reset reconnect attempts if we're manually connecting
    if (connectionState === "idle") {
      reconnectAttemptsRef.current = 0;
    }

    isConnectingRef.current = true;
    setConnectionState("connecting");
    setError(null);

    // Clean up existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Clear any pending reconnection
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    try {
      const url = getProgressSseUrl(jobId);
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        isConnectingRef.current = false;
        setConnectionState("connected");
        reconnectAttemptsRef.current = 0; // Reset on successful connection
        onConnect?.();
      };

      eventSource.onmessage = (event) => {
        // Debug: log raw event data
        console.debug("SSE message received:", event.data);
        
        const progressEvent = parseSseData(event.data);
        
        if (progressEvent) {
          console.debug("Parsed progress event:", progressEvent);
          latestProgressRef.current = progressEvent;
          setProgress(progressEvent);
          onProgress?.(progressEvent);
          
          // If job completed, close connection
          if (progressEvent.status === "done" || progressEvent.status === "failed") {
            setTimeout(() => {
              eventSource.close();
              eventSourceRef.current = null;
              setConnectionState("closed");
              onClose?.();
            }, 100); // Small delay to ensure last message is processed
          }
        } else {
          console.debug("Failed to parse progress event from:", event.data);
        }
      };

      eventSource.onerror = (event) => {
        isConnectingRef.current = false;
        const currentState = eventSource.readyState;

        if (currentState === EventSource.CLOSED) {
          // Stream closed (job completed or server closed connection)
          eventSource.close();
          eventSourceRef.current = null;
          
          // Check if job is complete using latest progress
          const latestProgress = latestProgressRef.current;
          if (latestProgress?.status === "done" || latestProgress?.status === "failed") {
            // Job completed normally - connection closed as expected
            setConnectionState("closed");
            onClose?.();
            return;
          }
          
          // Job not complete - attempt reconnection if enabled
          if (reconnect.enabled && reconnectAttemptsRef.current < (reconnect.maxAttempts ?? 5)) {
            const delay = (reconnect.delay ?? 1000) * Math.pow(2, reconnectAttemptsRef.current);
            reconnectAttemptsRef.current += 1;
            
            reconnectTimeoutRef.current = setTimeout(() => {
              connect();
            }, delay);
          } else {
            // Max reconnection attempts reached or reconnection disabled
            setConnectionState("error");
            const err = new Error("SSE connection closed unexpectedly");
            setError(err.message);
            onError?.(err);
            onClose?.();
          }
        } else {
          // Connection error (but not closed)
          setConnectionState("error");
          const err = new Error("SSE connection error");
          setError(err.message);
          onError?.(err);
        }
      };
    } catch (err) {
      isConnectingRef.current = false;
      setConnectionState("error");
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error.message);
      onError?.(error);
    }
  }, [jobId, connectionState, progress, onProgress, onConnect, onClose, onError, reconnect, parseSseData]);

  /**
   * Disconnect from the SSE stream.
   */
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    setConnectionState("idle");
    reconnectAttemptsRef.current = 0;
  }, []);

  // Auto-connect when jobId is provided
  useEffect(() => {
    if (autoConnect && jobId && connectionState === "idle") {
      connect();
    }
  }, [autoConnect, jobId, connectionState, connect]);

  // Cleanup on unmount or jobId change
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Disconnect when jobId changes to null
  useEffect(() => {
    if (!jobId) {
      disconnect();
      setProgress(null);
      latestProgressRef.current = null;
      setError(null);
    }
  }, [jobId, disconnect]);

  const isComplete = progress?.status === "done" || progress?.status === "failed";
  const isFailed = progress?.status === "failed";

  return {
    progress,
    connectionState,
    isComplete,
    isFailed,
    connect,
    disconnect,
    error,
  };
}

