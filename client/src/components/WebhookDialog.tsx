/**
 * Webhook create/edit dialog component.
 * 
 * Provides a form dialog for creating new webhooks or editing existing ones.
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
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import type { Webhook, WebhookCreate, WebhookUpdate } from "@/types/api";

/**
 * Available webhook event types.
 */
export const WEBHOOK_EVENTS = [
  { value: "product.created", label: "Product Created" },
  { value: "product.updated", label: "Product Updated" },
  { value: "product.deleted", label: "Product Deleted" },
  { value: "product.bulk_deleted", label: "Product Bulk Deleted" },
  { value: "import.completed", label: "Import Completed" },
  { value: "import.failed", label: "Import Failed" },
] as const;

/**
 * Validation schema for webhook form.
 */
const webhookFormSchema = z.object({
  url: z
    .string()
    .min(1, "URL is required")
    .url("Must be a valid URL")
    .refine(
      (url) => url.startsWith("http://") || url.startsWith("https://"),
      "URL must start with http:// or https://"
    ),
  events: z
    .array(z.string())
    .min(1, "At least one event type must be selected"),
  enabled: z.boolean().default(true),
});

type WebhookFormValues = z.infer<typeof webhookFormSchema>;

/**
 * Props for WebhookDialog component.
 */
interface WebhookDialogProps {
  /**
   * Whether the dialog is open.
   */
  open: boolean;
  
  /**
   * Callback when dialog should close.
   */
  onOpenChange: (open: boolean) => void;
  
  /**
   * Webhook to edit (if editing). If null, creates a new webhook.
   */
  webhook: Webhook | null;
  
  /**
   * Callback when webhook is successfully created or updated.
   */
  onSuccess?: () => void;
  
  /**
   * Callback when an error occurs.
   */
  onError?: (error: Error) => void;
  
  /**
   * Mutation function for creating/updating webhook.
   * Should be from useCreateWebhook or useUpdateWebhook hook.
   */
  mutation: {
    mutate: (
      data: WebhookCreate | WebhookUpdate,
      options?: {
        onSuccess?: () => void;
        onError?: (error: unknown) => void;
      }
    ) => void;
    isPending: boolean;
  };
}

/**
 * Webhook create/edit dialog component.
 */
export function WebhookDialog({
  open,
  onOpenChange,
  webhook,
  onSuccess,
  onError,
  mutation,
}: WebhookDialogProps) {
  const isEditing = webhook !== null;

  const form = useForm<WebhookFormValues>({
    resolver: zodResolver(webhookFormSchema),
    defaultValues: {
      url: "",
      events: [],
      enabled: true,
    },
  });

  // Reset form when webhook changes or dialog opens/closes
  useEffect(() => {
    if (open) {
      if (webhook) {
        // Editing: populate form with webhook data
        form.reset({
          url: webhook.url,
          events: webhook.events,
          enabled: webhook.enabled,
        });
      } else {
        // Creating: reset to defaults
        form.reset({
          url: "",
          events: [],
          enabled: true,
        });
      }
    }
  }, [open, webhook, form]);

  const onSubmit = (values: WebhookFormValues) => {
    const submitData: WebhookCreate | WebhookUpdate = {
      url: values.url,
      events: values.events,
      enabled: values.enabled,
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

  const watchedEvents = form.watch("events");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit Webhook" : "Create Webhook"}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the webhook configuration below."
              : "Configure a new webhook endpoint to receive event notifications."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="url"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Webhook URL</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="https://api.example.com/webhook"
                      {...field}
                      disabled={mutation.isPending}
                    />
                  </FormControl>
                  <FormDescription>
                    The URL where webhook events will be sent (must start with http:// or https://)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="events"
              render={() => (
                <FormItem>
                  <div className="mb-4">
                    <FormLabel className="text-base">Event Types</FormLabel>
                    <FormDescription>
                      Select one or more event types to subscribe to
                    </FormDescription>
                  </div>
                  <div className="space-y-3">
                    {WEBHOOK_EVENTS.map((event) => (
                      <FormField
                        key={event.value}
                        control={form.control}
                        name="events"
                        render={({ field }) => {
                          return (
                            <FormItem
                              key={event.value}
                              className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4"
                            >
                              <FormControl>
                                <Checkbox
                                  checked={field.value?.includes(event.value)}
                                  onCheckedChange={(checked) => {
                                    return checked
                                      ? field.onChange([...field.value, event.value])
                                      : field.onChange(
                                          field.value?.filter(
                                            (value) => value !== event.value
                                          )
                                        );
                                  }}
                                  disabled={mutation.isPending}
                                />
                              </FormControl>
                              <FormLabel className="font-normal cursor-pointer flex-1">
                                <div className="flex items-center justify-between">
                                  <span>{event.label}</span>
                                  <Badge variant="outline" className="font-mono text-xs">
                                    {event.value}
                                  </Badge>
                                </div>
                              </FormLabel>
                            </FormItem>
                          );
                        }}
                      />
                    ))}
                  </div>
                  {watchedEvents.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {watchedEvents.map((event) => (
                        <Badge key={event} variant="secondary" className="font-mono text-xs">
                          {event}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="enabled"
              render={({ field }) => (
                <FormItem className="flex flex-row items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel className="text-base">Enabled</FormLabel>
                    <FormDescription>
                      Whether the webhook is active and will receive events
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
                    ? "Update Webhook"
                    : "Create Webhook"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

