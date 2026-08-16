"""PyInstaller runtime hook: expose bundled NVIDIA CUDA DLLs to onnxruntime.

The nvidia-*-cu13 wheels scatter their DLLs across several trees below
site-packages/nvidia (cu13/bin/x86_64, cudnn/bin, ...), none of which are on
the Windows loader search path of onnxruntime_providers_cuda.dll. The build
gathers every DLL into one directory; this hook puts it on the loader path.
"""

import os
import sys

_base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
_cuda_dll_dir = os.path.join(_base, "nvidia", "cu13", "bin", "x86_64")
if os.path.isdir(_cuda_dll_dir):
    os.environ["PATH"] = _cuda_dll_dir + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(_cuda_dll_dir)
    except Exception:
        pass
