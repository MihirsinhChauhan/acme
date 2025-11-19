/**
 * Product create/edit dialog component.
 * 
 * Provides a form dialog for creating new products or editing existing ones.
 * Uses react-hook-form with zod validation.
 */

import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { Product, ProductCreate, ProductUpdate } from "@/types/api";

/**
 * Validation schema for product form.
 */
const productFormSchema = z.object({
  sku: z.string().min(1, "SKU is required").max(255, "SKU must be 255 characters or less"),
  name: z.string().min(1, "Name is required").max(255, "Name must be 255 characters or less"),
  description: z.string().max(1000, "Description must be 1000 characters or less").optional().nullable(),
  active: z.boolean().default(true),
});

type ProductFormValues = z.infer<typeof productFormSchema>;

/**
 * Props for ProductDialog component.
 */
interface ProductDialogProps {
  /**
   * Whether the dialog is open.
   */
  open: boolean;
  
  /**
   * Callback when dialog should close.
   */
  onOpenChange: (open: boolean) => void;
  
  /**
   * Product to edit (if editing). If null, creates a new product.
   */
  product: Product | null;
  
  /**
   * Callback when product is successfully created or updated.
   */
  onSuccess?: () => void;
  
  /**
   * Callback when an error occurs.
   */
  onError?: (error: Error) => void;
  
  /**
   * Mutation function for creating/updating product.
   * Should be from useCreateProduct or useUpdateProduct hook.
   */
  mutation: {
    mutate: (
      data: ProductCreate | ProductUpdate,
      options?: {
        onSuccess?: () => void;
        onError?: (error: unknown) => void;
      }
    ) => void;
    isPending: boolean;
  };
}

/**
 * Product create/edit dialog component.
 */
export function ProductDialog({
  open,
  onOpenChange,
  product,
  onSuccess,
  onError,
  mutation,
}: ProductDialogProps) {
  const isEditing = product !== null;

  const form = useForm<ProductFormValues>({
    resolver: zodResolver(productFormSchema),
    defaultValues: {
      sku: "",
      name: "",
      description: "",
      active: true,
    },
  });

  // Reset form when product changes or dialog opens/closes
  useEffect(() => {
    if (open) {
      if (product) {
        // Editing: populate form with product data
        form.reset({
          sku: product.sku,
          name: product.name,
          description: product.description ?? "",
          active: product.active,
        });
      } else {
        // Creating: reset to defaults
        form.reset({
          sku: "",
          name: "",
          description: "",
          active: true,
        });
      }
    }
  }, [open, product, form]);

  const onSubmit = (values: ProductFormValues) => {
    const submitData: ProductCreate | ProductUpdate = {
      sku: values.sku,
      name: values.name,
      description: values.description || null,
      active: values.active,
    };

    mutation.mutate(submitData, {
      onSuccess: () => {
        form.reset();
        onOpenChange(false);
        onSuccess?.();
      },
      onError: (error: unknown) => {
        onError?.(error instanceof Error ? error : new Error(String(error)));
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit Product" : "Create Product"}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the product information below."
              : "Fill in the details to create a new product."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="sku"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>SKU</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="PROD-001"
                      {...field}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  <FormDescription>
                    Unique stock keeping unit identifier (1-255 characters)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Name</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Product Name"
                      {...field}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  <FormDescription>
                    Display name for the product (1-255 characters)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Product description (optional)"
                      {...field}
                      value={field.value ?? ""}
                      disabled={mutation.isPending}
                      rows={4}
                    />
                  </FormControl>
                  <FormDescription>
                    Optional marketing copy or product details
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="active"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base">Active</FormLabel>
                    <FormDescription>
                      Whether the product is sellable and visible
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending
                  ? isEditing
                    ? "Updating..."
                    : "Creating..."
                  : isEditing
                    ? "Update Product"
                    : "Create Product"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

