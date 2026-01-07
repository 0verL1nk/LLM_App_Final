import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fileService } from '@/services/api';
import { useTaskWebSocket } from '@/hooks/useTaskWebSocket';
import {
  ChevronLeft,
  MessageSquare,

  Layout,
  Share2,
  Download,
  Maximize2,
  Sparkles
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores/uiStore';
import { PdfViewer } from '@/components/features/documents/PdfViewer';
import { SummaryPanel } from '@/components/features/documents/SummaryPanel';
import { QAPanel } from '@/components/features/documents/QAPanel';
import { RewritePanel } from '@/components/features/documents/RewritePanel';
import { MindmapPanel } from '@/components/features/documents/MindmapPanel';

export default function Workspace() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { activeToolTab, setActiveToolTab, setSidebarCollapsed } = useUIStore();

  // Enable WebSocket for real-time task updates
  useTaskWebSocket();

  // Collapse sidebar by default in workspace for more space
  useEffect(() => {
    setSidebarCollapsed(true);
    return () => setSidebarCollapsed(false);
  }, [setSidebarCollapsed]);

  const { data: file, isLoading } = useQuery({
    queryKey: ['file', id],
    queryFn: () => fileService.getFile(id!),
    enabled: !!id,
  });

  const tools = [
    { id: 'summary', name: '智能总结', icon: Sparkles },
    { id: 'qa', name: 'AI 问答', icon: MessageSquare },
    { id: 'rewrite', name: '文本改写', icon: Share2 },
    { id: 'mindmap', name: '思维导图', icon: Layout },
  ];

  if (isLoading) return <div className="p-8">正在加载文献数据...</div>;

  return (
    <div className="flex h-[calc(100vh-4rem)] -m-6 overflow-hidden bg-background">
      {/* Workspace Header is handled by the main DashboardLayout header, 
          but we might want a sub-header for file info */}
      
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Subheader */}
        <div className="h-12 border-b bg-card flex items-center justify-between px-4">
          <div className="flex items-center space-x-4">
            <button 
              onClick={() => navigate('/documents')}
              className="p-1.5 hover:bg-accent rounded-md transition-colors"
            >
              <ChevronLeft size={18} />
            </button>
            <div className="flex items-center space-x-2">
              <span className="font-semibold truncate max-w-[300px]">{file?.original_filename || file?.filename}</span>
              <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-muted text-muted-foreground">PDF</span>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button className="p-1.5 hover:bg-accent rounded-md text-muted-foreground"><Download size={16} /></button>
            <button className="p-1.5 hover:bg-accent rounded-md text-muted-foreground"><Maximize2 size={16} /></button>
          </div>
        </div>

        {/* Workspace Main Area */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left: PDF Viewer */}
          <div className="flex-1 overflow-hidden flex flex-col">
            <PdfViewer fileId={id} />
          </div>

          {/* Right: AI Tools Sidebar */}
          <div className="w-[400px] border-l bg-card flex flex-col overflow-hidden">
            <div className="flex items-center border-b overflow-x-auto no-scrollbar bg-muted/30">
              {tools.map((tool) => (
                <button
                  key={tool.id}
                  onClick={() => setActiveToolTab(tool.id)}
                  className={cn(
                    "flex-1 flex items-center justify-center p-3 text-sm font-medium transition-all relative",
                    activeToolTab === tool.id 
                      ? "text-primary bg-background" 
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                  )}
                >
                  <tool.icon size={16} className="mr-2" />
                  <span>{tool.name}</span>
                  {activeToolTab === tool.id && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
                  )}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto">
              {activeToolTab === 'summary' && <SummaryPanel fileId={id!} />}
              {activeToolTab === 'qa' && <QAPanel fileId={id!} />}
              {activeToolTab === 'rewrite' && <RewritePanel fileId={id!} />}
              {activeToolTab === 'mindmap' && <MindmapPanel fileId={id!} />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
