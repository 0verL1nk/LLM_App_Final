"""Guard the API startup import budget.

Importing api.main used to pull lancedb, pyarrow, fastembed, onnxruntime and
langchain_community into every desktop launch (seconds of cold-start). Those
stacks are deferred to first use; this test blocks them so a new eager import
fails loudly instead of silently re-inflating startup.
"""

import subprocess
import sys

BLOCKED_PREFIXES = (
    "lancedb",
    "pyarrow",
    "fastembed",
    "onnxruntime",
    "langchain_community",
)

_PROBE = """
import sys

blocked = {prefixes!r}

class _StartupBudgetGuard:
    def find_module(self, name, path=None):
        if name.split(".")[0] in blocked:
            raise ImportError(
                f"api.main startup must not import {{name}}; defer it to first use"
            )
        return None

sys.meta_path.insert(0, _StartupBudgetGuard())
import api.main
print("STARTUP_IMPORTS_OK")
"""


def test_api_startup_does_not_import_rag_and_embedding_stacks() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(prefixes=BLOCKED_PREFIXES)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "STARTUP_IMPORTS_OK" in result.stdout
