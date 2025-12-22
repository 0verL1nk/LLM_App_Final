# =============================================================================
# LLM App Makefile
# 自动化项目开发、测试、部署流程
# =============================================================================

# 变量定义
PYTHON := python3
UV := uv
PROJECT_NAME := llm-app
VENV_DIR := .venv
PYTHON_VERSION := 3.9

# 颜色定义
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# 默认目标
.PHONY: help
help: ## 显示帮助信息
	@echo "$(BLUE)LLM App 项目 Makefile$(NC)"
	@echo ""
	@echo "$(GREEN)可用命令:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# =============================================================================
# 环境检查与安装
# =============================================================================

.PHONY: check-deps
check-deps: ## 检查系统依赖 (Python, uv, Redis)
	@echo "$(BLUE)检查系统依赖...$(NC)"
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "$(RED)错误: Python3 未安装$(NC)"; exit 1; }
	@echo "  ✓ Python3: $$($(PYTHON) --version)"
	@command -v $(UV) >/dev/null 2>&1 || { echo "$(YELLOW)警告: uv 未安装$(NC)"; echo "  安装 uv: https://docs.astral.sh/uv/"; exit 1; }
	@echo "  ✓ uv: $$($(UV) --version)"
	@echo ""

.PHONY: check-python-version
check-python-version: ## 检查 Python 版本
	@echo "$(BLUE)检查 Python 版本...$(NC)"
	@PYTHON_VERSION_OK=$$($(PYTHON) -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)'); \
	if [ $$? -eq 0 ]; then \
		echo "  ✓ Python 版本符合要求 (>= 3.9)"; \
	else \
		echo "$(RED)错误: 需要 Python 3.9 或更高版本$(NC)"; \
		echo "  当前版本: $$($(PYTHON) --version)"; \
		exit 1; \
	fi
	@echo ""

.PHONY: install-uv
install-uv: ## 安装 uv (如果未安装)
	@echo "$(BLUE)安装 uv...$(NC)"
	@command -v $(UV) >/dev/null 2>&1 && { echo "  ✓ uv 已安装"; } || { \
		echo "  正在安装 uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
		echo "  ✓ uv 安装完成"; \
		echo "  请重新运行此命令或添加到 PATH"; \
	}

.PHONY: check-redis
check-redis: ## 检查 Redis 服务
	@echo "$(BLUE)检查 Redis 服务...$(NC)"
	@command -v redis-cli >/dev/null 2>&1 || { \
		echo "$(YELLOW)⚠️  Redis CLI 未安装$(NC)"; \
		echo "  可选安装:"; \
		echo "    Ubuntu/Debian: sudo apt-get install redis-server"; \
		echo "    macOS: brew install redis"; \
		echo "    Docker: docker run -d -p 6379:6379 redis"; \
		echo ""; \
		echo "  注意: 异步任务功能需要 Redis，但项目默认使用内存模式"; \
		echo ""; \
		return 0; \
	}
	@REDIS_OK=$$(redis-cli ping 2>/dev/null | grep -c PONG); \
	if [ $$REDIS_OK -eq 1 ]; then \
		echo "  ✅ Redis 服务正在运行"; \
	else \
		echo "$(YELLOW)⚠️  Redis 服务未启动$(NC)"; \
		echo "  启动命令: redis-server"; \
		echo "  或使用 Docker: docker run -d -p 6379:6379 redis"; \
		echo ""; \
		echo "  💡 项目默认使用内存模式，无需 Redis 即可运行"; \
		echo ""; \
	fi

.PHONY: show-config-redis
show-config-redis: ## 显示 Redis 配置
	@echo "$(BLUE)Redis 配置信息:$(NC)"
	@echo "  USE_REDIS: $$(grep -E '^USE_REDIS' .env 2>/dev/null || echo '未设置 (默认: false)')"
	@echo "  REDIS_HOST: $$(grep -E '^REDIS_HOST' .env 2>/dev/null || echo 'localhost (默认)')"
	@echo "  REDIS_PORT: $$(grep -E '^REDIS_PORT' .env 2>/dev/null || echo '6379 (默认)')"
	@echo ""
	@echo "$(GREEN)当前队列模式:$(NC)"
	@echo "  项目会智能检测 Redis 配置"; \
	echo "  默认使用内存模式 (无需 Redis)"; \
	echo "  设置 USE_REDIS=true 可启用 Redis 队列"

.PHONY: test-redis
test-redis: ## 测试 Redis 连接
	@echo "$(BLUE)测试 Redis 连接...$(NC)"
	@command -v redis-cli >/dev/null 2>&1 || { \
		echo "$(RED)❌ redis-cli 未安装$(NC)"; \
		exit 1; \
	}
	@REDIS_OK=$$(redis-cli ping 2>/dev/null | grep -c PONG); \
	if [ $$REDIS_OK -eq 1 ]; then \
		echo "  ✅ Redis 连接成功"; \
		redis-cli info server | grep -E 'redis_version|used_memory'; \
	else \
		echo "$(RED)❌ Redis 连接失败$(NC)"; \
		echo "  请启动 Redis 服务后重试"; \
		exit 1; \
	fi

