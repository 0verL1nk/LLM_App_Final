import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  description?: string;
  trend?: {
    value: number;
    isUp: boolean;
  };
  className?: string;
}

export function StatCard({ title, value, icon: Icon, description, trend, className }: StatCardProps) {
  return (
    <motion.div 
      whileHover={{ y: -4 }}
      className={cn(
        "p-6 bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-3xl shadow-sm hover:shadow-xl hover:shadow-indigo-500/5 transition-all", 
        className
      )}
    >
      <div className="flex items-center justify-between mb-5">
        <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-2xl text-indigo-600 dark:text-indigo-400 group-hover:bg-indigo-600 group-hover:text-white transition-colors">
          <Icon size={24} strokeWidth={2.5} />
        </div>
        {trend && (
          <div className={cn(
            "text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded-full",
            trend.isUp 
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400" 
              : "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400"
          )}>
            {trend.isUp ? '↑' : '↓'} {trend.value}%
          </div>
        )}
      </div>
      <div>
        <p className="text-xs font-black text-slate-400 uppercase tracking-[0.1em]">{title}</p>
        <h3 className="text-3xl font-black mt-1 tracking-tight text-slate-900 dark:text-white">{value}</h3>
        {description && (
          <p className="text-[11px] text-slate-500 mt-3 font-medium flex items-center">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mr-2 opacity-50" />
            {description}
          </p>
        )}
      </div>
    </motion.div>
  );
}