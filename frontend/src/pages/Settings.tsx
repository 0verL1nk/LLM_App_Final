import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/stores/authStore';
import { userService } from '@/services/api';
import {
  Key,
  Shield,
  User as UserIcon,
  Bell,
  Palette,
  Save,
  Check,
  Trash2,
  Calendar,
  Cpu,
  Lock,
  Eye,
  EyeOff
} from 'lucide-react';
import { cn } from '@/lib/utils';

type TabType = 'profile' | 'api' | 'security' | 'notifications' | 'appearance';

export default function Settings() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState<TabType>('profile');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const queryClient = useQueryClient();

  // User preferences state
  const [compactMode, setCompactMode] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [taskNotifications, setTaskNotifications] = useState(true);

  // Fetch current user data
  const { data: currentUser, isLoading } = useQuery({
    queryKey: ['user'],
    queryFn: () => userService.getMe(),
  });

  // Update API key mutation
  const updateKeyMutation = useMutation({
    mutationFn: (newApiKey: string) => userService.updateApiKey(newApiKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      setApiKey('');
    },
  });

  // Update preferences mutation
  const updatePreferencesMutation = useMutation({
    mutationFn: (preferences: any) => userService.updatePreferences(preferences),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  // Delete API key mutation
  const deleteKeyMutation = useMutation({
    mutationFn: () => userService.deleteApiKey(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user'] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const handleSaveApiKey = () => {
    if (apiKey.trim()) {
      updateKeyMutation.mutate(apiKey);
    }
  };

  const handleDeleteApiKey = () => {
    if (confirm('确定要删除已配置的 API 密钥吗？删除后将使用系统默认配置。')) {
      deleteKeyMutation.mutate();
    }
  };

  const handleSavePreferences = () => {
    updatePreferencesMutation.mutate({
      compact_mode: compactMode,
      auto_scroll: autoScroll,
      email_notifications: emailNotifications,
      task_notifications: taskNotifications,
    });
  };

  const sections = [
    { id: 'profile' as TabType, name: '个人资料', icon: UserIcon },
    { id: 'api' as TabType, name: 'API 设置', icon: Key },
    { id: 'security' as TabType, name: '安全设置', icon: Shield },
    { id: 'notifications' as TabType, name: '通知设置', icon: Bell },
    { id: 'appearance' as TabType, name: '外观定制', icon: Palette },
  ];

  const toggleSwitch = (
    enabled: boolean,
    onChange: (value: boolean) => void,
    disabled = false
  ) => (
    <button
      onClick={() => !disabled && onChange(!enabled)}
      disabled={disabled}
      className={cn(
        "relative w-11 h-6 rounded-full transition-colors duration-200 ease-in-out",
        enabled ? "bg-primary" : "bg-muted",
        disabled && "opacity-50 cursor-not-allowed"
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 left-0.5 bg-white rounded-full h-5 w-5 transition-transform duration-200 ease-in-out shadow-sm",
          enabled && "translate-x-5"
        )}
      />
    </button>
  );

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">系统设置</h1>
        <p className="text-muted-foreground mt-1">管理您的个人资料、API 密钥与系统偏好。</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        {/* Navigation */}
        <div className="md:col-span-1 space-y-1">
          {sections.map((section) => (
            <button
              key={section.id}
              onClick={() => setActiveTab(section.id)}
              className={cn(
                "w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
                activeTab === section.id
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-accent"
              )}
            >
              <section.icon size={18} className={cn(activeTab === section.id ? "text-current" : "text-muted-foreground")} />
              <span>{section.name}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="md:col-span-3 space-y-6">
          {/* Profile Section */}
          {activeTab === 'profile' && (
            <>
              <div className="bg-card border rounded-xl p-6 space-y-6">
                <div className="flex items-center justify-between border-b pb-4">
                  <h3 className="text-lg font-semibold">基本信息</h3>
                  <UserIcon size={20} className="text-muted-foreground" />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-muted-foreground">用户名</label>
                    <div className="flex items-center space-x-2 bg-muted border rounded-md px-3 py-2">
                      <UserIcon size={16} className="text-muted-foreground" />
                      <input
                        type="text"
                        value={isLoading ? '加载中...' : (currentUser?.username || user?.username)}
                        disabled
                        className="flex-1 bg-transparent border-0 text-sm focus:outline-none cursor-not-allowed"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-muted-foreground">邮箱地址</label>
                    <div className="flex items-center space-x-2 bg-muted border rounded-md px-3 py-2">
                      <Lock size={16} className="text-muted-foreground" />
                      <input
                        type="text"
                        value={isLoading ? '加载中...' : (currentUser?.email || user?.email)}
                        disabled
                        className="flex-1 bg-transparent border-0 text-sm focus:outline-none cursor-not-allowed"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-muted-foreground">账号创建时间</label>
                    <div className="flex items-center space-x-2 bg-muted border rounded-md px-3 py-2">
                      <Calendar size={16} className="text-muted-foreground" />
                      <input
                        type="text"
                        value={isLoading ? '加载中...' : (currentUser?.created_at ?
                          new Date(currentUser.created_at).toLocaleDateString('zh-CN', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric'
                          }) : '未知')}
                        disabled
                        className="flex-1 bg-transparent border-0 text-sm focus:outline-none cursor-not-allowed"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-muted-foreground">偏好模型</label>
                    <div className="flex items-center space-x-2 bg-muted border rounded-md px-3 py-2">
                      <Cpu size={16} className="text-muted-foreground" />
                      <input
                        type="text"
                        value={isLoading ? '加载中...' : (currentUser?.preferred_model || 'qwen-max')}
                        disabled
                        className="flex-1 bg-transparent border-0 text-sm focus:outline-none cursor-not-allowed"
                      />
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-muted/50 border border-dashed rounded-xl p-6">
                <div className="flex items-start space-x-3">
                  <Shield className="text-primary mt-0.5" size={20} />
                  <div className="flex-1 space-y-1">
                    <p className="text-sm font-medium">账号安全提示</p>
                    <p className="text-xs text-muted-foreground">
                      您的账号数据已加密保护。请定期更新密码并确保 API 密钥安全。
                      如遇到问题，请联系技术支持。
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* API Settings Section */}
          {activeTab === 'api' && (
            <>
              <div className="bg-card border rounded-xl p-6 space-y-6">
                <div className="flex items-center justify-between border-b pb-4">
                  <div>
                    <h3 className="text-lg font-semibold">DashScope API 密钥</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      配置您自己的 API 密钥以获得更快的处理速度和更高的配额
                    </p>
                  </div>
                  <Key size={20} className="text-muted-foreground" />
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-muted/30 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <div className={cn(
                        "w-2 h-2 rounded-full",
                        currentUser?.has_api_key || user?.apiKeyConfigured
                          ? "bg-green-500"
                          : "bg-amber-500"
                      )} />
                      <span className="text-sm font-medium">
                        当前状态: {currentUser?.has_api_key || user?.apiKeyConfigured ? (
                          <span className="text-green-600">已配置</span>
                        ) : (
                          <span className="text-amber-600">未配置（使用系统默认）</span>
                        )}
                      </span>
                    </div>
                    {(currentUser?.has_api_key || user?.apiKeyConfigured) && (
                      <button
                        onClick={handleDeleteApiKey}
                        disabled={deleteKeyMutation.isPending}
                        className="text-destructive hover:text-destructive/80 text-xs flex items-center px-2 py-1 rounded hover:bg-destructive/10 transition-colors disabled:opacity-50"
                      >
                        <Trash2 size={12} className="mr-1" />
                        删除密钥
                      </button>
                    )}
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      {(currentUser?.has_api_key || user?.apiKeyConfigured)
                        ? '更新 API 密钥（留空以保持当前密钥）'
                        : '输入新的 API 密钥'}
                    </label>
                    <div className="flex space-x-2">
                      <div className="relative flex-1">
                        <input
                          type={showApiKey ? "text" : "password"}
                          value={apiKey}
                          onChange={(e) => setApiKey(e.target.value)}
                          placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                          className="w-full bg-background border rounded-md px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
                        />
                        <button
                          type="button"
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                        </button>
                      </div>
                      <button
                        onClick={handleSaveApiKey}
                        disabled={updateKeyMutation.isPending}
                        className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors flex items-center disabled:opacity-50 min-w-[100px]"
                      >
                        {updateKeyMutation.isPending ? (
                          <>保存中...</>
                        ) : (
                          <>
                            <Save size={16} className="mr-2" />
                            保存
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  <div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900 rounded-md p-3">
                    <p className="text-xs text-blue-800 dark:text-blue-200">
                      <strong>提示：</strong>API 密钥将加密存储在后端数据库中，只有您可以访问。
                      请妥善保管您的密钥，不要与他人分享。
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-card border rounded-xl p-6 space-y-4">
                <h4 className="font-semibold text-sm">使用统计</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center p-3 bg-muted/30 rounded-lg">
                    <p className="text-2xl font-bold text-primary">--</p>
                    <p className="text-xs text-muted-foreground mt-1">本月调用次数</p>
                  </div>
                  <div className="text-center p-3 bg-muted/30 rounded-lg">
                    <p className="text-2xl font-bold text-primary">--</p>
                    <p className="text-xs text-muted-foreground mt-1">总处理文件</p>
                  </div>
                  <div className="text-center p-3 bg-muted/30 rounded-lg">
                    <p className="text-2xl font-bold text-primary">--</p>
                    <p className="text-xs text-muted-foreground mt-1">平均响应时间</p>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Security Section */}
          {activeTab === 'security' && (
            <div className="bg-card border rounded-xl p-6 space-y-6">
              <div className="flex items-center justify-between border-b pb-4">
                <h3 className="text-lg font-semibold">安全设置</h3>
                <Shield size={20} className="text-muted-foreground" />
              </div>

              <div className="space-y-4">
                <div className="p-4 bg-muted/30 rounded-lg">
                  <p className="text-sm font-medium mb-1">数据加密</p>
                  <p className="text-xs text-muted-foreground">
                    您的所有数据均使用 AES-256 加密存储，API 密钥采用额外的加密层保护。
                  </p>
                </div>

                <div className="p-4 bg-muted/30 rounded-lg">
                  <p className="text-sm font-medium mb-1">会话管理</p>
                  <p className="text-xs text-muted-foreground">
                    您的登录令牌有效期为 24 小时，超时后需要重新登录。
                    支持「记住我」功能可延长会话时间。
                  </p>
                </div>

                <div className="p-4 bg-muted/30 rounded-lg">
                  <p className="text-sm font-medium mb-1">访问控制</p>
                  <p className="text-xs text-muted-foreground">
                    只允许您本人访问您的文件和数据。所有 API 请求都经过身份验证和授权检查。
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Notifications Section */}
          {activeTab === 'notifications' && (
            <div className="bg-card border rounded-xl p-6 space-y-6">
              <div className="flex items-center justify-between border-b pb-4">
                <h3 className="text-lg font-semibold">通知设置</h3>
                <Bell size={20} className="text-muted-foreground" />
              </div>

              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="text-sm font-medium">任务完成通知</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      当文档分析、总结等任务完成时接收通知
                    </p>
                  </div>
                  {toggleSwitch(taskNotifications, setTaskNotifications)}
                </div>

                <div className="flex items-center justify-between border-t pt-4">
                  <div className="flex-1">
                    <p className="text-sm font-medium">邮件通知</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      通过邮件接收重要更新和系统通知
                    </p>
                  </div>
                  {toggleSwitch(emailNotifications, setEmailNotifications)}
                </div>

                <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 rounded-md p-3">
                  <p className="text-xs text-amber-800 dark:text-amber-200">
                    <strong>注意：</strong>浏览器通知需要您的许可才能显示。
                    您可以在浏览器设置中管理通知权限。
                  </p>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={handleSavePreferences}
                  disabled={updatePreferencesMutation.isPending}
                  className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors flex items-center disabled:opacity-50"
                >
                  {updatePreferencesMutation.isPending ? (
                    <>保存中...</>
                  ) : saved ? (
                    <>
                      <Check size={16} className="mr-2" />
                      已保存
                    </>
                  ) : (
                    <>
                      <Save size={16} className="mr-2" />
                      保存设置
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Appearance Section */}
          {activeTab === 'appearance' && (
            <div className="bg-card border rounded-xl p-6 space-y-6">
              <div className="flex items-center justify-between border-b pb-4">
                <h3 className="text-lg font-semibold">外观定制</h3>
                <Palette size={20} className="text-muted-foreground" />
              </div>

              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="text-sm font-medium">紧凑模式</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      减少界面间距，在相同空间内显示更多内容
                    </p>
                  </div>
                  {toggleSwitch(compactMode, setCompactMode)}
                </div>

                <div className="flex items-center justify-between border-t pt-4">
                  <div className="flex-1">
                    <p className="text-sm font-medium">自动滚动</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      AI 生成新内容时自动滚动到底部
                    </p>
                  </div>
                  {toggleSwitch(autoScroll, setAutoScroll)}
                </div>

                <div className="p-4 bg-muted/30 rounded-lg">
                  <p className="text-sm font-medium mb-2">主题预览</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-3 bg-background border-2 border-primary rounded-md text-center">
                      <p className="text-xs font-medium">浅色主题</p>
                    </div>
                    <div className="p-3 bg-slate-900 border border-slate-700 rounded-md text-center text-white">
                      <p className="text-xs font-medium">深色主题</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    主题将自动跟随系统设置
                  </p>
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={handleSavePreferences}
                  disabled={updatePreferencesMutation.isPending}
                  className="bg-primary text-primary-foreground px-4 py-2 rounded-md text-sm font-medium hover:bg-primary/90 transition-colors flex items-center disabled:opacity-50"
                >
                  {updatePreferencesMutation.isPending ? (
                    <>保存中...</>
                  ) : saved ? (
                    <>
                      <Check size={16} className="mr-2" />
                      已保存
                    </>
                  ) : (
                    <>
                      <Save size={16} className="mr-2" />
                      保存设置
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
