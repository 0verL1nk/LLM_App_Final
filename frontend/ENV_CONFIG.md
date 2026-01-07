# 环境配置说明

## 开发环境 vs 生产环境

### 开发环境（当前配置）
```bash
# 使用相对路径，通过 Vite 代理转发到后端
VITE_API_BASE_URL=/api/v1

# WebSocket 需要完整 URL（Vite 代理不支持 WebSocket）
VITE_WS_BASE_URL=ws://localhost:8501/api/v1/ws/tasks
```

**优点：**
- ✅ 避免 CORS 跨域问题
- ✅ 统一的开发域名和端口
- ✅ Vite 自动代理到后端

**缺点：**
- ❌ WebSocket 需要单独配置完整 URL
- ❌ 需要后端服务运行在 8501 端口

---

### 生产环境
```bash
# 生产环境使用完整的后端 URL
VITE_API_BASE_URL=http://your-domain.com/api/v1
VITE_WS_BASE_URL=ws://your-domain.com/api/v1/ws/tasks
```

**配置说明：**
- 前端静态文件由后端 FastAPI 服务
- 不需要 Vite 代理
- 所有请求都发往同一个域名

---

## WebSocket 跨域问题

### 为什么 WebSocket 会有跨域问题？

1. **Vite HTTP 代理不支持 WebSocket 协议升级**
   - Vite 的 `server.proxy` 只代理 HTTP/HTTPS 请求
   - WebSocket 需要单独的 `ws://` 或 `wss://` 连接

2. **浏览器安全策略**
   - WebSocket 连接需要明确的 CORS 支持
   - 开发环境可以直接连接到 `localhost:8501`

### 解决方案

**方案 1：开发环境直接连接（推荐）**
```bash
# .env
VITE_WS_BASE_URL=ws://localhost:8501/api/v1/ws/tasks
```
- ✅ 简单直接
- ✅ 适合本地开发
- ❌ 需要后端允许跨域

**方案 2：后端允许 WebSocket 跨域**
```python
# 后端已经配置了 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 常见问题

### Q1: 为什么 HTTP API 可以用代理，WebSocket 不行？
A: Vite 的代理只处理 HTTP/HTTPS 请求，不支持 WebSocket 协议升级。

### Q2: 生产环境如何配置？
A: 生产环境前端静态文件由后端服务，使用相对路径或完整域名都可以。

### Q3: 如何测试 WebSocket 连接？
A:
1. 启动后端：`make run` 或 `python -m src.llm_app.main`
2. 启动前端：`cd frontend && pnpm dev`
3. 登录后，检查浏览器控制台的 WebSocket 连接日志

---

## 端口配置

### 后端端口
- **默认端口**：`8501`
- **环境变量**：`LLM_APP_PORT`
- **修改方式**：`.env` 文件或启动命令

### 前端端口
- **开发服务器**：`5173`（Vite 默认）
- **生产构建**：静态文件，无独立端口

---

## 检查清单

开发环境启动前检查：
- [ ] 后端服务运行在 8501 端口
- [ ] 前端 `.env` 文件配置正确
- [ ] `VITE_API_BASE_URL=/api/v1`（相对路径）
- [ ] `VITE_WS_BASE_URL=ws://localhost:8501/api/v1/ws/tasks`
- [ ] 浏览器控制台无 CORS 错误
- [ ] WebSocket 连接成功
