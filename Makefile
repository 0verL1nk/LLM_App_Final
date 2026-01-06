# =============================================================================
# LLM App Makefile
# =============================================================================

# Variables
UV := uv
PYTHON := python3

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
NC := \033[0m

.PHONY: help
help: ## Display this help message
	@echo "$(BLUE)LLM App Makefile$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'

# =============================================================================
# Development Setup
# =============================================================================

.PHONY: setup
setup: ## Initialize development environment
	@echo "$(BLUE)Setting up backend...$(NC)"
	@$(UV) sync
	@echo "$(BLUE)Setting up frontend...$(NC)"
	@cd frontend && pnpm install
	@echo "$(GREEN)Setup complete!$(NC)"

# =============================================================================
# Running
# =============================================================================

.PHONY: dev-backend
dev-backend: ## Run backend in development mode
	@echo "$(BLUE)Starting backend...$(NC)"
	@PYTHONPATH=src $(UV) run uvicorn llm_app.main:app --reload --port 8501

.PHONY: dev-frontend
dev-frontend: ## Run frontend in development mode
	@echo "$(BLUE)Starting frontend...$(NC)"
	@cd frontend && npm run dev

.PHONY: dev
dev: ## Explain how to run development server
	@echo "$(BLUE)To run the development environment:$(NC)"
	@echo "1. Open one terminal and run: $(GREEN)make dev-backend$(NC)"
	@echo "2. Open another terminal and run: $(GREEN)make dev-frontend$(NC)"
	@echo "3. Access the app at http://localhost:5173"

.PHONY: pre-install
pre-install:
	@mkdir -p src/llm_app/static
	@touch src/llm_app/static/.gitkeep

.PHONY: install
install: pre-install ## Install backend dependencies
	@echo "$(BLUE)Installing backend dependencies...$(NC)"
	@$(UV) sync

.PHONY: run
run: install setup-frontend ## One-click start: Install all deps and run dev server (Backend + Frontend)
	@echo "$(BLUE)Starting development server (Backend + Frontend)...$(NC)"
	@cd frontend && pnpm dev

.PHONY: setup-frontend
setup-frontend: ## Install frontend dependencies
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	@cd frontend && pnpm install


# =============================================================================
# Building
# =============================================================================

.PHONY: build-frontend
build-frontend: ## Build frontend assets
	@echo "$(BLUE)Building frontend...$(NC)"
	@cd frontend && npm run build

.PHONY: build
build: build-frontend ## Build python package (includes frontend)
	@echo "$(BLUE)Building package...$(NC)"
	@$(UV) run python -m build

# =============================================================================
# Quality & Testing
# =============================================================================

.PHONY: lint
lint: ## Run linting
	@$(UV) run ruff check src/

.PHONY: format
format: ## Format code
	@$(UV) run ruff format src/

.PHONY: test
test: ## Run tests
	@$(UV) run pytest