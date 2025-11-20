/**
 * Webhook test results dialog component.
 * 
 * Displays the results of a webhook test, including response code, response time,
 * and response body.
 */

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
import { CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";
import type { WebhookTestResponse } from "@/types/api";

/**
 * Props for WebhookTestDialog component.
 */
interface WebhookTestDialogProps {
  /**
   * Whether the dialog is open.
   */
  open: boolean;
  
  /**
   * Callback when dialog should close.
   */
  onOpenChange: (open: boolean) => void;
  
  /**
   * Test response data to display.
   */
  testResponse: WebhookTestResponse | null;
  
  /**
   * Whether the test is currently running.
   */
  isTesting: boolean;
  
  /**
   * Webhook URL being tested (for display).
   */
  webhookUrl?: string;
}

/**
 * Webhook test results dialog component.
 */
export function WebhookTestDialog({
  open,
  onOpenChange,
  testResponse,
  isTesting,
  webhookUrl,
}: WebhookTestDialogProps) {
  const getStatusIcon = () => {
    if (isTesting) {
      return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
    }
    
    if (!testResponse) {
      return null;
    }
    
    if (testResponse.success) {
      return <CheckCircle2 className="h-5 w-5 text-green-600" />;
    }
    
    return <XCircle className="h-5 w-5 text-destructive" />;
  };

  const getStatusText = () => {
    if (isTesting) {
      return "Testing webhook...";
    }
    
    if (!testResponse) {
      return "No test results";
    }
    
    if (testResponse.success) {
      return "Test successful";
    }
    
    return "Test failed";
  };

  const getStatusBadge = () => {
    if (isTesting) {
      return <Badge variant="outline">Testing...</Badge>;
    }
    
    if (!testResponse) {
      return null;
    }
    
    if (testResponse.success) {
      return <Badge variant="default" className="bg-green-600">Success</Badge>;
    }
    
    return <Badge variant="destructive">Failed</Badge>;
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Webhook Test Results</DialogTitle>
          <DialogDescription>
            {webhookUrl && (
              <span className="font-mono text-xs break-all">{webhookUrl}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Status Section */}
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                {getStatusIcon()}
                <div>
                  <p className="text-sm font-medium">{getStatusText()}</p>
                  {testResponse?.error && (
                    <p className="text-xs text-destructive mt-1">{testResponse.error}</p>
                  )}
                </div>
              </div>
              {getStatusBadge()}
            </div>
          </Card>

          {/* Response Details */}
          {testResponse && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                {/* Response Code */}
                <Card className="p-4">
                  <div className="flex items-center space-x-2 mb-2">
                    <span className="text-xs font-medium text-muted-foreground">
                      Response Code
                    </span>
                  </div>
                  {testResponse.response_code !== null && testResponse.response_code !== undefined ? (
                    <div className="flex items-center space-x-2">
                      <Badge
                        variant={
                          testResponse.response_code >= 200 && testResponse.response_code < 300
                            ? "default"
                            : "destructive"
                        }
                      >
                        {testResponse.response_code}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {testResponse.response_code >= 200 && testResponse.response_code < 300
                          ? "OK"
                          : "Error"}
                      </span>
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">—</span>
                  )}
                </Card>

                {/* Response Time */}
                <Card className="p-4">
                  <div className="flex items-center space-x-2 mb-2">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    <span className="text-xs font-medium text-muted-foreground">
                      Response Time
                    </span>
                  </div>
                  {testResponse.response_time_ms !== null &&
                  testResponse.response_time_ms !== undefined ? (
                    <p className="text-sm font-medium">
                      {testResponse.response_time_ms} ms
                    </p>
                  ) : (
                    <span className="text-sm text-muted-foreground">—</span>
                  )}
                </Card>
              </div>

              {/* Response Body */}
              {testResponse.response_body && (
                <Card className="p-4">
                  <div className="mb-2">
                    <span className="text-xs font-medium text-muted-foreground">
                      Response Body
                    </span>
                  </div>
                  <div className="rounded-md bg-muted p-3 max-h-48 overflow-auto">
                    <pre className="text-xs font-mono whitespace-pre-wrap break-words">
                      {testResponse.response_body}
                    </pre>
                  </div>
                </Card>
              )}

              {/* Error Message */}
              {testResponse.error && (
                <Card className="p-4 border-destructive/20 bg-destructive/5">
                  <div className="mb-2">
                    <span className="text-xs font-medium text-destructive">Error</span>
                  </div>
                  <p className="text-sm text-destructive">{testResponse.error}</p>
                </Card>
              )}
            </div>
          )}

          {/* Loading State */}
          {isTesting && (
            <Card className="p-4">
              <div className="flex items-center space-x-3">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <p className="text-sm text-muted-foreground">
                  Sending test request to webhook endpoint...
                </p>
              </div>
            </Card>
          )}
        </div>

        <DialogFooter>
          <Button onClick={() => onOpenChange(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

