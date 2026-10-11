"""Validate committed publication assets without exposing possible secret values."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
                    r"github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b")
FORBIDDEN = {".env", "node_modules", ".venv", ".lightrag-venv", "__pycache__",
             ".coverage", ".pytest_cache", "dist"}


def main() -> None:
    manifest = json.loads((ROOT / "PUBLICATION_MANIFEST.json").read_text(encoding="utf-8"))
    errors = []
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        path = ROOT / relative
        if (any(part in FORBIDDEN for part in relative.parts)
                or relative.parts[:2] == ("minibkn", "data")
                or path.suffix in {".db", ".sqlite", ".pyc"}):
            errors.append(f"Forbidden asset: {relative}")
        if not path.is_file():
            errors.append(f"Missing asset: {relative}")
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            errors.append(f"Hash differs: {relative}")
        text = raw.decode("utf-8")
        if SECRET.search(text):
            errors.append(f"Potential secret (value hidden): {relative}")
        if re.search(r"[CD]:[/\\](?:Users|baidu|anaconda|cbl_file)", text, re.I):
            errors.append(f"Author-machine path: {relative}")
        if relative.suffix in {".json", ".jsonl"}:
            try:
                if relative.suffix == ".json":
                    json.loads(text)
                else:
                    for line in text.splitlines():
                        if line.strip():
                            json.loads(line)
            except ValueError:
                errors.append(f"Invalid JSON: {relative}")
    # Check current guides; archive documents can reference stage-specific artifacts.
    for guide in [ROOT / "README.md", ROOT / "README.zh.md", *(ROOT / "docs").glob("*.md")]:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", guide.read_text(encoding="utf-8")):
            if "://" not in target and not target.startswith("#"):
                resolved = (guide.parent / target.split("#")[0]).resolve()
                if not resolved.exists():
                    errors.append(f"Missing guide link: {guide.name} -> {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {len(manifest['files'])} manifest assets; hashes, common-secret patterns, "
          "local-path checks, JSON validity and current guide links.")


if __name__ == "__main__":
    main()
