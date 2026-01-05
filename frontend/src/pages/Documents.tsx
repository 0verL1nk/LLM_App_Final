import { useQuery } from '@tanstack/react-query';
import { fileService } from '@/services/api';
import { FileUpload } from '@/components/features/files/FileUpload';
import { 
  FileText, 
   
  Trash2, 
  Eye, 
  Search,
  ArrowUpDown,
  Filter,
  Download
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { cn } from '@/lib/utils';

export default function Documents() {
  const [search, setSearch] = useState('');
  
  const { data: files, isLoading } = useQuery({
    queryKey: ['files'],
    queryFn: () => fileService.getFiles(),
  });

  const filteredFiles = files?.filter(file => 
    file.filename.toLowerCase().includes(search.toLowerCase())
  ) || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">文献列表</h1>
          <p className="text-muted-foreground mt-1">管理您上传的所有文献和分析结果。</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Upload Panel */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-card border rounded-xl p-4">
            <h3 className="font-semibold mb-4 text-sm">上传新文献</h3>
            <FileUpload />
          </div>
          
          <div className="bg-card border rounded-xl p-4">
            <h3 className="font-semibold mb-4 text-sm">筛选器</h3>
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-medium">处理状态</label>
                <select className="w-full bg-background border rounded-md px-2 py-1.5 text-sm">
                  <option>全部</option>
                  <option>已完成</option>
                  <option>处理中</option>
                  <option>已失败</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* List Panel */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="search"
                placeholder="搜索文献名称..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-card border rounded-md pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div className="flex items-center space-x-2">
              <button className="flex items-center text-sm border bg-card px-3 py-2 rounded-md hover:bg-accent transition-colors">
                <Filter size={14} className="mr-2" /> 筛选
              </button>
              <button className="flex items-center text-sm border bg-card px-3 py-2 rounded-md hover:bg-accent transition-colors">
                <ArrowUpDown size={14} className="mr-2" /> 排序
              </button>
            </div>
          </div>

          <div className="bg-card border rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-muted-foreground border-b uppercase text-[10px] font-bold tracking-wider">
                <tr>
                  <th className="px-6 py-3">文件名</th>
                  <th className="px-6 py-3">状态</th>
                  <th className="px-6 py-3">上传日期</th>
                  <th className="px-6 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {isLoading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="px-6 py-4"><div className="h-4 bg-muted rounded w-3/4"></div></td>
                      <td className="px-6 py-4"><div className="h-4 bg-muted rounded w-1/4"></div></td>
                      <td className="px-6 py-4"><div className="h-4 bg-muted rounded w-1/2"></div></td>
                      <td className="px-6 py-4 text-right"><div className="h-4 bg-muted rounded w-8 ml-auto"></div></td>
                    </tr>
                  ))
                ) : filteredFiles.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-12 text-center text-muted-foreground italic">
                      未发现匹配的文献
                    </td>
                  </tr>
                ) : (
                  filteredFiles.map((file) => (
                    <tr key={file.id} className="hover:bg-accent/50 transition-colors group">
                      <td className="px-6 py-4">
                        <div className="flex items-center space-x-3">
                          <div className="p-2 bg-primary/5 rounded group-hover:bg-primary/10 transition-colors">
                            <FileText size={18} className="text-primary" />
                          </div>
                          <span className="font-medium truncate max-w-[200px]">{file.filename}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={cn(
                          "px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide border",
                          file.status === 'completed' ? "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800" :
                          file.status === 'processing' ? "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800 animate-pulse" :
                          file.status === 'failed' ? "bg-red-100 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800" :
                          "bg-muted text-muted-foreground border-border"
                        )}>
                          {file.status === 'completed' ? '已完成' : 
                           file.status === 'processing' ? '处理中' : 
                           file.status === 'failed' ? '失败' : '排队中'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-muted-foreground">
                        {new Date(file.createdAt).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <Link 
                            to={`/documents/${file.id}`}
                            className="p-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-md transition-all"
                            title="查看详情"
                          >
                            <Eye size={16} />
                          </Link>
                          <button className="p-2 text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-all">
                            <Download size={16} />
                          </button>
                          <button className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-md transition-all">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
