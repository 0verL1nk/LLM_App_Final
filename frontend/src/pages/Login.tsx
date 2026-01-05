import { AuthForm } from '@/components/features/auth/AuthForm';
import { motion } from 'framer-motion';

export default function Login() {
  return (
    <div className="min-h-screen flex bg-background font-sans">
      {/* Left side: Modern Branding */}
      <div className="hidden lg:flex lg:w-3/5 bg-slate-950 items-center justify-center p-12 relative overflow-hidden">
        {/* Animated Gradient Background */}
        <div className="absolute inset-0 opacity-40">
          <div className="absolute top-[-10%] left-[-10%] w-[70%] h-[70%] rounded-full bg-indigo-600/30 blur-[120px] animate-pulse" />
          <div className="absolute bottom-[-10%] right-[-10%] w-[60%] h-[60%] rounded-full bg-blue-600/20 blur-[100px]" />
        </div>
        
        {/* Abstract Grid Pattern */}
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay" />
        <div className="absolute inset-0 opacity-[0.15]" 
          style={{ backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)', backgroundSize: '40px 40px' }} 
        />

        <div className="relative z-10 text-white max-w-xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
          >
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-white/10 border border-white/20 text-xs font-medium mb-8 backdrop-blur-md">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
              </span>
              <span>Next Generation Research Tool</span>
            </div>
            
            <h1 className="text-6xl font-bold mb-6 tracking-tight leading-[1.1]">
              用 <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">AI</span> 重新定义<br />您的学术阅读
            </h1>
            <p className="text-xl text-slate-400 mb-10 leading-relaxed font-light">
              LLM App 是一款专为研究者打造的沉浸式工作空间，集成了最先进的语言模型，助您秒级理清复杂文献脉络。
            </p>
            
            <div className="grid grid-cols-2 gap-6">
              {[
                { label: "智能全文总结", desc: "毫秒级提取核心论点" },
                { label: "结构化脑图", desc: "自动可视化逻辑框架" },
                { label: "深度改写润色", desc: "提升学术表达专业性" },
                { label: "多维上下文问答", desc: "针对性解决理解难点" }
              ].map((f, i) => (
                <motion.div 
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + i * 0.1 }}
                  className="p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-colors"
                >
                  <h4 className="font-semibold text-white mb-1">{f.label}</h4>
                  <p className="text-xs text-slate-500">{f.desc}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Right side: Clean Auth Form */}
      <div className="w-full lg:w-2/5 flex items-center justify-center p-8 bg-slate-50 dark:bg-slate-900/50">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          <AuthForm />
        </motion.div>
      </div>
    </div>
  );
}