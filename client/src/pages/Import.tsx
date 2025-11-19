import { useState } from "react";
import FileUpload from "@/components/FileUpload";
import ProgressTracker from "@/components/ProgressTracker";
import { Card } from "@/components/ui/card";
import { Info } from "lucide-react";

export default function Import() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<"idle" | "importing" | "completed" | "failed">("idle");
  const [processedRows, setProcessedRows] = useState(0);
  const [totalRows, setTotalRows] = useState(0);

  const handleUploadComplete = (newJobId: string) => {
    setJobId(newJobId);
    setStatus("importing");
    setTotalRows(100000);
    setProcessedRows(0);

    // Simulate progress
    const interval = setInterval(() => {
      setProcessedRows((prev) => {
        if (prev >= 100000) {
          clearInterval(interval);
          setStatus("completed");
          return 100000;
        }
        return prev + 5000;
      });
    }, 300);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Import Products</h1>
        <p className="mt-2 text-muted-foreground">
          Upload a CSV file to import products into the database
        </p>
      </div>

      <Card className="bg-primary/5 border-primary/20 p-4">
        <div className="flex items-start space-x-3">
          <Info className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">CSV Format Requirements</p>
            <ul className="text-xs text-muted-foreground space-y-1">
              <li>• Required columns: <span className="font-mono">sku</span>, <span className="font-mono">name</span></li>
              <li>• Optional columns: <span className="font-mono">description</span>, <span className="font-mono">active</span></li>
              <li>• SKU must be unique (case-insensitive)</li>
              <li>• Duplicate SKUs will be overwritten</li>
              <li>• Maximum file size: 512MB</li>
            </ul>
          </div>
        </div>
      </Card>

      <FileUpload onUploadComplete={handleUploadComplete} />

      <ProgressTracker
        jobId={jobId}
        status={status}
        processedRows={processedRows}
        totalRows={totalRows}
        stage={status === "importing" ? `batch_${Math.floor(processedRows / 10000)}` : undefined}
      />
    </div>
  );
}
