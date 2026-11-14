"""Rebuild the automation source manifest with portable LF-normalized hashes."""
import hashlib
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "integrations/long-v2"
IGNORED = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "data", "logs", "test-videos"}


def package_files(root=ROOT):
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or any(part in IGNORED for part in relative.parts):
            continue
        if path.name == "SOURCE_MANIFEST.json" or (path.name.startswith(".env") and path.name != ".env.example"):
            continue
        if path.suffix in {".py", ".json", ".md", ".yml", ".ps1", ".conf"} or path.name in {
            "Dockerfile", "requirements.txt", ".dockerignore", ".env.example"
        }:
            yield relative.as_posix(), path


def digest(path):
    return hashlib.sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def main():
    manifest = ROOT / "SOURCE_MANIFEST.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data.update(packaged_on=date.today().isoformat(), hash_format="sha256-utf8-lf",
                files_sha256={name: digest(path) for name, path in package_files()})
    manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Updated {len(data['files_sha256'])} packaged source hashes.")


if __name__ == "__main__":
    main()
