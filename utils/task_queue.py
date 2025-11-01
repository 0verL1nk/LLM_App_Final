"""
任务队列模块 - 使用 RQ (Redis Queue) 实现异步任务处理
"""
import os
import json
import sqlite3
from typing import Optional, Dict, Any
from enum import Enum
from redis import Redis
from rq import Queue
from rq.job import Job

# Redis 连接配置（可通过环境变量配置）
# 默认使用 localhost，因为 Redis 和应用在同一容器中
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
REDIS_URL = os.getenv('REDIS_URL', f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}')

# 创建 Redis 连接
try:
    redis_conn = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    # 测试连接
    redis_conn.ping()
except Exception as e:
    print(f"警告: Redis 连接失败: {e}")
    redis_conn = None

# 创建任务队列
task_queue = Queue('tasks', connection=redis_conn) if redis_conn else None


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    STARTED = "started"      # 已开始
    FINISHED = "finished"    # 已完成
    FAILED = "failed"        # 失败
    QUEUED = "queued"        # 已入队


def init_task_table(db_name='./database.sqlite'):
    """初始化任务状态表"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_status (
            task_id TEXT PRIMARY KEY,
            uid TEXT NOT NULL,
            content_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            error_message TEXT,
            job_id TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_status_uid ON task_status(uid, content_type)
    """)
    conn.commit()
    conn.close()


def create_task(task_id: str, uid: str, content_type: str, db_name='./database.sqlite'):
    """创建任务记录"""
    import datetime
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        INSERT OR REPLACE INTO task_status 
        (task_id, uid, content_type, status, created_at, updated_at, job_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (task_id, uid, content_type, TaskStatus.PENDING.value, current_time, current_time, None))
    conn.commit()
    conn.close()


def update_task_status(
    task_id: str, 
    status: TaskStatus, 
    job_id: Optional[str] = None,
    error_message: Optional[str] = None,
    db_name='./database.sqlite'
):
    """更新任务状态"""
    import datetime
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if error_message:
        cursor.execute("""
            UPDATE task_status 
            SET status = ?, updated_at = ?, error_message = ?, job_id = ?
            WHERE task_id = ?
        """, (status.value, current_time, error_message, job_id, task_id))
    else:
        cursor.execute("""
            UPDATE task_status 
            SET status = ?, updated_at = ?, job_id = ?
            WHERE task_id = ?
        """, (status.value, current_time, job_id, task_id))
    conn.commit()
    conn.close()


def get_task_status(task_id: str, db_name='./database.sqlite') -> Optional[Dict[str, Any]]:
    """获取任务状态"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT task_id, uid, content_type, status, created_at, updated_at, error_message, job_id
        FROM task_status
        WHERE task_id = ?
    """, (task_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return None
    
    return {
        'task_id': result[0],
        'uid': result[1],
        'content_type': result[2],
        'status': result[3],
        'created_at': result[4],
        'updated_at': result[5],
        'error_message': result[6],
        'job_id': result[7]
    }


def get_task_status_by_uid(uid: str, content_type: str, db_name='./database.sqlite') -> Optional[Dict[str, Any]]:
    """根据 uid 和 content_type 获取任务状态"""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT task_id, uid, content_type, status, created_at, updated_at, error_message, job_id
        FROM task_status
        WHERE uid = ? AND content_type = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (uid, content_type))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return None
    
    return {
        'task_id': result[0],
        'uid': result[1],
        'content_type': result[2],
        'status': result[3],
        'created_at': result[4],
        'updated_at': result[5],
        'error_message': result[6],
        'job_id': result[7]
    }


def get_job_status(job_id: str) -> Optional[str]:
    """从 RQ 获取任务状态"""
    if not redis_conn or not job_id:
        return None
    
    try:
        job = Job.fetch(job_id, connection=redis_conn)
        return job.get_status()
    except Exception:
        return None


def enqueue_task(task_func, *args, **kwargs) -> Optional[str]:
    """将任务加入队列"""
    if not task_queue:
        # 如果没有 Redis，直接同步执行
        try:
            result = task_func(*args, **kwargs)
            return result
        except Exception as e:
            raise e
    
    try:
        job = task_queue.enqueue(task_func, *args, **kwargs, job_timeout='10m')
        return job.id
    except Exception as e:
        print(f"任务入队失败: {e}")
        # 如果入队失败，回退到同步执行
        try:
            result = task_func(*args, **kwargs)
            return result
        except Exception as e:
            raise e

