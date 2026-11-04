"""Build a private local plugin ZIP from current server source, excluding caches."""
from pathlib import Path
import json
import zipfile


def main():
    project = Path(__file__).resolve().parent.parent
    version = json.loads((project / "packaging" / "chatgpt" / "plugin.json").read_text(encoding="utf-8"))["version"]
    output = project / "dist" / f"zmcp-chatgpt-{version}.zip"
    output.parent.mkdir(exist_ok=True)
    files = []
    template = project / "packaging" / "chatgpt"
    for path in sorted(template.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            files.append((path, path.relative_to(template)))
    for path in sorted((project / "src" / "zmcp").rglob("*")):
        if path.is_file() and path.suffix in {".py", ".json"} and "__pycache__" not in path.parts:
            files.append((path, Path("server/src") / path.relative_to(project / "src")))
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source, target in files:
            archive.write(source, str(target))
    print(output)


if __name__ == "__main__":
    main()
