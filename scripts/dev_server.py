"""Run the API and Vite development servers with shared lifecycle."""

import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    pnpm = "pnpm.cmd" if sys.platform == "win32" else "pnpm"
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"],
            cwd=root,
        ),
        subprocess.Popen([pnpm, "run", "dev"], cwd=root / "web"),
    ]
    print("PaperSage development servers are running:")
    print("  API:  http://127.0.0.1:8000")
    print("  Web:  http://127.0.0.1:5173")
    print("Press Ctrl+C to stop both servers.")
    exit_code = 0
    try:
        while True:
            finished = next((process for process in processes if process.poll() is not None), None)
            if finished is not None:
                exit_code = finished.returncode or 0
                if exit_code:
                    print(f"A development server exited with code {exit_code}.", file=sys.stderr)
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping PaperSage development servers...")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
