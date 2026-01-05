import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useAuthStore } from '@/stores/authStore';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, User, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const authSchema = z.object({
  username: z.string().min(3, '用户名至少3个字符'),
  password: z.string().min(6, '密码至少6个字符'),
  email: z.string().email('无效的邮箱地址').optional().or(z.literal('')),
});

type AuthValues = z.infer<typeof authSchema>;

export function AuthForm() {
  const [isLogin, setIsLogin] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const setAuth = useAuthStore((state) => state.setAuth);
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<AuthValues>({
    resolver: zodResolver(authSchema),
    defaultValues: {
      username: '',
      password: '',
      email: '',
    }
  });

  const onSubmit = async (data: AuthValues) => {
    if (!isLogin && !data.email) {
      setError('注册需要邮箱地址');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      // Simulation of API call
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Mock data
      const mockUser = {
        id: '1',
        username: data.username,
        email: data.email || `${data.username}@example.com`,
        apiKeyConfigured: false
      };
      
      setAuth('mock_token', mockUser);
      navigate('/');
    } catch (err: any) {
      setError(err.message || '操作失败，请稍后再试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md p-8 bg-card rounded-xl shadow-lg border">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-primary">{isLogin ? '欢迎回来' : '创建账号'}</h2>
        <p className="text-muted-foreground mt-2">
          {isLogin ? '请输入您的凭据以登录系统' : '填写以下信息以注册新账号'}
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">用户名</label>
          <div className="relative">
            <User className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              {...register('username')}
              type="text"
              placeholder="请输入用户名"
              className={cn(
                "w-full bg-background border rounded-md pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary",
                errors.username && "border-destructive focus:ring-destructive"
              )}
            />
          </div>
          {errors.username && <p className="text-xs text-destructive">{errors.username.message}</p>}
        </div>

        {!isLogin && (
          <div className="space-y-2">
            <label className="text-sm font-medium">邮箱</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                {...register('email')}
                type="email"
                placeholder="请输入邮箱"
                className={cn(
                  "w-full bg-background border rounded-md pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary",
                  errors.email && "border-destructive focus:ring-destructive"
                )}
              />
            </div>
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
        )}

        <div className="space-y-2">
          <label className="text-sm font-medium">密码</label>
          <div className="relative">
            <Lock className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              {...register('password')}
              type="password"
              placeholder="请输入密码"
              className={cn(
                "w-full bg-background border rounded-md pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary",
                errors.password && "border-destructive focus:ring-destructive"
              )}
            />
          </div>
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>

        {error && (
          <div className="p-3 bg-destructive/10 border border-destructive/20 text-destructive text-sm rounded-md">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="w-full bg-primary text-primary-foreground py-2 rounded-md font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center justify-center"
        >
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {isLogin ? '登录' : '注册'}
        </button>
      </form>

      <div className="mt-6 text-center text-sm">
        <span className="text-muted-foreground">
          {isLogin ? '还没有账号？' : '已经有账号了？'}
        </span>
        <button
          onClick={() => setIsLogin(!isLogin)}
          className="ml-1 text-primary font-medium hover:underline"
        >
          {isLogin ? '立即注册' : '立即登录'}
        </button>
      </div>
    </div>
  );
}