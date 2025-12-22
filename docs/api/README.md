# 文献阅读助手 API 接口文档

## 概述

本文档描述了文献阅读助手系统的 RESTful API 接口。API 采用 JSON 格式进行数据交换，基于 HTTP 协议。

### Base URL

```
开发环境: http://localhost:8501/api/v1
生产环境: https://your-domain.com/api/v1
```

### 认证方式

API 使用 Token 认证。所有需要认证的接口必须在请求头中包含：

```
Authorization: Bearer <token>
```

### 通用响应格式

#### 成功响应

```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

#### 错误响应

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": { ... }
  }
}
```

### HTTP 状态码

- `200` - 请求成功
- `201` - 创建成功
- `400` - 请求参数错误
- `401` - 未认证或 Token 失效
- `403` - 没有权限
- `404` - 资源不存在
- `422` - 数据验证失败
- `429` - 请求过于频繁
- `500` - 服务器内部错误

---

## 认证接口

### 1. 用户注册

**POST** `/auth/register`

#### 请求体

```json
{
  "username": "string, 3-50字符",
  "email": "string, 邮箱格式",
  "password": "string, 最小8字符"
}
```

#### 响应

```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "token": "string, JWT token",
    "expires_at": "datetime"
  },
  "message": "注册成功"
}
```

---

### 2. 用户登录

**POST** `/auth/login`

#### 请求体

```json
{
  "username": "string",
  "password": "string"
}
```

#### 响应

```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "token": "string",
    "expires_at": "datetime"
  },
  "message": "登录成功"
}
```

---

### 3. 用户登出

**POST** `/auth/logout`

#### 响应

```json
{
  "success": true,
  "message": "已安全登出"
}
```

---

## 用户管理接口

### 1. 获取当前用户信息

**GET** `/users/me`

#### 响应

```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "api_key_configured": "boolean",
    "preferred_model": "string",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
}
```

---

### 2. 更新用户 API Key

**PUT** `/users/api-key`

#### 请求体

```json
{
  "api_key": "string, DashScope API Key"
}
```

#### 响应

```json
{
  "success": true,
  "message": "API Key 更新成功"
}
```

---

### 3. 更新用户偏好

**PUT** `/users/preferences`

#### 请求体

```json
{
  "preferred_model": "string, 模型名称"
}
```

#### 响应

```json
{
  "success": true,
  "message": "偏好设置更新成功"
}
```

---

## 文件管理接口

### 1. 上传文件

**POST** `/files/upload`

#### 请求

- `Content-Type: multipart/form-data`
- `file`: 文件 (支持 PDF, DOCX, TXT)
- `tags`: 字符串数组, 可选 (文件标签)

#### 响应

```json
{
  "success": true,
  "data": {
    "file_id": "uuid",
    "original_filename": "string",
    "filename": "string, 存储的文件名",
    "file_size": "integer, 字节数",
    "mime_type": "string",
    "md5": "string, 文件MD5哈希",
    "upload_url": "string, 可下载链接",
    "processing_status": "pending|processing|completed|failed",
    "created_at": "datetime"
  },
  "message": "文件上传成功"
}
```

---

### 2. 获取文件列表

**GET** `/files`

#### 查询参数

- `page`: integer, 页码 (默认: 1)
- `page_size`: integer, 每页数量 (默认: 20, 最大: 100)
- `search`: string, 搜索关键词
- `status`: string, 过滤状态 (all|pending|processing|completed|failed)
- `sort`: string, 排序方式 (created_desc|created_asc|name_asc|name_desc)

