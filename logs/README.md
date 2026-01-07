# 日志文件说明

本目录存放应用程序的日志文件。

## 📁 日志文件

### backend.log
**说明：** 后端服务器日志
**内容：**
- HTTP 请求/响应
- 数据库查询
- 任务处理状态
- 错误和异常信息
- WebSocket 连接状态

**日志级别：**
- DEBUG - 详细调试信息
- INFO - 一般信息（默认）
- WARNING - 警告信息
- ERROR - 错误信息
- CRITICAL - 严重错误

**日志轮转：**
- 单个文件最大 10MB
- 保留最近 5 个备份文件
- 备份文件命名：`backend.log.1`, `backend.log.2`, ...

### 前端日志
**说明：** 前端是浏览器应用，日志在开发者工具中查看
**查看方式：**
- 打开浏览器开发者工具（F12）
- 查看 Console 标签
- 查看 Network 标签（API 请求）
- Vite 开发服务器日志直接在终端显示

---

## 🔍 查看日志

### 实时查看后端日志
```bash
# 查看最新的日志
tail -f logs/backend.log

# 查看最近 100 行
tail -n 100 logs/backend.log

# 搜索特定关键词
grep "ERROR" logs/backend.log
grep "WebSocket" logs/backend.log
```

### 查看特定时间的日志
```bash
# 查看今天的日志
grep "$(date +%Y-%m-%d)" logs/backend.log

# 查看最近的错误
grep "ERROR" logs/backend.log | tail -20
```

---

## 📊 日志分析

### 统计请求类型
```bash
grep "GET /api/v1" logs/backend.log | wc -l
grep "POST /api/v1" logs/backend.log | wc -l
```

### 查看错误统计
```bash
grep "ERROR" logs/backend.log | awk '{print $5}' | sort | uniq -c | sort -rn
```

### 查看最慢的请求
```bash
grep "response_time" logs/backend.log | sort -t: -k2 -rn | head -10
```

---

## 🧹 日志清理

### 自动清理
日志文件会自动轮转，旧日志会被自动删除（只保留 5 个备份）。

### 手动清理
```bash
# 清空日志（谨慎操作）
> logs/backend.log

# 删除所有备份
rm logs/backend.log.*
```

---

## ⚙️ 日志配置

### 后端日志配置
**文件：** `src/llm_app/core/logger.py`

**修改日志级别：**
在 `.env` 文件中设置：
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**修改日志大小限制：**
在 `logger.py` 中修改 `maxBytes` 参数。

### 前端日志查看
前端日志直接在浏览器开发者工具中查看：

**浏览器控制台（F12）：**
- Console 标签：查看 `console.log`、错误信息
- Network 标签：查看 API 请求/响应
- Application 标签：查看本地存储、Cookie

**Vite 开发服务器：**
```bash
cd frontend
pnpm dev  # 日志直接在终端显示
```

---

## 📝 日志格式示例

### HTTP 请求日志
```
2026-01-06 22:34:01 - llm_app.main - INFO - HTTP Request
INFO:     127.0.0.1:49136 - "GET /api/v1/files/?page_size=10 HTTP/1.1" 200 OK
```

### 数据库查询日志
```
2026-01-06 22:34:01 - sqlalchemy.engine.Engine - INFO - SELECT users.uuid, users.username FROM users WHERE users.uuid = ?
```

### WebSocket 日志
```
2026-01-06 22:34:01 - llm_app.api.websocket - INFO - WebSocket connected for user 687eca57-9f9b-4b94-a853-66ece7dfb777
```

### 错误日志
```
2026-01-06 22:34:01 - llm_app.api.errors - ERROR - Unhandled Exception: AttributeError: type object 'File' has no attribute 'status'
```
