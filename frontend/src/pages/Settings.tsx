import React, { useState } from 'react';
import { Key, User, Bell, Palette } from 'lucide-react';
import { motion } from 'framer-motion';

const Settings: React.FC = () => {
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('qwen-max');

  const models = [
    { value: 'qwen-max', label: 'Qwen Max (推荐)' },
    { value: 'qwen-plus', label: 'Qwen Plus' },
    { value: 'qwen-turbo', label: 'Qwen Turbo' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">设置</h1>
        <p className="text-slate-500 mt-1">管理您的账户和应用偏好</p>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl border border-slate-200 p-6 space-y-6"
      >
        <div className="flex items-center gap-3 pb-4 border-b border-slate-200">
          <Key className="text-slate-600" size={20} />
          <h2 className="text-lg font-semibold text-slate-900">API 配置</h2>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              DashScope API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              placeholder="请输入您的 API Key"
            />
            <p className="mt-1 text-xs text-slate-500">
              您的 API Key 将安全存储在本地，不会上传到服务器
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">模型选择</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
            >
              {models.map((model) => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>
          </div>

          <button className="bg-primary-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-primary-700 transition-colors">
            保存配置
          </button>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white rounded-xl border border-slate-200 p-6 space-y-6"
      >
        <div className="flex items-center gap-3 pb-4 border-b border-slate-200">
          <User className="text-slate-600" size={20} />
          <h2 className="text-lg font-semibold text-slate-900">账户信息</h2>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">用户名</label>
            <input
              type="text"
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm"
              value="Dr. Ling"
              readOnly
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">邮箱</label>
            <input
              type="email"
              className="w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm"
              value="user@example.com"
              readOnly
            />
          </div>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="bg-white rounded-xl border border-slate-200 p-6 space-y-6"
      >
        <div className="flex items-center gap-3 pb-4 border-b border-slate-200">
          <Bell className="text-slate-600" size={20} />
          <h2 className="text-lg font-semibold text-slate-900">通知偏好</h2>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">文件处理完成通知</p>
              <p className="text-xs text-slate-500">当文件处理完成时发送通知</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" className="sr-only peer" defaultChecked />
              <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
            </label>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default Settings;