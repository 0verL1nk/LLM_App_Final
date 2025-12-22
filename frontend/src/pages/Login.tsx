import React, { useState } from 'react';
import { ArrowRight, BookOpen } from 'lucide-react';

const Login: React.FC = () => {
  const [isRegisterMode, setIsRegisterMode] = useState(false);

  return (
    <div className="min-h-screen flex bg-white">
      {/* Left: Form */}
      <div className="flex-1 flex items-center justify-center p-8 sm:p-12 lg:p-16">
        <div className="w-full max-w-sm space-y-8">
          <div className="text-center">
            <div className="w-12 h-12 bg-primary-600 rounded-xl flex items-center justify-center text-white mx-auto mb-4">
              <BookOpen size={24} />
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-slate-900">
              {isRegisterMode ? '创建账号' : '欢迎回来'}
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              {isRegisterMode ? '请输入您的信息以注册' : '请输入您的账号信息以继续'}
            </p>
          </div>

          <form className="space-y-6">
            {isRegisterMode && (
              <div>
                <label className="block text-sm font-medium text-slate-700">用户名</label>
                <input
                  type="text"
                  className="mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                  placeholder="请输入用户名"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-700">邮箱</label>
              <input
                type="email"
                className="mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                placeholder="user@example.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">密码</label>
              <input
                type="password"
                className="mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                placeholder="••••••••"
              />
            </div>

            {isRegisterMode && (
              <div>
                <label className="block text-sm font-medium text-slate-700">确认密码</label>
                <input
                  type="password"
                  className="mt-1 block w-full px-3 py-2 bg-white border border-slate-300 rounded-lg text-sm shadow-sm placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                  placeholder="••••••••"
                />
              </div>
            )}

            <button
              type="submit"
              className="w-full flex justify-center items-center gap-2 py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 transition-colors"
            >
              {isRegisterMode ? '注册' : '登录'}
              <ArrowRight size={16} />
            </button>
          </form>

          <p className="text-center text-sm text-slate-500">
            {isRegisterMode ? (
              <>
                已有账号?{' '}
                <button
                  onClick={() => setIsRegisterMode(false)}
                  className="font-medium text-primary-600 hover:text-primary-500"
                >
                  立即登录
                </button>
              </>
            ) : (
              <>
                还没有账号?{' '}
                <button
                  onClick={() => setIsRegisterMode(true)}
                  className="font-medium text-primary-600 hover:text-primary-500"
                >
                  立即注册
                </button>
              </>
            )}
          </p>
        </div>
      </div>

      {/* Right: Feature/Image */}
      <div className="hidden lg:block relative w-0 flex-1 bg-slate-900">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-900 to-slate-900 opacity-90" />
        <div className="relative h-full flex flex-col justify-center px-12 text-white">
          <h2 className="text-4xl font-bold mb-6">智能解析，深度阅读。</h2>
          <p className="text-lg text-slate-300 max-w-md leading-relaxed">
            利用最先进的大语言模型，为您提供精准的文献总结、改写与问答服务。让科研更高效。
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;