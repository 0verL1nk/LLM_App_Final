import { useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { Key, Shield, User as UserIcon, Bell, Palette, Save, Check } from 'lucide-react';

export default function Settings() {
  const { user } = useAuthStore();
  const [apiKey, setApiKey] = useState('************************');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const sections = [
    { id: 'profile', name: '个人资料', icon: UserIcon },
    { id: 'api', name: 'API 设置', icon: Key },
    { id: 'security', name: '安全与隐私', icon: Shield },
    { id: 'notifications', name: '通知设置', icon: Bell },
    { id: 'appearance', name: '外观定制', icon: Palette },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">系统设置</h1>
        <p className="text-muted-foreground mt-1">管理您的个人偏好、API 密钥与安全设置。</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        {/* Navigation */}
        <div className="md:col-span-1 space-y-1">
          {sections.map((section) => (
            <button
              key={section.id}
              className="w-full flex items-center space-x-3 px-3 py-2 rounded-md hover:bg-accent text-sm font-medium transition-colors"
            >
              <section.icon size={18} className="text-muted-foreground" />
              <span>{section.name}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="md:col-span-3 space-y-6">
          {/* Profile Section */}
          <div className="bg-card border rounded-xl p-6 space-y-6">
            <h3 className="text-lg font-semibold border-b pb-4">基本信息</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground">用户名</label>
                <input 
                  type="text" 
                  value={user?.username} 
                  disabled
                  className="w-full bg-muted border rounded-md px-3 py-2 text-sm cursor-not-allowed"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-muted-foreground">邮箱</label>
                <input 
                  type="email" 
                  value={user?.email} 
                  disabled
                  className="w-full bg-muted border rounded-md px-3 py-2 text-sm cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          {/* API Key Section */}
          <div className="bg-card border rounded-xl p-6 space-y-6">
            <h3 className="text-lg font-semibold border-b pb-4">OpenAI / DeepSeek API 密钥</h3>
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                配置您自己的 API 密钥以获得更快的处理速度和更高的配额限制。密钥将加密存储在后端数据库中。
              </p>
              <div className="space-y-2">
                <label className="text-sm font-medium">当前密钥</label>
                <div className="flex space-x-2">
                  <input 
                    type="password" 
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="flex-1 bg-background border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button 
                    onClick={handleSave}
                    className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors flex items-center"
                  >
                    {saved ? <Check size={16} className="mr-2" /> : <Save size={16} className="mr-2" />}
                    {saved ? '已保存' : '更新密钥'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Appearance Section */}
          <div className="bg-card border rounded-xl p-6 space-y-6">
            <h3 className="text-lg font-semibold border-b pb-4">界面偏好</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">紧凑模式</p>
                  <p className="text-xs text-muted-foreground">减少间距，显示更多内容。</p>
                </div>
                <div className="w-10 h-5 bg-muted rounded-full relative cursor-pointer">
                  <div className="absolute left-1 top-1 w-3 h-3 bg-white rounded-full" />
                </div>
              </div>
              <div className="flex items-center justify-between border-t pt-4">
                <div>
                  <p className="text-sm font-medium">自动滚动改写文</p>
                  <p className="text-xs text-muted-foreground">改写结果生成时自动定位到底部。</p>
                </div>
                <div className="w-10 h-5 bg-primary rounded-full relative cursor-pointer">
                  <div className="absolute right-1 top-1 w-3 h-3 bg-white rounded-full" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
