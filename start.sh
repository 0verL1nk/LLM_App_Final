#!/bin/bash
set -e

# 清理函数：当收到退出信号时，清理所有后台进程
cleanup() {
    echo "正在关闭服务..."
    kill $REDIS_PID $WORKER_PID 2>/dev/null || true
    wait $REDIS_PID $WORKER_PID 2>/dev/null || true
    exit 0
}

# 注册清理函数
trap cleanup SIGTERM SIGINT

# 启动 Redis 服务器（后台运行）
echo "启动 Redis 服务器..."
redis-server --daemonize yes --protected-mode no
REDIS_PID=$(pgrep -f "redis-server" | head -1)

# 等待 Redis 启动
echo "等待 Redis 启动..."
for i in {1..10}; do
    if redis-cli ping > /dev/null 2>&1; then
        echo "Redis 已启动"
        break
    fi
    sleep 1
done

# 启动 RQ worker（后台运行）
echo "启动 RQ worker..."
cd /app
rq worker tasks --url redis://localhost:6379/0 > /tmp/rq_worker.log 2>&1 &
WORKER_PID=$!

# 等待 worker 启动
sleep 2

# 启动 Streamlit 应用（前台运行，这样容器不会退出）
echo "启动 Streamlit 应用..."
exec streamlit run 文件中心.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true

