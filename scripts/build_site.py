"""Publish only explicitly allowed static assets and validated archive data."""
import argparse
import shutil
from pathlib import Path

from archive import ROOT, indexes, load


def build(root=ROOT, destination=None):
    root = Path(root).resolve()
    destination = Path(destination or root / "dist").resolve()
    index, papers = indexes(root)
    if index != load(root / "data/index.json") or papers != load(root / "data/papers.json"):
        raise ValueError("Stale index; rebuild metadata before publishing")
    # Only clear our conventional generated output, never an arbitrary user directory.
    if destination.exists():
        if destination != root / "dist":
            raise ValueError("Refusing to replace a nonstandard output directory")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for path in (root / "site").iterdir():
        if path.is_file() and path.suffix in (".html", ".css", ".mjs"):
            shutil.copy2(path, destination / path.name)
    for name in ("archive", "data", "history"):
        source = root / name
        for file in sorted(source.rglob("*.json")) if source.exists() else []:
            target = destination / file.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    # Legacy artifacts are private backup material until explicitly reviewed and imported.
    (destination / ".nojekyll").touch()
    if not (destination / "index.html").exists():
        raise ValueError("Missing website entry point")
    print(f"Static site built: {destination}")
    return destination


if __name__ == "__main__":
    build()
