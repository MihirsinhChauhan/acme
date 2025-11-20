/**
 * Webhook delivery history dialog component.
 * 
 * Displays the delivery history for a webhook with pagination.
 */

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronLeft, ChevronRight, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { useWebhookDeliveries } from "@/hooks/useWebhooks";
import type { WebhookDeliveryResponse } from "@/types/api";

/**
 * Props for WebhookDeliveriesDialog component.
 */
interface WebhookDeliveriesDialogProps {
  /**
   * Whether the dialog is open.
   */
  open: boolean;
  
  /**
   * Callback when dialog should close.
   */
  onOpenChange: (open: boolean) => void;
  
  /**
   * Webhook ID to fetch deliveries for.
   */
  webhookId: number | null;
  
  /**
   * Webhook URL (for display).
   */
  webhookUrl?: string;
}

/**
 * Format a date string for display.
 */
function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  } catch {
    return dateString;
  }
}

/**
 * Get status icon for a delivery.
 */
function getStatusIcon(status: string) {
  switch (status) {
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-green-600" />;
    case "failed":
      return <XCircle className="h-4 w-4 text-destructive" />;
    case "pending":
      return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
    default:
      return null;
  }
}

/**
 * Get status badge for a delivery.
 */
function getStatusBadge(status: string) {
  switch (status) {
    case "success":
      return <Badge variant="default" className="bg-green-600">Success</Badge>;
    case "failed":
      return <Badge variant="destructive">Failed</Badge>;
    case "pending":
      return <Badge variant="outline">Pending</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

/**
 * Webhook delivery history dialog component.
 */
export function WebhookDeliveriesDialog({
  open,
  onOpenChange,
  webhookId,
  webhookUrl,
}: WebhookDeliveriesDialogProps) {
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const {
    data: deliveries,
    isLoading,
    error,
  } = useWebhookDeliveries(
    webhookId,
    { page, page_size: pageSize },
    { enabled: open && webhookId !== null }
  );

  const hasNextPage = deliveries && deliveries.length === pageSize;
  const hasPrevPage = page > 1;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Delivery History</DialogTitle>
          <DialogDescription>
            {webhookUrl && (
              <span className="font-mono text-xs break-all">{webhookUrl}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Card key={i} className="p-4">
                  <Skeleton className="h-4 w-full" />
                </Card>
              ))}
            </div>
          ) : error ? (
            <Card className="p-4">
              <p className="text-sm text-destructive">
                Error loading deliveries: {error instanceof Error ? error.message : "Unknown error"}
              </p>
            </Card>
          ) : !deliveries || deliveries.length === 0 ? (
            <Card className="p-4">
              <p className="text-sm text-muted-foreground text-center py-8">
                No delivery history found
              </p>
            </Card>
          ) : (
            <div className="rounded-md border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Event Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Response Code</TableHead>
                    <TableHead>Response Time</TableHead>
                    <TableHead>Attempted At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deliveries.map((delivery: WebhookDeliveryResponse) => (
                    <TableRow key={delivery.id}>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {delivery.event_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          {getStatusIcon(delivery.status)}
                          {getStatusBadge(delivery.status)}
                        </div>
                      </TableCell>
                      <TableCell>
                        {delivery.response_code !== null &&
                        delivery.response_code !== undefined ? (
                          <Badge
                            variant={
                              delivery.response_code >= 200 &&
                              delivery.response_code < 300
                                ? "default"
                                : "destructive"
                            }
                          >
                            {delivery.response_code}
                          </Badge>
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {delivery.response_time_ms !== null &&
                        delivery.response_time_ms !== undefined ? (
                          <div className="flex items-center space-x-1">
                            <Clock className="h-3 w-3 text-muted-foreground" />
                            <span className="text-sm">
                              {delivery.response_time_ms} ms
                            </span>
                          </div>
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground">
                            {formatDate(delivery.attempted_at)}
                          </span>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-4 border-t">
          <p className="text-sm text-muted-foreground">
            {isLoading
              ? "Loading..."
              : deliveries
                ? `Showing ${deliveries.length} delivery${deliveries.length !== 1 ? "s" : ""}`
                : "No deliveries"}
          </p>
          <div className="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={!hasPrevPage || isLoading}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNextPage || isLoading}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

