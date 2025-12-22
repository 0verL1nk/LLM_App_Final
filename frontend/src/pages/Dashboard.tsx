import React, { useCallback, useState } from 'react';
import { Upload, FileText, Clock, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ComponentType<any>;
  color: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon: Icon, color }) => (
  <motion.div
    whileHover={{ y: -4 }}
    className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-start justify-between"
  >
    <div>
      <p className="text-slate-500 text-sm font-medium mb-1">{title}</p>
      <h3 className="text-3xl font-bold text-slate-900">{value}</h3>
    </div>
    <div className={`p-3 rounded-xl ${color}`}>
      <Icon size={24} className="text-white" />
    </div>
  </motion.div>
);

const Dashboard: React.FC = () => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    // 处理文件上传
    console.log('Files dropped:', e.dataTransfer.files);
  }, []);

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-2xl font-bold text-slate-900"
        >
          欢迎回来, Ling 👋
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="text-slate-500 mt-1"
        >
          这里是您的文献阅读概览。
        </motion.p>
      </div>

      {/* Stats Grid */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-3 gap-6"
      >
        <StatCard title="已上传文献" value="12" icon={FileText} color="bg-blue-500" />
        <StatCard title="阅读时长 (小时)" value="4.5" icon={Clock} color="bg-emerald-500" />
        <StatCard title="AI 问答次数" value="86" icon={Sparkles} color="bg-violet-500" />
      </motion.div>

      {/* Upload Area */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="bg-white rounded-2xl border border-slate-200 p-8 shadow-sm"
      >
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer group transition-all ${
            isDragging
              ? 'border-primary-500 bg-primary-50'
              : 'border-slate-300 hover:border-primary-500 hover:bg-primary-50'
          }`}
        >
          <motion.div
            whileHover={{ scale: 1.1 }}
            className="w-16 h-16 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform"
          >
            <Upload size={32} />
          </motion.div>
          <h3 className="text-lg font-semibold text-slate-900">点击或拖拽上传文献</h3>
          <p className="text-slate-500 mt-2 text-sm">支持 PDF, DOCX, TXT (最大 50MB)</p>
          <button className="mt-4 bg-primary-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-primary-700 transition-colors">
            选择文件
          </button>
        </div>
      </motion.div>

      {/* Recent Files */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <h2 className="text-lg font-semibold text-slate-900 mb-4">最近阅读</h2>
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {[1, 2, 3].map((i) => (
            <motion.div
              key={i}
              whileHover={{ backgroundColor: '#f8fafc' }}
              className="flex items-center justify-between p-4 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
                  <FileText size={20} className="text-slate-500" />
                </div>
                <div>
                  <p className="font-medium text-slate-900">Deep Learning Survey 2024.pdf</p>
                  <p className="text-xs text-slate-500">2 小时前上传</p>
                </div>
              </div>
              <button className="text-primary-600 text-sm font-medium hover:underline">
                查看总结
              </button>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  );
};

export default Dashboard;