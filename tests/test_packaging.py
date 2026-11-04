"""Isolated installer update check; never touches the real user profile."""
import importlib.util
import json
import sys
from pathlib import Path


def test_existing_registered_plugin_is_overwritten(tmp_path, monkeypatch):
    script = Path(__file__).parent.parent / "packaging" / "chatgpt" / "install.py"
    monkeypatch.syspath_prepend(str(script.parent))
    spec = importlib.util.spec_from_file_location("zmcp_installer_test", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(module, "runtime_python", lambda: Path(sys.executable))
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda args, **kwargs: calls.append(args))
    destination = tmp_path / ".codex" / "plugins" / "zmcp"
    destination.mkdir(parents=True)
    (destination / "launch.py").write_text("old loader")
    marketplace = tmp_path / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True)
    other = {"name": "other", "source": {"path": "./other"}}
    marketplace.write_text(json.dumps({"name": "personal-local", "plugins": [other,
        {"name": "zmcp", "source": {"path": "./.codex/plugins/zmcp"}}]}))
    module.main()
    assert (destination / "launch.py").read_text() != "old loader"
    updated = json.loads(marketplace.read_text())
    assert other in updated["plugins"]
    assert sum(p["name"] == "zmcp" for p in updated["plugins"]) == 1
    assert calls and calls[0][1:4] == ["-m", "pip", "install"]
