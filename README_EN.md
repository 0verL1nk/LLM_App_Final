# Literature Reading Assistant v2.0

[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Quality](https://img.shields.io/badge/Code%20Quality-Ruff%20%7C%20MyPy-green.svg)](https://github.com/astral-sh/ruff)
[![Test Coverage](https://img.shields.io/badge/Test%20Coverage-67%25-orange.svg)](#testing)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg)](.github/workflows/ci.yml)

[English](README_EN.md) | [简体中文](README.md)

An AI-powered literature reading assistant tool that helps researchers and students read, understand, and analyze academic literature more efficiently. Built with modular architecture and enterprise-grade development experience.

## ✨ Key Features

### 🔐 User System
- Complete user authentication (register/login)
- Token-based secure authentication
- Support for user-customizable API keys

### 📁 File Management Center
- Multi-format support (PDF, DOC, DOCX, TXT)
- File deduplication (MD5-based)
- Secure file storage and management

### 📑 Intelligent Literature Analysis
- 🔍 **Key Text Extraction**: Automatically extract and categorize key content (Background, Purpose, Methods, Conclusions, Future Work)
- 📝 **Smart Summarization**: Generate structured literature summaries
- 💬 **Interactive Q&A**: Answer questions based on paper content
- ✏️ **Text Optimization**:
  - Text polishing and clarity enhancement
  - Smart paraphrasing and plagiarism reduction
  - Academic writing style enhancement
  - Text translation (Chinese/English)

### 🗺️ Visual Mind Mapping
- Interactive visualization based on pyecharts
- Intuitive display of literature structure and key concepts
- Hierarchical navigation and node expansion

### 🛡️ Enterprise-Grade Features
- **Modular Architecture**: Python best practices with src/ layout
- **Type Safety**: 100% type annotation coverage
- **Comprehensive Testing**: 67%+ test coverage, 100+ unit tests
- **Code Quality**: Integrated Ruff, MyPy, Bandit checks
- **CI/CD**: GitHub Actions automation pipeline
- **Complete Documentation**: Architecture docs, API reference, migration guide

## 🚀 Quick Start

### Requirements

- **Python**: 3.9+ (recommended 3.11)
- **uv**: Modern Python package manager ([Installation Guide](https://docs.astral.sh/uv/))
- **Optional**: Redis (default memory mode, configurable)

### 💡 Queue Mode Explanation

The project supports two task queue modes:

**1. Memory Mode (Default, Recommended)**
- ✅ No Redis installation required
- ✅ Zero configuration, ready to use
- ✅ Perfect for development and small to medium scale
- ⚠️ Task history lost after application restart

**2. Redis Mode (Optional)**
- ✅ Task persistence, recoverable after restart
- ✅ Multi-process/multi-instance support
- ✅ Better performance and reliability
- ⚠️ Requires Redis installation and configuration

**Enable Redis Mode**:
```bash
export USE_REDIS=true
# or create .env file with: USE_REDIS=true
```

### Recommended: Use Makefile (Easiest)

```bash
# 1. Check and install all dependencies (automatic)
make setup

# 2. Run tests
make test

# 3. Start application
make run
```

### Manual Installation

#### 1. Clone Repository

```bash
git clone <repository-url>
cd LLM_App_Final
```

#### 2. Check System Dependencies

```bash
# Check Python (requires 3.9+)
python3 --version

# Check and install uv
make check-deps
# or manually install:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 3. Setup Development Environment

```bash
# Automatic setup (recommended)
make setup

# or manual steps:
# Install dependencies
uv sync --all-extras --dev

# Install pre-commit hooks
pre-commit install

# Create necessary directories
mkdir -p uploads logs
```

#### 4. Configure API Key

**Option 1: Environment Variable**

```bash
export DASHSCOPE_API_KEY='your_api_key_here'
```

**Option 2: Through Application**
- Configure your API key in the app sidebar

#### 5. Start Application

```bash
# Using Makefile (recommended)
make run

# or directly with uv
uv run streamlit run 文件中心.py
```

#### 6. Access Application

Open browser and visit `http://localhost:8501`

---

### 🛠️ Makefile Commands Reference

```bash
# Development Environment
make setup              # Initialize development environment (one-time)
make check-deps         # Check system dependencies (Python, uv, Redis)
make check-redis        # Check Redis service status
make show-config-redis  # Show Redis configuration

# Code Quality
make lint               # Code checking (Ruff)
make lint-fix           # Auto-fix code issues
make type-check         # Type checking (MyPy)
make security-check     # Security checking (Bandit)
make check-all          # Run all quality checks

# Testing
make test               # Run all tests
make test-fast          # Quick tests (skip integration)
make test-unit          # Unit tests only
make test-integration   # Integration tests only

# Run
make run                # Start application
make run-dev            # Development mode (auto-reload)

# Docker
make docker-build       # Build Docker image
make docker-compose-up  # Start with Docker Compose

# View all commands
make help
```

## 📁 Project Structure

```
LLM_App_Final/
├── src/                          # ✅ Source code (modular architecture)
│   └── llm_app/
│       ├── core/                 # Core business logic
│       │   ├── auth.py          # User authentication
│       │   ├── database.py      # Database operations
│       │   ├── file_handler.py  # File processing
│       │   ├── text_processor.py # Text analysis
│       │   ├── optimizer.py     # Text optimization
│       │   └── logger.py        # Logging
│       ├── api/                 # API layer
│       │   └── llm_client.py    # LLM client
│       ├── queue/               # Async task queue
│       │   ├── task_queue.py    # RQ management
│       │   └── workers.py       # Background tasks
│       └── ui/                  # UI utilities
│           └── page_helpers.py  # Streamlit helpers
│
├── tests/                        # ✅ Test suite
│   ├── unit/                    # Unit tests (100+)
│   ├── integration/             # Integration tests
│   └── conftest.py              # pytest configuration
│
├── docs/                        # ✅ Complete documentation
│   ├── architecture.md          # Architecture documentation
│   ├── api_reference.md         # API reference
│   ├── migration_guide.md       # Migration guide
│   └── refactor_summary.md      # Refactoring summary
│
├── pages/                        # Streamlit pages
├── 文件中心.py                    # Main application entry
├── Makefile                      # ✅ Automated commands
├── pyproject.toml                # ✅ Project configuration
├── .pre-commit-config.yaml      # ✅ Pre-commit configuration
├── .github/workflows/           # ✅ CI/CD
└── REFACTOR_COMPLETE.md          # Refactoring completion report
```

## 📸 Feature Showcase

### Login Interface
![Login Interface](images/登录.png)

### File Center
![File Center](images/%E6%96%87%E4%BB%B6%E4%B8%AD%E5%BF%83.png)

### Text Extraction
![Text Extraction](images/%E5%8E%9F%E6%96%87%E6%8F%90%E5%8F%96.png)

### Text Optimization
![Text Optimization Example](images/文段优化1.png)
![Text Optimization Example](images/文段优化3.png)
![Text Optimization Result](images/文段优化4.png)

### Paper Q&A
![Paper Q&A](images/论文问答.png)
![Q&A Example](images/论文问答2.png)

### Mind Map
![Mind Map](images/思维导图.png)

## 🧪 Testing

### Run Tests

```bash
# Run all tests (with coverage)
make test

# Unit tests only (fast)
make test-fast

# View coverage report
open htmlcov/index.html
```

### Test Coverage

- **Target Coverage**: 70-80%
- **Current Coverage**: 67%+ (core modules)
- **Test Count**: 100+ unit tests + integration tests
- **Module Coverage**:
  - ✅ DatabaseManager: 95%
  - ✅ AuthManager: 95%
  - ✅ FileHandler: 94%
  - ✅ LLMClient: 95%
  - ✅ TextProcessor: 71%
  - ✅ TextOptimizer: 83%

### Test Report

See detailed test report: `TEST_REPORT.md`

## 🛠️ Tech Stack

### Core Frameworks
- **Frontend**: Streamlit 1.40+
- **Backend**: Python 3.9+
- **Database**: SQLite (users, files, tasks, contents)
- **Task Queue**: Redis + RQ (async processing)

### LLM Integration
- **API**: DashScope (Alibaba Cloud), OpenAI-compatible interface
- **Framework**: LangChain 0.3.x
- **Models**: Qwen, GPT series, etc.

### Visualization
- **Charts**: pyecharts 2.0+, streamlit-echarts
- **Chart Types**: Tree, Bar, Line, etc.

### Document Processing
- **Extraction**: textract, tesseract-ocr, antiword
- **Formats**: PDF, DOC, DOCX, TXT

### Development Tools
- **Package Management**: uv (recommended), pip
- **Code Quality**: Ruff, MyPy, Bandit
- **Testing**: pytest, coverage
- **Pre-commit**: pre-commit
- **CI/CD**: GitHub Actions
- **Automation**: Makefile

## 🏗️ Architecture Design

### Design Principles

1. **Modularity**: Single responsibility, clear boundaries
2. **Testability**: Dependency injection, low coupling
3. **Type Safety**: 100% type annotations
4. **Maintainability**: Clear documentation and code structure
5. **Extensibility**: Easy to add new features

### Core Modules

| Module | Responsibility | Coverage |
|--------|---------------|----------|
| **DatabaseManager** | Database CRUD operations | 95% |
| **AuthManager** | User authentication | 95% |
| **FileHandler** | File upload and processing | 94% |
| **LLMClient** | LLM API integration | 95% |
| **TextProcessor** | Text analysis | 71% |
| **TextOptimizer** | Text optimization | 83% |

### Data Flow

```
User Upload → FileHandler → SQLite
    ↓
Text Extraction → TextProcessor → LLM API
    ↓
Result Storage → Database → Frontend Display
```

## 🚀 Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Set API Key
export DASHSCOPE_API_KEY='your_api_key_here'

# Start all services
make docker-compose-up

# Stop services
make docker-compose-down
```

### Manual Build

```bash
# Build image
make docker-build

# Run container
make docker-run
```

Visit `http://localhost:8501`

## 📊 Development Workflow

### Pre-commit Checks

```bash
# Auto-fix + check + test
make dev-check

# or step by step
make lint-fix
make type-check
make test-fast
```

### CI/CD Pipeline

GitHub Actions automatically runs:
1. Code quality checks (Ruff, MyPy, Bandit)
2. Multi-platform testing (Ubuntu/Windows/macOS)
3. Multi-Python version testing (3.9/3.10/3.11)
4. Test coverage reports
5. Docker image builds

### Version Management

```bash
# Update dependencies
make update-deps

# View dependency tree
make show-deps

# View configuration
make show-config
```

## 🗺️ Roadmap

### Completed ✅
- ✅ User authentication system
- ✅ Modular architecture refactoring (v2.0)
- ✅ Comprehensive test suite (67%+ coverage)
- ✅ Code quality toolchain
- ✅ CI/CD pipeline
- ✅ Complete documentation system
- ✅ Dockerfile & Docker Compose

### In Progress 🚧
- [ ] Fix 16 failing tests (target 70%+ coverage)
- [ ] Add queue module tests (requires Redis)
- [ ] Optimize code quality (fix Ruff warnings)

### Planned 📋
- [ ] Migrate to PostgreSQL
- [ ] Add WebSocket real-time updates
- [ ] Microservices splitting
- [ ] Add end-to-end tests (Playwright)
- [ ] Performance benchmarking

## 🤝 Contributing

We welcome all forms of contributions!

### Contribution Process

1. **Fork** the project
2. **Create** feature branch: `git checkout -b feature/AmazingFeature`
3. **Commit** changes: `git commit -m 'Add some AmazingFeature'`
4. **Push** to branch: `git push origin feature/AmazingFeature`
5. **Open** a Pull Request

### Development Standards

- Follow [PEP 8](https://pep8.org/) code style
- Add type annotations
- Write unit tests
- Run `make check-all` to pass all checks
- Update relevant documentation

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation update
- `refactor`: Code refactoring
- `test`: Test-related
- `chore`: Build/tooling-related

## 📝 Notes

### Environment Configuration

- **Python Version**: Strongly recommend Python 3.11+
- **uv**: Recommended over pip for faster installation and better dependency resolution
- **Redis**: Optional, for async task queue functionality

### API Key Configuration

- Requires a valid DashScope API key
- Configure via app sidebar or environment variable
- See [DashScope Documentation](https://help.aliyun.com/zh/model-studio/getting-started/first-api-call-to-qwen)

### Performance Tips

- Large file processing may take time (recommended < 100MB)
- Redis significantly improves async task performance
- Regularly clean `uploads/` and `database.sqlite`

## ❓ FAQ

### Q: How to update dependencies?
A: `make update-deps` or `uv sync --upgrade`

### Q: Tests failing?
A: Check `TEST_REPORT.md` for detailed error info, or run `make test-unit` to locate issues

### Q: How to add new LLM provider?
A: Modify `src/llm_app/api/llm_client.py`, following existing interface patterns

### Q: Is Redis required?
A: No, Redis is only for async tasks. Sync functions work without Redis

### Q: How to view API docs?
A: `open docs/api_reference.md` or check online documentation

## 📚 Related Documentation

- [Architecture Documentation](docs/architecture.md) - Detailed system architecture
- [API Reference](docs/api_reference.md) - Complete API documentation
- [Migration Guide](docs/migration_guide.md) - v1.x to v2.0 migration
- [Refactoring Summary](docs/refactor_summary.md) - Detailed refactoring report
- [Test Report](TEST_REPORT.md) - Test results and coverage
- [Makefile Help](Makefile) - Automated command reference

## 📄 License

This project is licensed under the [MIT License](LICENSE)

## 👥 Authors

- **0verL1nk** - *Initial Development* - [GitHub](https://github.com/0verL1nk)

## 🙏 Acknowledgments

- [Streamlit](https://streamlit.io/) - Excellent data app framework
- [LangChain](https://www.langchain.com/) - LLM application framework
- [DashScope](https://www.alibabacloud.com/product/dashscope) - Alibaba Cloud Tongyi Qianwen
- [uv](https://docs.astral.sh/uv/) - Ultra-fast Python package manager
- [Ruff](https://github.com/astral-sh/ruff) - Ultra-fast Python linter

## ⭐ Support

If you find this project helpful, please give us a ⭐!

---

**Note**: This project is AI-generated and for learning/research purposes only.