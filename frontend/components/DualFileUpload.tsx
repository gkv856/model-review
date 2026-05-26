"use client";

import { useCallback, useState } from "react";
import { Upload, FileSpreadsheet, X, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, formatFileSize } from "@/lib/utils";

const MAX_MB = 50;
const MAX_BYTES = MAX_MB * 1024 * 1024;

interface IDropzone {
  label: string;
  file: File | null;
  error: string | null;
  onFile: (file: File | null, error: string | null) => void;
}

// Input: label, current file, error, onFile callback
// Output: drag-and-drop zone — validates xlsx extension and 50MB limit
const Dropzone = (props: IDropzone) => {
  const { label, file, error, onFile } = props;
  const [dragging, setDragging] = useState(false);

  const validate = (f: File): string | null => {
    if (!f.name.toLowerCase().endsWith(".xlsx")) return "Only .xlsx files are accepted.";
    if (f.size > MAX_BYTES) return `File exceeds ${MAX_MB}MB limit.`;
    return null;
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const dropped = e.dataTransfer.files[0];
      if (!dropped) return;
      const err = validate(dropped);
      onFile(err ? null : dropped, err);
    },
    [onFile]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    const err = validate(selected);
    onFile(err ? null : selected, err);
    e.target.value = "";
  };

  return (
    <div className="flex flex-col gap-2 flex-1">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </p>

      <label
        className={cn(
          "relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 cursor-pointer transition-all min-h-[180px]",
          dragging
            ? "border-primary bg-primary/10"
            : file
              ? "border-border bg-muted/30"
              : "border-border hover:border-primary/40 hover:bg-muted/10"
        )}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input type="file" accept=".xlsx" className="sr-only" onChange={handleChange} />

        {file ? (
          <>
            <FileSpreadsheet className="w-8 h-8 text-primary" />
            <div className="text-center space-y-0.5">
              <p className="text-sm font-medium text-foreground truncate max-w-[200px]">
                {file.name}
              </p>
              <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
            </div>
            <button
              type="button"
              aria-label="Remove file"
              className="absolute top-2 right-2 p-1 rounded hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
              onClick={(e) => { e.preventDefault(); onFile(null, null); }}
            >
              <X className="w-4 h-4" />
            </button>
          </>
        ) : (
          <>
            <Upload className="w-8 h-8 text-muted-foreground" />
            <div className="text-center space-y-1">
              <p className="text-sm font-medium text-foreground">Drop file or click to browse</p>
              <p className="text-xs text-muted-foreground">.xlsx only — max {MAX_MB}MB</p>
            </div>
          </>
        )}
      </label>

      {error && (
        <div className="flex items-center gap-1.5 text-xs text-[var(--sev-critical-fg)]">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
};

interface IDualUpload {
  onSubmit: (modelFile: File, mapFile: File) => Promise<void>;
  isLoading: boolean;
}

// Input: onSubmit callback, isLoading flag
// Output: two side-by-side dropzones + Analyse button
const DualFileUpload = (props: IDualUpload) => {
  const { onSubmit, isLoading } = props;

  const [modelFile, setModelFile] = useState<File | null>(null);
  const [mapFile, setMapFile] = useState<File | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  const handleModelFile = (file: File | null, error: string | null) => {
    setModelFile(file);
    setModelError(error);
  };

  const handleMapFile = (file: File | null, error: string | null) => {
    setMapFile(file);
    setMapError(error);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!modelFile || !mapFile) return;
    await onSubmit(modelFile, mapFile);
  };

  const canSubmit = !!modelFile && !!mapFile && !isLoading;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div className="flex flex-col sm:flex-row gap-4">
        <Dropzone label="Model File (.xlsx)" file={modelFile} error={modelError} onFile={handleModelFile} />
        <Dropzone label="Map File (.xlsx)" file={mapFile} error={mapError} onFile={handleMapFile} />
      </div>

      {(!!modelFile !== !!mapFile) && (
        <p className="text-xs text-muted-foreground text-center">
          Both files are required before analysis can begin.
        </p>
      )}

      <Button
        type="submit"
        disabled={!canSubmit}
        size="lg"
        className="w-full h-12 text-sm font-semibold tracking-wide"
      >
        {isLoading ? "Uploading..." : "Analyse Model"}
      </Button>
    </form>
  );
};

export default DualFileUpload;
