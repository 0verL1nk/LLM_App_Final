@echo off
setlocal

REM ============================================================================
REM LLM App Windows Launcher
REM ============================================================================

echo [INFO] Checking prerequisites...

REM Check for uv
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'uv' is not installed. Please install it first: https://docs.astral.sh/uv/
    exit /b 1
)

REM Check for pnpm
where pnpm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 'pnpm' is not installed. Please install it via npm: npm install -g pnpm
    exit /b 1
)

echo.
echo [INFO] Setting up backend...
call uv sync
if %errorlevel% neq 0 (
    echo [ERROR] Backend setup failed.
    exit /b 1
)

echo.
echo [INFO] Setting up frontend...
cd frontend
call pnpm install
if %errorlevel% neq 0 (
    echo [ERROR] Frontend setup failed.
    cd ..
    exit /b 1
)

echo.
echo [INFO] Starting development server (Backend + Frontend)...
call pnpm dev

cd ..
endlocal
