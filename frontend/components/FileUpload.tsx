'use client';

import { useCallback, useState, useRef } from 'react';
import { Upload, FileText, Loader2, Sparkles, X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadProps {
  onProcess: (file: File) => Promise<void>;
  isLoading: boolean;
}

export function FileUpload({ onProcess, isLoading }: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback((f: File) => {
    if (!f.name.match(/\.(pdf|png|jpg|jpeg|tiff|bmp)$/i)) {
      alert('Please upload a PDF or image file.');
      return;
    }
    setFile(f);
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  const handleProcess = async () => {
    if (!file) return;
    await onProcess(file);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="glow-card p-6 flex flex-col gap-5">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <div className="w-7 h-7 rounded-lg bg-indigo-500/20 flex items-center justify-center">
            <Upload className="w-4 h-4 text-indigo-400" />
          </div>
          <h2 className="text-sm font-semibold text-slate-200 tracking-wide uppercase">Upload Document</h2>
        </div>
        <p className="text-xs text-slate-500 ml-9">Form 16 PDF or image file</p>
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => !file && inputRef.current?.click()}
        className={cn(
          'relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 cursor-pointer transition-all duration-200',
          isDragging
            ? 'border-indigo-500 bg-indigo-500/10 scale-[1.01]'
            : file
            ? 'border-slate-700 bg-slate-800/30 cursor-default'
            : 'border-slate-700 bg-slate-900/40 hover:border-slate-500 hover:bg-slate-800/30',
        )}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />

        {file ? (
          <>
            {/* File preview */}
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
              <FileText className="w-6 h-6 text-emerald-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-200 truncate max-w-[200px]">{file.name}</p>
              <p className="text-xs text-slate-500 mt-0.5">{formatSize(file.size)}</p>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setFile(null); }}
              className="absolute top-3 right-3 w-6 h-6 rounded-full bg-slate-700 hover:bg-slate-600 flex items-center justify-center transition-colors"
            >
              <X className="w-3 h-3 text-slate-300" />
            </button>
          </>
        ) : (
          <>
            <div className={cn(
              'w-12 h-12 rounded-xl flex items-center justify-center transition-all',
              isDragging ? 'bg-indigo-500/30' : 'bg-slate-800',
            )}>
              <Upload className={cn('w-6 h-6 transition-colors', isDragging ? 'text-indigo-400' : 'text-slate-500')} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-slate-300">
                {isDragging ? 'Drop it here' : 'Drag & drop your Form 16'}
              </p>
              <p className="text-xs text-slate-500 mt-1">or click to browse · PDF, PNG, JPG, TIFF</p>
            </div>
          </>
        )}
      </div>

      {/* Process Button */}
      <button
        onClick={handleProcess}
        disabled={Boolean(!file || isLoading)}
        className={cn(
          'relative w-full h-11 rounded-xl font-semibold text-sm transition-all duration-200 flex items-center justify-center gap-2 overflow-hidden',
          !file || isLoading
            ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
            : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 hover:-translate-y-0.5',
        )}
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Processing…</span>
          </>
        ) : (
          <>
            <Sparkles className="w-4 h-4" />
            <span>Process Document</span>
          </>
        )}
      </button>
    </div>
  );
}