#### 响应

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "file_id": "uuid",
        "original_filename": "string",
        "filename": "string",
        "file_size": "integer",
        "mime_type": "string",
        "processing_status": "string",
        "tags": ["array"],
        "created_at": "datetime",
        "updated_at": "datetime"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 50,
      "total_pages": 3
    }
  }
}
```

---

### 3. 获取文件详情

**GET** `/files/{file_id}`

#### 响应

```json
{
  "success": true,
  "data": {
    "file_id": "uuid",
    "original_filename": "string",
    "filename": "string",
    "file_size": "integer",
    "mime_type": "string",
    "md5": "string",
    "processing_status": "string",
    "tags": ["array"],
    "extracted_text": "string, 提取的文本内容",
    "word_count": "integer, 字数统计",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
}
```

---

### 4. 删除文件

**DELETE** `/files/{file_id}`

#### 响应

```json
{
  "success": true,
  "message": "文件删除成功"
}
```

---

### 5. 下载文件

**GET** `/files/{file_id}/download`

#### 响应

文件下载流

---

## 文档处理接口

### 1. 文档文本提取

**POST** `/documents/{file_id}/extract`

#### 请求体

```json
{
  "task_id": "uuid, 可选，传入则查询任务状态"
}
```

#### 响应 (异步)

```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "pending|processing|completed|failed",
    "progress": "integer, 0-100",
    "result": {
      "text": "string, 提取的文本",
      "sections": ["array, 文本段落"],
      "metadata": {
        "page_count": "integer",
        "word_count": "integer",
        "language": "string"
      }
    }
  },
  "message": "文本提取任务已创建"
}
```

---

### 2. 文档总结

**POST** `/documents/{file_id}/summarize`

#### 请求体

```json
{
  "task_id": "uuid, 可选",
  "options": {
    "summary_type": "brief|detailed|custom",
    "length": "short|medium|long",
    "focus_areas": ["array, 关注点"],
    "language": "zh|en"
  }
}
```

#### 响应

```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "pending|processing|completed|failed",
    "result": {
      "summary": "string, 总结内容",
      "key_points": ["array, 关键点"],
      "sections_summary": [
        {
          "section": "string",
          "summary": "string"
        }
      ],
      "statistics": {
        "original_length": "integer",
        "summary_length": "integer",
        "compression_ratio": "float"
      }
    }
  }
}
```

---

### 3. 文档问答

**POST** `/documents/{file_id}/qa`

#### 请求体

```json
{
  "question": "string, 问题",
  "context": "string, 可选，上下文补充",
  "history": [
    {
      "question": "string",
      "answer": "string"
    }
  ]
}
```

#### 响应

```json
{
  "success": true,
  "data": {
    "answer": "string, 答案",
    "confidence": "float, 0-1，可信度",
    "sources": [
      {
        "page": "integer",
        "section": "string",
        "excerpt": "string"
      }
    ],
    "suggested_questions": ["array, 建议后续问题"]
  }
}
```

---

### 4. 文段改写

**POST** `/documents/{file_id}/rewrite`

#### 请求体

```json
{
  "text": "string, 要改写的文本",
  "rewrite_type": "academic|casual|formal|creative|concise",
  "tone": "string, 语调",
  "length": "shorter|same|longer",
  "language": "zh|en"
}
```

#### 响应

```json
{
  "success": true,
  "data": {
    "rewritten_text": "string, 改写后的文本",
    "original_length": "integer",
    "rewritten_length": "integer",
    "improvements": ["array, 改进说明"],
    "alternatives": [
      {
        "text": "string, 备选方案1",
        "description": "string"
      }
    ]
  }
}
```

---

### 5. 思维导图

**POST** `/documents/{file_id}/mindmap`

#### 请求体

```json
{
  "task_id": "uuid, 可选",
  "options": {
    "max_depth": "integer, 最大层级 (1-5)",
    "include_keywords": "boolean",
    "group_by": "topic|structure|timeline"
  }
}
```

#### 响应

```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "pending|processing|completed|failed",
    "result": {
      "mindmap": {
        "name": "string, 中心主题",
        "children": [
          {
            "name": "string, 分支名称",
            "value": "integer, 权重",
            "children": [
              {
                "name": "string",
                "value": "integer"
              }
            ]
          }
        ]
      },
      "keywords": ["array, 关键词"],
      "structure": {
        "total_branches": "integer",
        "max_depth": "integer",
        "main_topics": ["array"]
      }
    }
  }
}
```

---

## 任务管理接口

### 1. 获取任务状态

**GET** `/tasks/{task_id}`

#### 响应

```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "task_type": "extract|summarize|rewrite|mindmap",
    "status": "pending|processing|completed|failed|cancelled",
    "progress": "integer, 0-100",
    "started_at": "datetime",
    "completed_at": "datetime",
    "error_message": "string, 错误信息",
    "result": {}
  }
}
```

---

### 2. 取消任务

**POST** `/tasks/{task_id}/cancel`

#### 响应

```json
{
  "success": true,
  "message": "任务已取消"
}
```

---

### 3. 获取用户任务列表

**GET** `/tasks`

#### 查询参数

- `status`: string, 过滤状态 (all|pending|processing|completed|failed)
- `task_type`: string, 任务类型 (extract|summarize|qa|rewrite|mindmap)
- `page`: integer, 页码
- `page_size`: integer, 每页数量

#### 响应

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "task_id": "uuid",
        "task_type": "string",
        "status": "string",
        "progress": "integer",
        "created_at": "datetime",
        "completed_at": "datetime",
        "file": {
          "file_id": "uuid",
          "filename": "string"
        }
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 50,
      "total_pages": 3
    }
  }
}
```

