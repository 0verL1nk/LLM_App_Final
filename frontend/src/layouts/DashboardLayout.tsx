import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, FileText, Settings, LogOut, Menu, X, BookOpen } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface SidebarItemProps {
  icon: React.ComponentType<any>;
  label: string;
  to: string;
}

const SidebarItem: React.FC<SidebarItemProps> = ({ icon: Icon, label, to }) => (
  <NavLink
    to={to}
    className={({ isActive }) =>
      `flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
        isActive
          ? 'bg-primary-50 text-primary-700 font-medium'
          : 'text-slate-600 hover:bg-slate-100'
      }`
    }
  >
    <Icon size={20} />
    <span>{label}</span>
  </NavLink>
);

const DashboardLayout: React.FC = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Sidebar - Desktop */}
      <aside className="hidden md:flex w-64 flex-col bg-white border-r border-slate-200 h-full">
        <div className="p-6 flex items-center gap-2">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center text-white">
            <BookOpen size={20} />
          </div>
          <span className="text-xl font-bold text-slate-800">LitReader AI</span>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-1">
          <SidebarItem icon={LayoutDashboard} label="仪表盘" to="/dashboard" />
          <SidebarItem icon={FileText} label="我的文献" to="/documents" />
          <SidebarItem icon={Settings} label="设置" to="/settings" />
        </nav>

        <div className="p-4 border-t border-slate-100">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-3 w-full text-slate-600 hover:bg-red-50 hover:text-red-600 rounded-xl transition-colors"
          >
            <LogOut size={20} />
            <span>退出登录</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 md:px-8">
          <button
            className="md:hidden"
            onClick={() => setIsMobileMenuOpen(true)}
          >
            <Menu className="text-slate-600" />
          </button>

          <div className="flex items-center gap-4 ml-auto">
            <div className="flex flex-col items-end">
              <span className="text-sm font-medium text-slate-900">Dr. Ling</span>
              <span className="text-xs text-slate-500">Premium User</span>
            </div>
            <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-bold border-2 border-white shadow-sm">
              L
            </div>
          </div>
        </header>

        {/* Scrollable Content Area */}
        <main className="flex-1 overflow-auto p-6 md:p-8">
          <Outlet />
        </main>
      </div>

      {/* Mobile Sidebar Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/50 md:hidden"
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <motion.div
              initial={{ x: -256 }}
              animate={{ x: 0 }}
              exit={{ x: -256 }}
              className="w-64 h-full bg-white p-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center text-white">
                    <BookOpen size={20} />
                  </div>
                  <span className="text-xl font-bold text-slate-800">LitReader AI</span>
                </div>
                <button onClick={() => setIsMobileMenuOpen(false)}>
                  <X className="text-slate-600" />
                </button>
              </div>
              <nav className="space-y-1">
                <SidebarItem icon={LayoutDashboard} label="仪表盘" to="/dashboard" />
                <SidebarItem icon={FileText} label="我的文献" to="/documents" />
                <SidebarItem icon={Settings} label="设置" to="/settings" />
              </nav>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default DashboardLayout;