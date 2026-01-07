import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/authStore';
import { useUIStore } from '@/stores/uiStore';
import { statisticsService } from '@/services/api';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  FileText,
  Settings,
  LogOut,
  Menu,
  ChevronLeft,
  Search,
  Command,
  Bell
} from 'lucide-react';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { motion, AnimatePresence } from 'framer-motion';

export function DashboardLayout() {
  const { sidebarCollapsed, toggleSidebar } = useUIStore();
  const { user, clearAuth } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  // Fetch user statistics for quota display
  const { data: stats } = useQuery({
    queryKey: ['statistics'],
    queryFn: () => statisticsService.getSummary(),
  });

  const handleLogout = () => {
    clearAuth();
    navigate('/login');
  };

  const navItems = [
    { name: '仪表盘', icon: LayoutDashboard, path: '/' },
    { name: '文献中心', icon: FileText, path: '/documents' },
    { name: '系统设置', icon: Settings, path: '/settings' },
  ];

  return (
    <div className="flex h-screen bg-white dark:bg-slate-950 font-sans text-slate-900 dark:text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside 
        className={cn(
          "bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 flex flex-col transition-all duration-300 ease-in-out z-20",
          sidebarCollapsed ? "w-20" : "w-72"
        )}
      >
        <div className="p-6 flex items-center justify-between h-20">
          {!sidebarCollapsed && (
            <Link to="/" className="flex items-center space-x-3 group">
              <div className="w-9 h-9 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 group-hover:scale-105 transition-transform">
                <Command size={20} />
              </div>
              <span className="font-black text-2xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600 dark:from-white dark:to-slate-400">LLM App</span>
            </Link>
          )}
          {sidebarCollapsed && (
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white mx-auto shadow-lg shadow-indigo-500/30">
               <Command size={22} />
            </div>
          )}
        </div>

        <div className="px-4 py-4 overflow-y-auto no-scrollbar flex-1">
          <nav className="space-y-2">
            {!sidebarCollapsed && <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] px-3 mb-4">主要菜单</p>}
            {navItems.map((item) => {
              const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center p-3 rounded-2xl transition-all duration-200 relative group",
                    isActive 
                      ? "bg-indigo-50 dark:bg-indigo-950/30 text-indigo-600 dark:text-indigo-400" 
                      : "text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-900 hover:text-slate-900 dark:hover:text-white"
                  )}
                >
                  <item.icon size={20} className={cn("min-w-[20px]", isActive ? "stroke-[2.5px]" : "stroke-[1.5px]")} />
                  {!sidebarCollapsed && <span className={cn("ml-4 font-bold text-sm", isActive ? "opacity-100" : "opacity-80 group-hover:opacity-100")}>{item.name}</span>}
                  {isActive && !sidebarCollapsed && (
                    <motion.div layoutId="sidebar-active" className="absolute right-3 w-1.5 h-1.5 rounded-full bg-indigo-600 dark:bg-indigo-400" />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-100 dark:border-slate-800 space-y-4">
          {!sidebarCollapsed && (
            <div className="bg-slate-50 dark:bg-slate-900 rounded-2xl p-4">
              <div className="flex items-center space-x-3 mb-3">
                <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-bold">
                  {user?.username?.[0]?.toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold truncate">{user?.username}</p>
                  <p className="text-[10px] text-slate-500 truncate">
                    {stats?.plan_type || '免费计划'}
                  </p>
                </div>
              </div>
              <div className="w-full bg-slate-200 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden mb-1">
                 <div
                   className="bg-indigo-600 h-full transition-all duration-500"
                   style={{ width: `${stats?.api_usage_percentage || 0}%` }}
                 />
              </div>
              <p className="text-[10px] text-slate-500 flex justify-between">
                <span>额度使用: {stats?.api_usage_percentage || 0}%</span>
                <span>{stats?.tokens_used || 0} tokens</span>
              </p>
            </div>
          )}

          <div className="flex items-center space-x-2">
            <button 
              onClick={handleLogout}
              className={cn(
                "flex items-center rounded-2xl p-3 transition-all text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/20 font-bold text-sm",
                sidebarCollapsed ? "mx-auto" : "w-full"
              )}
            >
              <LogOut size={20} />
              {!sidebarCollapsed && <span className="ml-4">注销退出</span>}
            </button>
            {!sidebarCollapsed && <button onClick={toggleSidebar} className="p-3 bg-slate-50 dark:bg-slate-900 text-slate-400 rounded-2xl hover:text-slate-900 transition-colors"><ChevronLeft size={20} /></button>}
          </div>
          {sidebarCollapsed && <button onClick={toggleSidebar} className="w-full p-3 flex justify-center text-slate-400 hover:text-indigo-600 transition-colors"><Menu size={20} /></button>}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Header */}
        <header className="h-20 flex items-center justify-between px-8 bg-white/80 dark:bg-slate-950/80 backdrop-blur-md z-10">
          <div className="flex items-center flex-1 max-w-xl">
            <div className="relative w-full group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Search size={18} className="text-slate-400 group-focus-within:text-indigo-500 transition-colors" />
              </div>
              <input
                type="search"
                placeholder="搜索文献、报告或笔记... (⌘ + K)"
                autoComplete="off"
                className="w-full bg-slate-50 dark:bg-slate-900 border-none rounded-2xl pl-12 pr-4 py-3 text-sm focus:ring-2 focus:ring-indigo-500/20 transition-all dark:text-white"
              />
            </div>
          </div>
          
          <div className="flex items-center space-x-6 pl-8">
            <div className="flex items-center space-x-2">
               <button className="p-2.5 bg-slate-50 dark:bg-slate-900 text-slate-500 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-all relative">
                 <Bell size={20} />
                 <span className="absolute top-2 right-2 w-2 h-2 bg-rose-500 rounded-full border-2 border-white dark:border-slate-900" />
               </button>
               <ThemeToggle />
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-auto relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2, ease: "easeOut" }}
              className="p-8 h-full"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}