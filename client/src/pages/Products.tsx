import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, Plus, Trash2, Edit, ChevronLeft, ChevronRight } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  useProducts,
  useCreateProduct,
  useUpdateProduct,
  useDeleteProduct,
  useBulkDeleteProducts,
} from "@/hooks/useProducts";
import { ProductDialog } from "@/components/ProductDialog";
import type { Product } from "@/types/api";
import { useProgress } from "@/hooks/useProgress";
import ProgressTracker from "@/components/ProgressTracker";

export default function Products() {
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [bulkDeleteJobId, setBulkDeleteJobId] = useState<string | null>(null);
  const { toast } = useToast();

  // Build query parameters
  const queryParams = useMemo(() => {
    const params: {
      page: number;
      page_size: number;
      sku?: string;
      name?: string;
      description?: string;
      active?: boolean;
    } = {
      page: currentPage,
      page_size: pageSize,
    };

    // Apply search filters
    if (searchTerm.trim()) {
      // For simplicity, search in name field (backend supports name, sku, description separately)
      // You could enhance this to search in specific fields
      params.name = searchTerm.trim();
    }

    // Apply status filter
    if (statusFilter === "active") {
      params.active = true;
    } else if (statusFilter === "inactive") {
      params.active = false;
    }

    return params;
  }, [searchTerm, statusFilter, currentPage, pageSize]);

  // Fetch products
  const {
    data: productsData,
    isLoading,
    error,
    refetch,
  } = useProducts(queryParams);

  // Mutations
  const createProduct = useCreateProduct({
    onSuccess: () => {
      toast({
        title: "Product created",
        description: "The product has been successfully created.",
      });
      setDialogOpen(false);
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to create product.",
        variant: "destructive",
      });
    },
  });

  const updateProduct = useUpdateProduct(editingProduct?.id ?? 0, {
    onSuccess: () => {
      toast({
        title: "Product updated",
        description: "The product has been successfully updated.",
      });
      setDialogOpen(false);
      setEditingProduct(null);
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to update product.",
        variant: "destructive",
      });
    },
  });

  const deleteProduct = useDeleteProduct({
    onSuccess: () => {
      toast({
        title: "Product deleted",
        description: "The product has been successfully deleted.",
      });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to delete product.",
        variant: "destructive",
      });
    },
  });

  const bulkDelete = useBulkDeleteProducts({
    onSuccess: (response) => {
      setBulkDeleteJobId(response.job_id);
      toast({
        title: "Bulk delete initiated",
        description: "All products are being deleted in the background.",
      });
    },
    onError: (error) => {
      toast({
        title: "Error",
        description: error.message || "Failed to initiate bulk delete.",
        variant: "destructive",
      });
    },
  });

  // Track bulk delete progress
  const { progress: bulkDeleteProgress, isComplete: bulkDeleteComplete } = useProgress(
    bulkDeleteJobId,
    {
      onProgress: (event) => {
        if (event.status === "done") {
          toast({
            title: "Bulk delete completed",
            description: "All products have been successfully deleted.",
          });
          setBulkDeleteJobId(null);
          refetch();
        } else if (event.status === "failed") {
          toast({
            title: "Bulk delete failed",
            description: event.error_message || "Failed to delete all products.",
            variant: "destructive",
          });
          setBulkDeleteJobId(null);
        }
      },
    }
  );

  // Handle dialog open for create
  const handleCreateClick = () => {
    setEditingProduct(null);
    setDialogOpen(true);
  };

  // Handle dialog open for edit
  const handleEditClick = (product: Product) => {
    setEditingProduct(product);
    setDialogOpen(true);
  };

  // Handle delete
  const handleDeleteClick = (product: Product) => {
    deleteProduct.mutate(product.id);
  };

  // Handle bulk delete
  const handleBulkDelete = () => {
    bulkDelete.mutate();
  };

  // Get current mutation (create or update)
  const currentMutation = editingProduct ? updateProduct : createProduct;

  // Calculate pagination
  const totalPages = productsData
    ? Math.ceil(productsData.total / productsData.page_size)
    : 0;
  const hasNextPage = currentPage < totalPages;
  const hasPrevPage = currentPage > 1;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Products</h1>
          <p className="mt-2 text-muted-foreground">
            Manage and view all your products
          </p>
        </div>
        <div className="flex space-x-3">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="destructive"
                disabled={bulkDelete.isPending || bulkDeleteJobId !== null}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete All
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action cannot be undone. This will permanently delete all products
                  from the database.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleBulkDelete}>
                  Delete All
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button onClick={handleCreateClick}>
            <Plus className="mr-2 h-4 w-4" />
            Add Product
          </Button>
        </div>
      </div>

      {/* Bulk delete progress tracker */}
      {bulkDeleteJobId && (
        <Card className="p-4">
          <ProgressTracker jobId={bulkDeleteJobId} />
        </Card>
      )}

      <Card className="p-6">
        <div className="mb-4 flex flex-col space-y-4 sm:flex-row sm:space-x-4 sm:space-y-0">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search by SKU, name, or description..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1); // Reset to first page on search
              }}
              className="pl-10"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-[180px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Products</SelectItem>
              <SelectItem value="active">Active Only</SelectItem>
              <SelectItem value="inactive">Inactive Only</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                // Loading skeleton
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Skeleton className="h-4 w-24" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-32" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-48" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-16" />
                    </TableCell>
                    <TableCell className="text-right">
                      <Skeleton className="h-8 w-16 ml-auto" />
                    </TableCell>
                  </TableRow>
                ))
              ) : error ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-destructive">
                    Error loading products: {error instanceof Error ? error.message : "Unknown error"}
                  </TableCell>
                </TableRow>
              ) : !productsData || productsData.items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                    No products found
                  </TableCell>
                </TableRow>
              ) : (
                productsData.items.map((product) => (
                  <TableRow key={product.id}>
                    <TableCell className="font-mono text-sm">{product.sku}</TableCell>
                    <TableCell className="font-medium">{product.name}</TableCell>
                    <TableCell className="max-w-md truncate text-muted-foreground">
                      {product.description || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={product.active ? "default" : "secondary"}>
                        {product.active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end space-x-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditClick(product)}
                          disabled={deleteProduct.isPending}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteClick(product)}
                          disabled={deleteProduct.isPending}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="mt-4 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {isLoading ? (
              "Loading..."
            ) : productsData ? (
              <>
                Showing {(productsData.page - 1) * productsData.page_size + 1} to{" "}
                {Math.min(productsData.page * productsData.page_size, productsData.total)} of{" "}
                {productsData.total} products
              </>
            ) : (
              "No products"
            )}
          </p>
          <div className="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={!hasPrevPage || isLoading}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={!hasNextPage || isLoading}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Product create/edit dialog */}
      <ProductDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        product={editingProduct}
        mutation={currentMutation}
        onSuccess={() => {
          refetch();
        }}
      />
    </div>
  );
}
