import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { fileService } from '@/services/api';
import { Upload, X, File, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileUploadProps {
  onSuccess?: () => void;
  className?: string;
}

interface UploadingFile {
  file: File;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  error?: string;
}

export function FileUpload({ onSuccess, className }: FileUploadProps) {
  const [uploadingFiles, setUploadingFiles] = useState<Record<string, UploadingFile>>({});
  const queryClient = useQueryClient();

  const uploadMutation = useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return fileService.uploadFile(formData);
    },
    onSuccess: (_, file) => {
      setUploadingFiles(prev => ({
        ...prev,
        [file.name]: { ...prev[file.name], status: 'completed', progress: 100 }
      }));
      queryClient.invalidateQueries({ queryKey: ['files'] });
      onSuccess?.();
    },
    onError: (err, file) => {
      setUploadingFiles(prev => ({
        ...prev,
        [file.name]: { ...prev[file.name], status: 'error', error: err.message }
      }));
    }
  });

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files) return;

    Array.from(files).forEach(file => {
      if (file.size > 50 * 1024 * 1024) {
        setUploadingFiles(prev => ({
          ...prev,
          [file.name]: { file, progress: 0, status: 'error', error: '文件超过 50MB 限制' }
        }));
        return;
      }

      setUploadingFiles(prev => ({
        ...prev,
        [file.name]: { file, progress: 10, status: 'uploading' }
      }));

      uploadMutation.mutate(file);
    });
  }, [uploadMutation]);

  return (
    <div className={cn("space-y-4", className)}>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFiles(e.dataTransfer.files);
        }}
        className="border-2 border-dashed border-muted-foreground/25 rounded-xl p-8 flex flex-col items-center justify-center text-center hover:border-primary/50 transition-colors cursor-pointer bg-muted/5 group"
        onClick={() => document.getElementById('file-input')?.click()}
      >
        <input
          id="file-input"
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
          accept=".pdf,.doc,.docx"
        />
        <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-4 group-hover:scale-110 transition-transform">
          <Upload size={24} />
        </div>
        <h3 className="text-lg font-medium">点击或拖拽上传文献</h3>
        <p className="text-sm text-muted-foreground mt-1">支持 PDF, Word (最大 50MB)</p>
      </div>

      {Object.values(uploadingFiles).length > 0 && (
        <div className="space-y-2 max-h-60 overflow-y-auto pr-2">
          {Object.values(uploadingFiles).map(({ file, status, progress, error }) => (
            <div key={file.name} className="flex items-center space-x-3 p-3 bg-card border rounded-lg text-sm">
              <div className="p-2 bg-muted rounded">
                <File size={16} className="text-muted-foreground" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between mb-1">
                  <span className="truncate font-medium">{file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {(file.size / (1024 * 1024)).toFixed(2)} MB
                  </span>
                </div>
                <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                  <div 
                    className={cn(
                      "h-full transition-all duration-300",
                      status === 'error' ? "bg-destructive" : status === 'completed' ? "bg-green-500" : "bg-primary"
                    )}
                    style={{ width: `${progress}%` }}
                  />
                </div>
                {status === 'error' && (
                  <p className="text-[10px] text-destructive mt-1 flex items-center">
                    <AlertCircle size={10} className="mr-1" /> {error}
                  </p>
                )}
              </div>
              <div>
                {status === 'uploading' ? <Loader2 size={16} className="animate-spin text-primary" /> :
                 status === 'completed' ? <CheckCircle2 size={16} className="text-green-500" /> :
                 <button onClick={() => setUploadingFiles(prev => {
                   const next = { ...prev };
                   delete next[file.name];
                   return next;
                 })}><X size={16} className="text-muted-foreground" /></button>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
