/**
 * React hooks for product CRUD operations.
 * 
 * Provides React Query hooks for fetching, creating, updating, and deleting products.
 * All hooks use the API client and are properly typed.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, put, del } from "@/lib/api/client";
import type {
  Product,
  ProductCreate,
  ProductUpdate,
  ProductListResponse,
  BulkDeleteResponse,
} from "@/types/api";

/**
 * Query parameters for listing products.
 */
export interface ProductListParams {
  sku?: string;
  name?: string;
  description?: string;
  active?: boolean;
  page?: number;
  page_size?: number;
}

/**
 * Fetch products list with filtering and pagination.
 */
async function fetchProducts(params: ProductListParams = {}): Promise<ProductListResponse> {
  const queryParams = new URLSearchParams();
  
  if (params.sku) queryParams.append("sku", params.sku);
  if (params.name) queryParams.append("name", params.name);
  if (params.description) queryParams.append("description", params.description);
  if (params.active !== undefined) queryParams.append("active", String(params.active));
  if (params.page) queryParams.append("page", String(params.page));
  if (params.page_size) queryParams.append("page_size", String(params.page_size));

  const queryString = queryParams.toString();
  const endpoint = queryString ? `products?${queryString}` : "products";
  
  return get<ProductListResponse>(endpoint);
}

/**
 * Fetch a single product by ID.
 */
async function fetchProduct(id: number): Promise<Product> {
  return get<Product>(`products/${id}`);
}

/**
 * Create a new product.
 */
async function createProduct(data: ProductCreate): Promise<Product> {
  return post<Product>("products", data);
}

/**
 * Update a product by ID.
 */
async function updateProduct(id: number, data: ProductUpdate): Promise<Product> {
  return put<Product>(`products/${id}`, data);
}

/**
 * Delete a product by ID.
 */
async function deleteProduct(id: number): Promise<void> {
  return del<void>(`products/${id}`);
}

/**
 * Initiate bulk delete of all products.
 */
async function bulkDeleteProducts(): Promise<BulkDeleteResponse> {
  return post<BulkDeleteResponse>("products/bulk-delete");
}

/**
 * Query key factory for products.
 */
export const productKeys = {
  all: ["products"] as const,
  lists: () => [...productKeys.all, "list"] as const,
  list: (params: ProductListParams) => [...productKeys.lists(), params] as const,
  details: () => [...productKeys.all, "detail"] as const,
  detail: (id: number) => [...productKeys.details(), id] as const,
};

/**
 * Hook for fetching products list with filtering and pagination.
 * 
 * @param params - Query parameters for filtering and pagination
 * @param options - React Query options
 * 
 * @example
 * ```tsx
 * const { data, isLoading, error } = useProducts({
 *   page: 1,
 *   page_size: 20,
 *   active: true,
 * });
 * ```
 */
export function useProducts(
  params: ProductListParams = {},
  options?: {
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => fetchProducts(params),
    enabled: options?.enabled !== false,
  });
}

/**
 * Hook for fetching a single product by ID.
 * 
 * @param id - Product ID
 * @param options - React Query options
 * 
 * @example
 * ```tsx
 * const { data, isLoading } = useProduct(1);
 * ```
 */
export function useProduct(
  id: number | null,
  options?: {
    enabled?: boolean;
  }
) {
  return useQuery({
    queryKey: productKeys.detail(id!),
    queryFn: () => fetchProduct(id!),
    enabled: options?.enabled !== false && id !== null,
  });
}

/**
 * Hook for creating a new product.
 * 
 * @example
 * ```tsx
 * const createProduct = useCreateProduct({
 *   onSuccess: (product) => {
 *     console.log('Product created:', product);
 *   },
 * });
 * 
 * createProduct.mutate({
 *   sku: "PROD-001",
 *   name: "Example Product",
 *   active: true,
 * });
 * ```
 */
export function useCreateProduct(options?: {
  onSuccess?: (data: Product) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createProduct,
    onSuccess: (data) => {
      // Invalidate products list queries to refetch
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
      // Optionally add the new product to cache
      queryClient.setQueryData(productKeys.detail(data.id), data);
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
 * Hook for updating a product.
 * 
 * @param id - Product ID to update
 * 
 * @example
 * ```tsx
 * const updateProduct = useUpdateProduct(1, {
 *   onSuccess: (product) => {
 *     console.log('Product updated:', product);
 *   },
 * });
 * 
 * updateProduct.mutate({
 *   name: "Updated Name",
 *   active: false,
 * });
 * ```
 */
export function useUpdateProduct(
  id: number,
  options?: {
    onSuccess?: (data: Product) => void;
    onError?: (error: Error) => void;
  }
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProductUpdate) => updateProduct(id, data),
    onSuccess: (data) => {
      // Update the product in cache
      queryClient.setQueryData(productKeys.detail(id), data);
      // Invalidate products list queries to refetch
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
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
 * Hook for deleting a product.
 * 
 * @example
 * ```tsx
 * const deleteProduct = useDeleteProduct({
 *   onSuccess: () => {
 *     console.log('Product deleted');
 *   },
 * });
 * 
 * deleteProduct.mutate(1);
 * ```
 */
export function useDeleteProduct(options?: {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteProduct,
    onSuccess: (_, productId) => {
      // Remove product from cache
      queryClient.removeQueries({ queryKey: productKeys.detail(productId) });
      // Invalidate products list queries to refetch
      queryClient.invalidateQueries({ queryKey: productKeys.lists() });
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
 * Hook for bulk deleting all products.
 * 
 * @example
 * ```tsx
 * const bulkDelete = useBulkDeleteProducts({
 *   onSuccess: (response) => {
 *     console.log('Bulk delete initiated:', response.job_id);
 *   },
 * });
 * 
 * bulkDelete.mutate();
 * ```
 */
export function useBulkDeleteProducts(options?: {
  onSuccess?: (data: BulkDeleteResponse) => void;
  onError?: (error: Error) => void;
}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: bulkDeleteProducts,
    onSuccess: (data) => {
      // Invalidate all product queries since all products will be deleted
      queryClient.invalidateQueries({ queryKey: productKeys.all });
      options?.onSuccess?.(data);
    },
    onError: (error) => {
      options?.onError?.(
        error instanceof Error ? error : new Error(String(error))
      );
    },
  });
}

