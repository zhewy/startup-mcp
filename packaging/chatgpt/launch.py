"""Launch with the separately installed runtime; keep stdout for MCP only."""
import os
from pathlib import Path
import subprocess
import sys


def runtime_python():
    root = Path.home() / ".zmcp" / "runtime-0.1.0"
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


if __name__ == "__main__":
    interpreter = Path(os.environ.get("ZMCP_PYTHON", str(runtime_python())))
    if not interpreter.is_file():
        print("zmcp: run python install.py from the extracted plugin first.", file=sys.stderr)
        sys.exit(1)
    source = Path(__file__).resolve().parent / "server" / "src"
    # Set sys.path in the child instead of replacing the user's PYTHONPATH.
    code = "import runpy, sys; sys.path.insert(0, sys.argv[1]); runpy.run_module('zmcp.server', run_name='__main__')"
    try:
        sys.exit(subprocess.call([str(interpreter), "-c", code, str(source)]))
    except KeyboardInterrupt:
        sys.exit(130)
