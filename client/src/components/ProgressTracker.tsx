import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";

interface ProgressTrackerProps {
  jobId: string | null;
  status: "idle" | "importing" | "completed" | "failed";
  processedRows: number;
  totalRows: number;
  stage?: string;
}

export default function ProgressTracker({
  jobId,
  status,
  processedRows,
  totalRows,
  stage,
}: ProgressTrackerProps) {
  if (!jobId || status === "idle") {
    return null;
  }

  const progress = totalRows > 0 ? (processedRows / totalRows) * 100 : 0;

  const getStatusIcon = () => {
    switch (status) {
      case "importing":
        return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
      case "completed":
        return <CheckCircle2 className="h-5 w-5 text-success" />;
      case "failed":
        return <AlertCircle className="h-5 w-5 text-destructive" />;
      default:
        return null;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case "importing":
        return "Importing products...";
      case "completed":
        return "Import completed successfully";
      case "failed":
        return "Import failed";
      default:
        return "";
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
          <div className="text-right">
            <p className="text-sm font-medium text-foreground">
              {processedRows.toLocaleString()} / {totalRows.toLocaleString()}
            </p>
            <p className="text-xs text-muted-foreground">{progress.toFixed(1)}%</p>
          </div>
        </div>

        {status === "importing" && (
          <Progress value={progress} className="h-2" />
        )}

        <div className="rounded-md bg-muted/50 p-3">
          <p className="text-xs text-muted-foreground">
            Job ID: <span className="font-mono">{jobId}</span>
          </p>
        </div>
      </div>
    </Card>
  );
}