.PHONY: check-all-deps
check-all-deps: check-deps check-python-version check-redis ## 检查所有依赖
	@echo "$(GREEN)✓ 所有依赖检查完成$(NC)"

# =============================================================================
# 开发环境设置
# =============================================================================

.PHONY: setup
setup: ## 初始化开发环境
	@echo "$(BLUE)初始化开发环境...$(NC)"
	@$(MAKE) install-deps
	@$(MAKE) install-dev-deps
	@$(MAKE) pre-commit-install
	@$(MAKE) ensure-dirs
	@echo ""
	@echo "$(GREEN)✓ 开发环境设置完成!$(NC)"
	@echo ""
	@echo "$(YELLOW)下一步:$(NC)"
	@echo "  1. 设置环境变量: export DASHSCOPE_API_KEY='your_api_key'"
	@echo "  2. 运行测试: make test"
	@echo "  3. 启动应用: make run"

.PHONY: install-deps
install-deps: ## 安装项目依赖
	@echo "$(BLUE)安装项目依赖...$(NC)"
	@$(UV) sync --no-install-project
	@echo "  ✓ 依赖安装完成"

.PHONY: install-dev-deps
install-dev-deps: ## 安装开发依赖
	@echo "$(BLUE)安装开发依赖...$(NC)"
	@$(UV) sync --all-extras --dev
	@echo "  ✓ 开发依赖安装完成"

.PHONY: ensure-dirs
ensure-dirs: ## 确保必要目录存在
	@echo "$(BLUE)创建必要目录...$(NC)"
	@mkdir -p uploads
	@mkdir -p logs
	@echo "  ✓ 目录创建完成"

.PHONY: clean
clean: ## 清理临时文件和缓存
	@echo "$(BLUE)清理临时文件...$(NC)"
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .coverage .pytest_cache htmlcov .mypy_cache .ruff_cache
	@rm -rf .venv
	@echo "  ✓ 清理完成"

.PHONY: clean-all
clean-all: clean ## 清理所有生成文件 (包括数据库)
	@echo "$(BLUE)清理所有生成文件...$(NC)"
	@rm -rf database.sqlite uploads logs
	@echo "  ✓ 清理完成"

# =============================================================================
# Pre-commit 设置
# =============================================================================

.PHONY: pre-commit-install
pre-commit-install: ## 安装 pre-commit 钩子
	@echo "$(BLUE)安装 pre-commit 钩子...$(NC)"
	@$(UV) run pre-commit install
	@echo "  ✓ pre-commit 钩子安装完成"

.PHONY: pre-commit-run
pre-commit-run: ## 运行所有 pre-commit 检查
	@echo "$(BLUE)运行 pre-commit 检查...$(NC)"
	@$(UV) run pre-commit run --all-files
	@echo "  ✓ 检查完成"

# =============================================================================
# 代码质量
# =============================================================================

.PHONY: lint
lint: ## 运行代码检查 (Ruff)
	@echo "$(BLUE)运行代码检查...$(NC)"
	@$(UV) run ruff check src/
	@echo "  ✓ 检查完成"

.PHONY: lint-fix
lint-fix: ## 自动修复代码问题
	@echo "$(BLUE)自动修复代码问题...$(NC)"
	@$(UV) run ruff check src/ --fix
	@$(UV) run ruff format src/
	@echo "  ✓ 修复完成"

.PHONY: type-check
type-check: ## 运行类型检查 (MyPy)
	@echo "$(BLUE)运行类型检查...$(NC)"
	@$(UV) run mypy src/
	@echo "  ✓ 类型检查完成"

.PHONY: security-check
security-check: ## 运行安全检查 (Bandit)
	@echo "$(BLUE)运行安全检查...$(NC)"
	@$(UV) run bandit -r src/
	@echo "  ✓ 安全检查完成"

.PHONY: check-all
check-all: lint type-check security-check ## 运行所有代码质量检查
	@echo ""
	@echo "$(GREEN)✓ 所有代码质量检查通过$(NC)"

# =============================================================================
# 测试
# =============================================================================

.PHONY: test
test: ## 运行所有测试
	@echo "$(BLUE)运行测试...$(NC)"
	@$(UV) run pytest --cov=src/llm_app --cov-report=term-missing --cov-report=html -v
	@echo ""
	@echo "$(GREEN)✓ 测试完成$(NC)"
	@echo "  查看覆盖率报告: htmlcov/index.html"

.PHONY: test-unit
test-unit: ## 运行单元测试
	@echo "$(BLUE)运行单元测试...$(NC)"
	@$(UV) run pytest tests/unit/ -v
	@echo "  ✓ 单元测试完成"

