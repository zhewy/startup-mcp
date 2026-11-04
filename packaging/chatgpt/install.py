"""Prepare dependencies and register this folder in the personal marketplace."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import venv

from launch import runtime_python


def main():
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 or newer is required.")
    root = Path(__file__).resolve().parent
    destination = Path.home() / ".codex" / "plugins" / "zmcp"
    source_path = "./.codex/plugins/zmcp"
    marketplace = Path.home() / ".agents" / "plugins" / "marketplace.json"
    # Validate existing configuration before installing or changing anything.
    data = json.loads(marketplace.read_text(encoding="utf-8")) if marketplace.exists() else {"name": "personal-local", "interface": {"displayName": "Personal local plugins"}, "plugins": []}
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        raise SystemExit("Existing marketplace has an unsupported format; left unchanged.")
    matches = [p for p in data["plugins"] if p.get("name") == "zmcp"]
    if matches and any(p.get("source", {}).get("path") not in (str(root), str(destination), source_path) for p in matches):
        raise SystemExit("A different zmcp is already registered; left unchanged.")
    interpreter = runtime_python()
    if not interpreter.exists():
        venv.EnvBuilder(with_pip=True).create(interpreter.parent.parent)
    subprocess.run([str(interpreter), "-m", "pip", "install", "mcp==2.3.0"], check=True)
    if root != destination:
        if destination.exists() and not matches:
            raise SystemExit("An unregistered zmcp folder already exists; left unchanged.")
        shutil.copytree(root, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".venv", ".git"))
    entry = {
            "name": "zmcp",
            "source": {"source": "local", "path": source_path},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            "category": "Productivity",
        }
    if matches:
        matches[0]["source"] = entry["source"]
    else:
        data["plugins"].append(entry)
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    if marketplace.exists():
        shutil.copy2(marketplace, marketplace.with_suffix(".json.zmcp.bak"))
    temporary = marketplace.with_suffix(".json.zmcp.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(marketplace)
    print(f"Plugin copied to {destination}")
    print(f"Registered in {marketplace}")
    print(f"Restart ChatGPT desktop, open Plugins, select marketplace {data.get('name', 'personal-local')!r}, and install zmcp.")


if __name__ == "__main__":
    main()
