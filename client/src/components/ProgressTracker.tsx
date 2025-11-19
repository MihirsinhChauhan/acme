import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { useProgress } from "@/hooks/useProgress";
import { ImportJobStatus } from "@/types/api";

interface ProgressTrackerProps {
  jobId: string | null;
}

export default function ProgressTracker({ jobId }: ProgressTrackerProps) {
  const {
    progress,
    connectionState,
    isComplete,
    isFailed,
    error,
  } = useProgress(jobId, {
    reconnect: {
      enabled: true,
      maxAttempts: 5,
      delay: 1000,
    },
  });

  if (!jobId || connectionState === "idle") {
    return null;
  }

  // Map ImportJobStatus to display status
  const getDisplayStatus = (): "idle" | "importing" | "completed" | "failed" => {
    if (!progress) return "idle";
    
    switch (progress.status) {
      case ImportJobStatus.DONE:
        return "completed";
      case ImportJobStatus.FAILED:
        return "failed";
      case ImportJobStatus.QUEUED:
      case ImportJobStatus.UPLOADING:
      case ImportJobStatus.PARSING:
      case ImportJobStatus.IMPORTING:
        return "importing";
      default:
        return "idle";
    }
  };

  const displayStatus = getDisplayStatus();
  const processedRows = progress?.processed_rows ?? 0;
  const totalRows = progress?.total_rows ?? 0;
  const progressPercent = progress?.progress_percent ?? (totalRows > 0 ? (processedRows / totalRows) * 100 : 0);
  const stage = progress?.stage;

  const getStatusIcon = () => {
    if (connectionState === "connecting") {
      return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />;
    }

    switch (displayStatus) {
      case "importing":
        return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
      case "completed":
        return <CheckCircle2 className="h-5 w-5 text-green-600" />;
      case "failed":
        return <AlertCircle className="h-5 w-5 text-destructive" />;
      default:
        return null;
    }
  };

  const getStatusText = () => {
    if (connectionState === "connecting") {
      return "Connecting...";
    }

    if (connectionState === "error") {
      return error || "Connection error";
    }

    if (!progress) {
      return "Waiting for progress...";
    }

    switch (progress.status) {
      case ImportJobStatus.QUEUED:
        return "Queued for processing...";
      case ImportJobStatus.UPLOADING:
        return "Uploading file...";
      case ImportJobStatus.PARSING:
        return "Parsing CSV file...";
      case ImportJobStatus.IMPORTING:
        return "Importing products...";
      case ImportJobStatus.DONE:
        return "Import completed successfully";
      case ImportJobStatus.FAILED:
        return progress.error_message ? `Import failed: ${progress.error_message}` : "Import failed";
      default:
        return "Processing...";
    }
  };

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            {getStatusIcon()}
            <div>
              <p className="text-sm font-medium text-foreground">{getStatusText()}</p>
              {stage && (
                <p className="text-xs text-muted-foreground">Stage: {stage}</p>
              )}
            </div>
          </div>
          {totalRows > 0 && (
            <div className="text-right">
              <p className="text-sm font-medium text-foreground">
                {processedRows.toLocaleString()} / {totalRows.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground">{progressPercent.toFixed(1)}%</p>
            </div>
          )}
        </div>

        {displayStatus === "importing" && (
          <Progress value={progressPercent} className="h-2" />
        )}

        {error && connectionState === "error" && (
          <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3">
            <p className="text-xs text-destructive">{error}</p>
          </div>
        )}

        <div className="rounded-md bg-muted/50 p-3">
          <p className="text-xs text-muted-foreground">
            Job ID: <span className="font-mono">{jobId}</span>
          </p>
          {connectionState !== "idle" && (
            <p className="text-xs text-muted-foreground mt-1">
              Connection: <span className="capitalize">{connectionState}</span>
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}
