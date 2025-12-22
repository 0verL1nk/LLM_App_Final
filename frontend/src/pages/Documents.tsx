import React, { useState } from 'react';
import { FileText, Search, MoreVertical, Filter } from 'lucide-react';
import { motion } from 'framer-motion';

const Documents: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('all');

  const documents = [
    { id: 1, name: 'Deep Learning Survey 2024.pdf', date: '2024-12-20', size: '2.3 MB', status: 'processed' },
    { id: 2, name: 'Attention Is All You Need.pdf', date: '2024-12-19', size: '1.8 MB', status: 'processed' },
    { id: 3, name: 'Transformers Research Paper.docx', date: '2024-12-18', size: '956 KB', status: 'processing' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">我的文献</h1>
        <button className="bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
          上传新文档
        </button>
      </div>

      <div className="flex gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
          <input
            type="text"
            placeholder="搜索文献..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white border border-slate-300 rounded-lg text-sm focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          />
        </div>
        <button className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-300 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors">
          <Filter size={16} />
          筛选
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-left py-3 px-6 text-sm font-semibold text-slate-900">文件名</th>
              <th className="text-left py-3 px-6 text-sm font-semibold text-slate-900">上传日期</th>
              <th className="text-left py-3 px-6 text-sm font-semibold text-slate-900">大小</th>
              <th className="text-left py-3 px-6 text-sm font-semibold text-slate-900">状态</th>
              <th className="text-right py-3 px-6 text-sm font-semibold text-slate-900">操作</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <motion.tr
                key={doc.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors"
              >
                <td className="py-4 px-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
                      <FileText size={20} className="text-slate-500" />
                    </div>
                    <span className="font-medium text-slate-900">{doc.name}</span>
                  </div>
                </td>
                <td className="py-4 px-6 text-sm text-slate-500">{doc.date}</td>
                <td className="py-4 px-6 text-sm text-slate-500">{doc.size}</td>
                <td className="py-4 px-6">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      doc.status === 'processed'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    {doc.status === 'processed' ? '已处理' : '处理中'}
                  </span>
                </td>
                <td className="py-4 px-6 text-right">
                  <button className="text-slate-400 hover:text-slate-600">
                    <MoreVertical size={18} />
                  </button>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Documents;