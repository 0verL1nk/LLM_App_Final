"""PyInstaller runtime hook: expose bundled NVIDIA CUDA DLLs to onnxruntime.

The nvidia-*-cu13 wheels place their DLLs under nvidia/<name>/bin/, which is
not on the Windows loader search path of onnxruntime_providers_cuda.dll.
"""

import os
import sys

_base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
_nvidia_root = os.path.join(_base, "nvidia")
if os.path.isdir(_nvidia_root):
    for _entry in os.listdir(_nvidia_root):
        _bin_dir = os.path.join(_nvidia_root, _entry, "bin")
        if os.path.isdir(_bin_dir):
            os.environ["PATH"] = _bin_dir + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(_bin_dir)
            except Exception:
                pass
