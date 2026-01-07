import { useQuery } from '@tanstack/react-query';
import { StatCard } from '@/components/features/dashboard/StatCard';
import { FileText, Clock, CheckCircle, Zap, Upload, ArrowRight, Star } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { statisticsService, fileService } from '@/services/api';
import { FavoriteButton } from '@/components/features/files/FavoriteButton';

export default function Dashboard() {
  const user = useAuthStore((state) => state.user);

  // Fetch statistics data
  const { data: statsData } = useQuery({
    queryKey: ['statistics'],
    queryFn: () => statisticsService.getSummary(),
  });

  // Fetch recent files
  const { data: filesData } = useQuery({
    queryKey: ['files'],
    queryFn: () => fileService.getFiles({ page_size: 10, sort: 'created_desc' }),
  });

  // Fetch favorite files
  const { data: favoritesData, isLoading: favoritesLoading } = useQuery({
    queryKey: ['favorites'],
    queryFn: () => fileService.getFavorites({ page_size: 4 }),
  });

  const favorites = favoritesData?.data?.items || [];

  const stats = [
    {
      title: '总文献数',
      value: statsData?.data?.total_files?.toString() || '0',
      icon: FileText,
      trend: { value: 8, isUp: true },
      description: '本月新增 ' + (statsData?.data?.new_files_this_month || 0) + ' 篇',
      className: "border-l-4 border-l-indigo-500"
    },
    {
      title: '正在处理',
      value: statsData?.data?.processing_files?.toString() || '0',
      icon: Clock,
      description: '平均处理耗时 ' + (statsData?.data?.avg_processing_time || '45s'),
      className: "border-l-4 border-l-amber-500"
    },
    {
      title: '已完成分析',
      value: statsData?.data?.completed_tasks?.toString() || '0',
      icon: CheckCircle,
      trend: { value: 12, isUp: true },
      description: '分析覆盖率 100%',
      className: "border-l-4 border-l-emerald-500"
    },
    {
      title: 'AI 额度使用',
      value: (statsData?.data?.api_usage_percentage || 0) + '%',
      icon: Zap,
      description: statsData?.data?.plan_type || '免费方案',
      className: "border-l-4 border-l-rose-500"
    },
  ];

  const recentFiles = filesData?.items?.slice(0, 3) || [];

  // Helper function to format time ago
  const getTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 3600) {
      return Math.floor(seconds / 60) + '分钟前';
    } else if (seconds < 86400) {
      return Math.floor(seconds / 3600) + '小时前';
    } else if (seconds < 604800) {
      return Math.floor(seconds / 86400) + '天前';
    } else {
      return date.toLocaleDateString();
    }
  };

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  };

  return (
    <div className="max-w-[1400px] mx-auto space-y-10">
      <div className="flex justify-between items-end">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <h1 className="text-4xl font-bold tracking-tight text-slate-900 dark:text-white">
            下午好, <span className="text-indigo-600">{user?.username}</span> 👋
          </h1>
          <p className="text-slate-500 mt-2 text-lg">
            {!statsData?.data || statsData?.data?.processing_files === 0
              ? '暂无正在处理的任务。上传文献开始 AI 分析吧！'
              : `今天有 ${statsData?.data?.processing_files} 个任务正在处理中，查看最新进度。`}
          </p>
        </motion.div>
        <Link to="/documents" className="hidden md:flex items-center space-x-2 bg-slate-900 dark:bg-white dark:text-slate-900 text-white px-5 py-2.5 rounded-xl font-medium hover:opacity-90 transition-all shadow-xl shadow-indigo-500/10">
          <Upload size={18} />
          <span>上传文献</span>
        </Link>
      </div>

      <motion.div 
        variants={container}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
      >
        {stats.map((stat, i) => (
          <motion.div key={i} variants={item}>
            <StatCard {...stat} className={stat.className} />
          </motion.div>
        ))}
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Action Area */}
        <motion.div 
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 space-y-6"
        >
          <div className="relative overflow-hidden bg-indigo-600 rounded-3xl p-8 text-white shadow-2xl shadow-indigo-500/20">
            <div className="absolute top-0 right-0 p-8 opacity-10">
              <Zap size={160} />
            </div>
            <div className="relative z-10 space-y-4 max-w-md">
              <h2 className="text-3xl font-bold">文献智能工作空间</h2>
              <p className="text-indigo-100 opacity-90 leading-relaxed">
                进入 Workspace，同时开启 PDF 阅读、AI 实时问答与思维导图生成，享受无缝的研究体验。
              </p>
              <div className="pt-2">
                <Link to="/documents" className="inline-flex items-center space-x-2 bg-white text-indigo-600 px-6 py-3 rounded-2xl font-bold hover:bg-indigo-50 transition-all group">
                  <span>立即开始阅读</span>
                  <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                </Link>
              </div>
            </div>
          </div>

          <div className="bg-card border border-slate-200 dark:border-slate-800 rounded-3xl p-6 shadow-sm">
            <h3 className="text-xl font-bold mb-6 flex items-center">
              <Star className="mr-2 text-amber-500 fill-amber-500" size={20} />
              收藏的文献
            </h3>

            {favoritesLoading ? (
              <div className="text-center py-8 text-slate-500">
                加载中...
              </div>
            ) : favorites.length === 0 ? (
              <div className="text-center py-8 text-slate-500">
                <p className="mb-2">还没有收藏的文献</p>
                <Link to="/documents" className="text-indigo-600 hover:text-indigo-700 text-sm">
                  去浏览文献 →
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {favorites.map((file: any) => (
                  <Link
                    key={file.file_id}
                    to={`/workspace/${file.file_id}`}
                    className="p-4 rounded-2xl border bg-slate-50/50 dark:bg-slate-900/50 hover:border-indigo-500/50 transition-all cursor-pointer group relative"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-3 flex-1 min-w-0">
                        <div className="p-2 bg-white dark:bg-slate-800 rounded-xl shadow-sm">
                          <FileText size={20} className="text-indigo-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-bold truncate text-sm">{file.original_filename}</p>
                          <p className="text-xs text-slate-500">
                            {file.processing_status === 'completed' ? '已完成' : '处理中'}
                          </p>
                        </div>
                      </div>
                      <div className="ml-2">
                        <FavoriteButton
                          fileId={file.file_id}
                          isFavorite={file.is_favorite}
                          size={18}
                        />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </motion.div>

        {/* Sidebar in Dashboard */}
        <motion.div 
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
          className="space-y-6"
        >
          <div className="bg-card border border-slate-200 dark:border-slate-800 rounded-3xl overflow-hidden shadow-sm">
            <div className="p-6 border-b flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
              <h3 className="font-bold">最近阅读</h3>
              <Link to="/documents" className="text-xs font-bold text-indigo-600 hover:opacity-80">查看全部</Link>
            </div>
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {recentFiles.length > 0 ? recentFiles.map((doc: any) => (
                <Link
                  key={doc.id}
                  to={`/documents/${doc.id}`}
                  className="p-4 flex items-center justify-between hover:bg-indigo-50/50 dark:hover:bg-indigo-900/10 transition-colors group"
                >
                  <div className="flex items-center space-x-3 overflow-hidden">
                    <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400 group-hover:text-indigo-600 transition-colors">
                      <FileText size={18} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-bold truncate group-hover:text-indigo-600 transition-colors">{doc.filename}</p>
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">
                        {Math.round(doc.file_size / 1024 / 1024 * 10) / 10}MB • {getTimeAgo(doc.created_at)}
                      </p>
                    </div>
                  </div>
                  <ArrowRight size={14} className="text-slate-300 group-hover:text-indigo-600 -translate-x-2 opacity-0 group-hover:translate-x-0 group-hover:opacity-100 transition-all" />
                </Link>
              )) : (
                <div className="p-8 text-center text-slate-400 text-sm">
                  暂无文献，请先上传文件
                </div>
              )}
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-900 to-slate-800 rounded-3xl p-6 text-white relative overflow-hidden shadow-xl shadow-slate-900/20">
             <div className="relative z-10">
               <h4 className="font-bold mb-2 flex items-center text-indigo-400">
                 <Star size={16} className="mr-2 fill-indigo-400" />
                 使用提示
               </h4>
               <p className="text-sm text-slate-300 mb-4">
                 {!statsData || statsData.total_files === 0
                   ? '上传您的第一篇文献开始使用 AI 智能分析功能。'
                   : `您已处理 ${statsData.total_files || 0} 篇文献，继续探索更多 AI 功能！`}
               </p>
               <div className="flex items-center space-x-2">
                 <Link
                   to="/documents"
                   className="text-xs bg-white/10 hover:bg-white/20 px-4 py-2 rounded-xl font-bold transition-all border border-white/10"
                 >
                   {!statsData || statsData.total_files === 0 ? '上传文献' : '查看文献'}
                 </Link>
                 {statsData && statsData.total_files > 0 && (
                   <Link
                     to="/settings"
                     className="text-xs bg-indigo-600/50 hover:bg-indigo-600/70 px-4 py-2 rounded-xl font-bold transition-all"
                   >
                     配置 API
                   </Link>
                 )}
               </div>
             </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}