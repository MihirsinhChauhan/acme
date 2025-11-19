import { useCallback, useState } from "react";
import { Upload, FileSpreadsheet, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";

interface FileUploadProps {
  onUploadComplete?: (jobId: string) => void;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const { toast } = useToast();

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
      setSelectedFile(files[0]);
    }
  }, []);

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setProgress(0);

    // Simulate upload progress
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) {
          clearInterval(interval);
          return prev;
        }
        return prev + 10;
      });
    }, 200);

    try {
      // TODO: Implement actual API call
      await new Promise((resolve) => setTimeout(resolve, 2000));
      setProgress(100);
      
      toast({
        title: "Upload successful",
        description: `${selectedFile.name} has been uploaded and is being processed.`,
      });

      setTimeout(() => {
        setIsUploading(false);
        setSelectedFile(null);
        setProgress(0);
        onUploadComplete?.("sample-job-id");
      }, 500);
    } catch (error) {
      toast({
        title: "Upload failed",
        description: "There was an error uploading your file. Please try again.",
        variant: "destructive",
      });
      setIsUploading(false);
      setProgress(0);
    }
  };

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
                  disabled={isUploading}
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
              disabled={isUploading}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {isUploading && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Uploading...</span>
              <span className="font-medium text-foreground">{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>
        )}

        <Button
          onClick={handleUpload}
          disabled={!selectedFile || isUploading}
          className="w-full"
          size="lg"
        >
          {isUploading ? "Uploading..." : "Upload and Import"}
        </Button>
      </div>
    </Card>
  );
}