---

## 统计接口

### 1. 获取用户统计

**GET** `/statistics`

#### 响应

```json
{
  "success": true,
  "data": {
    "files": {
      "total": 12,
      "processed": 10,
      "processing": 2,
      "this_month": 5
    },
    "usage": {
      "total_api_calls": 156,
      "total_tokens": 125000,
      "this_month_calls": 45
    },
    "tasks": {
      "total_completed": 89,
      "pending": 3,
      "average_completion_time": "number, 秒"
    }
  }
}
```

---

## WebSocket (可选)

用于实时推送任务进度

### 连接

```
ws://localhost:8501/ws/tasks/{task_id}
```

### 消息格式

#### 推送任务进度

```json
{
  "type": "task_progress",
  "task_id": "uuid",
  "status": "processing",
  "progress": 45,
  "message": "正在提取文本..."
}
```

#### 推送任务完成

```json
{
  "type": "task_completed",
  "task_id": "uuid",
  "status": "completed",
  "result": { ... }
}
```

---

## 错误代码

| 错误代码 | HTTP状态 | 描述 |
|---------|---------|------|
| `AUTH_REQUIRED` | 401 | 需要认证 |
| `AUTH_INVALID` | 401 | 认证信息无效 |
| `AUTH_EXPIRED` | 401 | Token 已过期 |
| `PERMISSION_DENIED` | 403 | 权限不足 |
| `RESOURCE_NOT_FOUND` | 404 | 资源不存在 |
| `VALIDATION_ERROR` | 422 | 数据验证失败 |
| `FILE_TOO_LARGE` | 413 | 文件过大 |
| `FILE_TYPE_INVALID` | 422 | 不支持的文件类型 |
| `API_KEY_INVALID` | 422 | API Key 无效 |
| `RATE_LIMIT_EXCEEDED` | 429 | 请求频率超限 |
| `TASK_NOT_FOUND` | 404 | 任务不存在 |
| `TASK_ALREADY_COMPLETED` | 422 | 任务已完成 |
| `SERVER_ERROR` | 500 | 服务器内部错误 |

---

## SDK 示例

### Python

```python
import requests

class LiteratureAssistantAPI:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def login(self, username, password):
        response = requests.post(
            f'{self.base_url}/auth/login',
            json={'username': username, 'password': password}
        )
        return response.json()

    def upload_file(self, file_path):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            headers = {'Authorization': f'Bearer {self.token}'}
            response = requests.post(
                f'{self.base_url}/files/upload',
                files=files,
                headers=headers
            )
        return response.json()

    def summarize_document(self, file_id, summary_type='brief'):
        response = requests.post(
            f'{self.base_url}/documents/{file_id}/summarize',
            json={'options': {'summary_type': summary_type}},
            headers=self.headers
        )
        return response.json()

    def get_task_status(self, task_id):
        response = requests.get(
            f'{self.base_url}/tasks/{task_id}',
            headers=self.headers
        )
        return response.json()
```

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1.0.0 | 2024-12-22 | 初始版本 |

---

## 联系信息

- API 支持: support@example.com
- 文档更新: https://github.com/your-org/literature-assistant-docs