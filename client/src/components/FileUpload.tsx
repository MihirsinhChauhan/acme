import { useCallback, useState } from "react";
import { Upload, FileSpreadsheet, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { useUpload } from "@/hooks/useUpload";
import { ApiError } from "@/lib/api/client";

interface FileUploadProps {
  onUploadComplete?: (jobId: string) => void;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const { toast } = useToast();

  const upload = useUpload({
    onSuccess: (response) => {
      toast({
        title: "Upload successful",
        description: `${selectedFile?.name} has been uploaded and is being processed.`,
      });
      setSelectedFile(null);
      onUploadComplete?.(response.job_id);
    },
    onError: (error) => {
      let errorMessage = "There was an error uploading your file. Please try again.";
      
      if (error instanceof ApiError) {
        // Handle API errors with detailed messages
        if (typeof error.data === "object" && error.data !== null) {
          const data = error.data as { detail?: string | { message?: string; errors?: unknown } };
          if (typeof data.detail === "string") {
            errorMessage = data.detail;
          } else if (data.detail && typeof data.detail === "object" && "message" in data.detail) {
            errorMessage = String(data.detail.message) || errorMessage;
          }
        } else if (error.message) {
          errorMessage = error.message;
        }
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      toast({
        title: "Upload failed",
        description: errorMessage,
        variant: "destructive",
      });
    },
  });

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragging(true);
    } else if (e.type === "dragleave") {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      const file = files[0];
      if (file.type === "text/csv" || file.name.endsWith(".csv")) {
        setSelectedFile(file);
      } else {
        toast({
          title: "Invalid file type",
          description: "Please upload a CSV file",
          variant: "destructive",
        });
      }
    }
  }, [toast]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      const file = files[0];
      if (file.type === "text/csv" || file.name.endsWith(".csv")) {
        setSelectedFile(file);
      } else {
        toast({
          title: "Invalid file type",
          description: "Please upload a CSV file",
          variant: "destructive",
        });
      }
    }
  }, [toast]);

  const handleUpload = useCallback(() => {
    if (!selectedFile) return;
    upload.mutate(selectedFile);
  }, [selectedFile, upload]);

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors ${
            isDragging
              ? "border-primary bg-primary/5"
              : "border-border bg-muted/30 hover:bg-muted/50"
          }`}
        >
          <Upload className={`mb-4 h-12 w-12 ${isDragging ? "text-primary" : "text-muted-foreground"}`} />
          <div className="text-center">
            <p className="text-sm font-medium text-foreground">
              Drop your CSV file here, or{" "}
              <label className="cursor-pointer text-primary hover:underline">
                browse
                <input
                  type="file"
                  className="sr-only"
                  accept=".csv"
                  onChange={handleFileSelect}
                  disabled={upload.isPending}
                />
              </label>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              CSV files up to 512MB (max 500,000 products)
            </p>
          </div>
        </div>

        {selectedFile && (
          <div className="flex items-center justify-between rounded-lg border border-border bg-card p-4">
            <div className="flex items-center space-x-3">
              <FileSpreadsheet className="h-8 w-8 text-primary" />
              <div>
                <p className="text-sm font-medium text-foreground">{selectedFile.name}</p>
                <p className="text-xs text-muted-foreground">
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedFile(null)}
              disabled={upload.isPending}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        <Button
          onClick={handleUpload}
          disabled={!selectedFile || upload.isPending}
          className="w-full"
          size="lg"
        >
          {upload.isPending ? "Uploading..." : "Upload and Import"}
        </Button>
      </div>
    </Card>
  );
}