.PHONY: test-integration
test-integration: ## 运行集成测试
	@echo "$(BLUE)运行集成测试...$(NC)"
	@$(UV) run pytest tests/integration/ -v
	@echo "  ✓ 集成测试完成"

.PHONY: test-fast
test-fast: ## 快速测试 (跳过集成测试)
	@echo "$(BLUE)运行快速测试...$(NC)"
	@$(UV) run pytest tests/unit/ -v --ignore=tests/integration
	@echo "  ✓ 快速测试完成"

# =============================================================================
# 构建与运行
# =============================================================================

.PHONY: run
run: ## 启动应用
	@echo "$(BLUE)启动 LLM App...$(NC)"
	@echo ""
	@$(UV) run streamlit run app.py --server.port 8501

.PHONY: run-dev
run-dev: ## 启动开发模式 (带重载)
	@echo "$(BLUE)启动开发模式...$(NC)"
	@$(UV) run streamlit run app.py --server.port 8501 --server.fileWatcherType

.PHONY: build
build: ## 构建项目
	@echo "$(BLUE)构建项目...$(NC)"
	@$(UV) run python -m build
	@echo "  ✓ 构建完成"

# =============================================================================
# 文档
# =============================================================================

.PHONY: docs
docs: ## 生成文档
	@echo "$(BLUE)生成文档...$(NC)"
	@$(UV) run mkdocs build --clean
	@echo "  ✓ 文档生成完成 (site/ 目录)"

.PHONY: docs-serve
docs-serve: ## 启动文档服务器
	@echo "$(BLUE)启动文档服务器...$(NC)"
	@$(UV) run mkdocs serve

# =============================================================================
# Docker
# =============================================================================

.PHONY: docker-build
docker-build: ## 构建 Docker 镜像
	@echo "$(BLUE)构建 Docker 镜像...$(NC)"
	docker build -t $(PROJECT_NAME):latest .
	@echo "  ✓ Docker 镜像构建完成"

.PHONY: docker-run
docker-run: ## 运行 Docker 容器
	@echo "$(BLUE)运行 Docker 容器...$(NC)"
	docker run -d --name $(PROJECT_NAME) \
		-p 8501:8501 \
		-e DASHSCOPE_API_KEY=$$DASHSCOPE_API_KEY \
		-v $(PWD)/database.sqlite:/app/database.sqlite \
		-v $(PWD)/uploads:/app/uploads \
		$(PROJECT_NAME):latest
	@echo "  ✓ 容器启动完成 (http://localhost:8501)"

.PHONY: docker-compose-up
docker-compose-up: ## 使用 Docker Compose 启动
	@echo "$(BLUE)使用 Docker Compose 启动...$(NC)"
	DASHSCOPE_API_KEY=$$DASHSCOPE_API_KEY docker-compose up -d
	@echo "  ✓ 服务启动完成 (http://localhost:8501)"

.PHONY: docker-compose-down
docker-compose-down: ## 停止 Docker Compose
	@echo "$(BLUE)停止 Docker Compose...$(NC)"
	docker-compose down
	@echo "  ✓ 服务已停止"

# =============================================================================
# 工具
# =============================================================================

.PHONY: show-config
show-config: ## 显示项目配置
	@echo "$(BLUE)项目配置:$(NC)"
	@echo "  项目名称: $(PROJECT_NAME)"
	@echo "  Python 版本: $(PYTHON_VERSION)"
	@echo "  虚拟环境: $(VENV_DIR)"
	@echo "  UV: $$($(UV) --version 2>/dev/null || echo '未安装')"

.PHONY: show-deps
show-deps: ## 显示依赖列表
	@echo "$(BLUE)项目依赖:$(NC)"
	@$(UV) tree

.PHONY: update-deps
update-deps: ## 更新依赖到最新版本
	@echo "$(BLUE)更新依赖...$(NC)"
	@$(UV) sync --upgrade
	@echo "  ✓ 依赖更新完成"

# =============================================================================
# 开发工作流
# =============================================================================

.PHONY: dev-check
dev-check: ## 开发前检查 (lint + type-check + test-fast)
	@echo "$(BLUE)运行开发前检查...$(NC)"
	@$(MAKE) lint-fix
	@$(MAKE) type-check
	@$(MAKE) test-fast
	@echo ""
	@echo "$(GREEN)✓ 开发前检查通过$(NC)"

.PHONY: ci
ci: ## CI/CD 流水线 (检查 + 测试)
	@echo "$(BLUE)运行 CI/CD 流水线...$(NC)"
	@$(MAKE) check-all
	@$(MAKE) test
	@echo ""
	@echo "$(GREEN)✓ CI/CD 流水线完成$(NC)"

# =============================================================================

# 说明: 使用 make <target> 来执行特定任务
# 示例: make setup    # 初始化开发环境
#      make test      # 运行测试
#      make run       # 启动应用