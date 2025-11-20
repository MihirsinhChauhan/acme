/**
 * React hooks for webhook CRUD operations.
 * 
 * Provides React Query hooks for fetching, creating, updating, deleting, testing webhooks,
 * and fetching delivery history.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, put, del } from "@/lib/api/client";
import type {
  Webhook,
  WebhookCreate,
  WebhookUpdate,
  WebhookTestResponse,
  WebhookDeliveryResponse,
} from "@/types/api";

/**
 * Query parameters for listing webhook deliveries.
 */
export interface WebhookDeliveriesParams {
  page?: number;
  page_size?: number;
}

/**
 * Fetch all webhooks.
 */
async function fetchWebhooks(): Promise<Webhook[]> {
  return get<Webhook[]>("webhooks");
}

/**
 * Fetch a single webhook by ID.
 */
async function fetchWebhook(id: number): Promise<Webhook> {
  return get<Webhook>(`webhooks/${id}`);
}

/**
 * Create a new webhook.
 */
async function createWebhook(data: WebhookCreate): Promise<Webhook> {
  return post<Webhook>("webhooks", data);
}

/**
 * Update a webhook by ID.
 */
async function updateWebhook(id: number, data: WebhookUpdate): Promise<Webhook> {
  return put<Webhook>(`webhooks/${id}`, data);
}

/**
 * Delete a webhook by ID.
 */
async function deleteWebhook(id: number): Promise<void> {
  return del<void>(`webhooks/${id}`);
}

/**
 * Test a webhook by ID.
 */
async function testWebhook(id: number): Promise<WebhookTestResponse> {
  return post<WebhookTestResponse>(`webhooks/${id}/test`);
}

/**
 * Fetch webhook delivery history.
 */
async function fetchWebhookDeliveries(
  id: number,
  params: WebhookDeliveriesParams = {}
): Promise<WebhookDeliveryResponse[]> {
  const queryParams = new URLSearchParams();
  
  if (params.page) queryParams.append("page", String(params.page));
  if (params.page_size) queryParams.append("page_size", String(params.page_size));

  const queryString = queryParams.toString();
  const endpoint = queryString ? `webhooks/${id}/deliveries?${queryString}` : `webhooks/${id}/deliveries`;
  
  return get<WebhookDeliveryResponse[]>(endpoint);
}

/**
 * Query key factory for webhooks.
 */
export const webhookKeys = {
  all: ["webhooks"] as const,
  lists: () => [...webhookKeys.all, "list"] as const,
  details: () => [...webhookKeys.all, "detail"] as const,
  detail: (id: number) => [...webhookKeys.details(), id] as const,
  deliveries: (id: number) => [...webhookKeys.detail(id), "deliveries"] as const,
  deliveriesList: (id: number, params: WebhookDeliveriesParams) =>
    [...webhookKeys.deliveries(id), params] as const,
};

/**
 * Hook for fetching all webhooks.
 * 
 * @example
 * ```tsx
 * const { data, isLoading, error } = useWebhooks();
 * ```
 */
export function useWebhooks(options?: {
  enabled?: boolean;
}) {
  return useQuery({
    queryKey: webhookKeys.lists(),
    queryFn: fetchWebhooks,
    enabled: options?.enabled !== false,
  });
}

/**
 * Hook for fetching a single webhook by ID.
 * 
 * @param id - Webhook ID
 * @param options - React Query options
 * 
 * @example
 * ```tsx
 * const { data, isLoading } = useWebhook(1);
 * ```
 */
export function useWebhook(
  id: number | null,
  options?: {
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: webhookKeys.detail(id!),
    queryFn: () => fetchWebhook(id!),
    enabled: options?.enabled !== false && id !== null,
  });
}

/**
 * Hook for creating a new webhook.
 * 
 * @example
 * ```tsx
 * const createWebhook = useCreateWebhook({
 *   onSuccess: (webhook) => {
 *     console.log('Webhook created:', webhook);
 *   },
 * });
 * 
 * createWebhook.mutate({
 *   url: "https://example.com/webhook",
 *   events: ["product.created"],
 *   enabled: true,
 * });
 * ```
 */
export function useCreateWebhook(options?: {
  onSuccess?: (data: Webhook) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createWebhook,
    onSuccess: (data) => {
      // Invalidate webhooks list queries to refetch
      queryClient.invalidateQueries({ queryKey: webhookKeys.lists() });
      // Optionally add the new webhook to cache
      queryClient.setQueryData(webhookKeys.detail(data.id), data);
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
 * Hook for updating a webhook.
 * 
 * @param id - Webhook ID to update
 * 
 * @example
 * ```tsx
 * const updateWebhook = useUpdateWebhook(1, {
 *   onSuccess: (webhook) => {
 *     console.log('Webhook updated:', webhook);
 *   },
 * });
 * 
 * updateWebhook.mutate({
 *   enabled: false,
 * });
 * ```
 */
export function useUpdateWebhook(
  id: number,
  options?: {
    onSuccess?: (data: Webhook) => void;
    onError?: (error: Error) => void;
  }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: WebhookUpdate) => updateWebhook(id, data),
    onSuccess: (data) => {
      // Update the webhook in cache
      queryClient.setQueryData(webhookKeys.detail(id), data);
      // Invalidate webhooks list queries to refetch
      queryClient.invalidateQueries({ queryKey: webhookKeys.lists() });
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
 * Hook for deleting a webhook.
 * 
 * @example
 * ```tsx
 * const deleteWebhook = useDeleteWebhook({
 *   onSuccess: () => {
 *     console.log('Webhook deleted');
 *   },
 * });
 * 
 * deleteWebhook.mutate(1);
 * ```
 */
export function useDeleteWebhook(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteWebhook,
    onSuccess: (_, webhookId) => {
      // Remove webhook from cache
      queryClient.removeQueries({ queryKey: webhookKeys.detail(webhookId) });
      // Invalidate webhooks list queries to refetch
      queryClient.invalidateQueries({ queryKey: webhookKeys.lists() });
      options?.onSuccess?.();
    },
    onError: (error) => {
      options?.onError?.(
        error instanceof Error ? error : new Error(String(error))
      );
    },
  });
}

/**
 * Hook for testing a webhook.
 * 
 * @example
 * ```tsx
 * const testWebhook = useTestWebhook({
 *   onSuccess: (response) => {
 *     console.log('Test result:', response);
 *   },
 * });
 * 
 * testWebhook.mutate(1);
 * ```
 */
export function useTestWebhook(options?: {
  onSuccess?: (data: WebhookTestResponse) => void;
  onError?: (error: Error) => void;
}) {
  return useMutation({
    mutationFn: testWebhook,
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
 * Hook for fetching webhook delivery history.
 * 
 * @param id - Webhook ID
 * @param params - Query parameters for pagination
 * 
 * @example
 * ```tsx
 * const { data, isLoading } = useWebhookDeliveries(1, {
 *   page: 1,
 *   page_size: 50,
 * });
 * ```
 */
export function useWebhookDeliveries(
  id: number | null,
  params: WebhookDeliveriesParams = {},
  options?: {
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: webhookKeys.deliveriesList(id!, params),
    queryFn: () => fetchWebhookDeliveries(id!, params),
    enabled: options?.enabled !== false && id !== null,
  });
}

