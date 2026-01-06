import os
import subprocess
import shutil
from pathlib import Path
import sys

def build():
    # Adjusted root_dir since script is now in dev_scripts/
    root_dir = Path(__file__).parent.parent.absolute()
    frontend_dir = root_dir / "frontend"
    
    print(f"Project root: {root_dir}")
    
    # 1. Build Frontend
    print("\n--- Building Frontend ---")
    if not frontend_dir.exists():
        print("Error: frontend directory not found!")
        sys.exit(1)
        
    # Check for npm/pnpm/yarn
    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        print("Error: npm not found in PATH")
        sys.exit(1)
        
    # Install dependencies if needed
    if not (frontend_dir / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run([npm_cmd, "install"], cwd=frontend_dir, check=True)
    
    # Build
    print("Compiling frontend assets...")
    subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir, check=True)
    
    # Verify output
    static_dir = root_dir / "src" / "llm_app" / "static"
    if not static_dir.exists() or not list(static_dir.iterdir()):
        print(f"Warning: Static directory {static_dir} seems empty or missing after build.")
    else:
        print(f"Frontend built successfully to {static_dir}")

    # 2. Build Python Package
    print("\n--- Building Python Package ---")
    
    # Install build tool if missing (optional check)
    try:
        import build
    except ImportError:
        print("Installing 'build' tool...")
        subprocess.run([sys.executable, "-m", "pip", "install", "build"], check=True)

    # Clean previous builds
    dist_dir = root_dir / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
        
    # Build
    subprocess.run([sys.executable, "-m", "build"], cwd=root_dir, check=True)
    
    print("\n--- Build Complete ---")
    print(f"Artifacts available in: {dist_dir}")
    print("You can upload to PyPI using: twine upload dist/*")

if __name__ == "__main__":
    build()
