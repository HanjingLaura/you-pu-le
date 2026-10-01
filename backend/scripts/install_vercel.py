"""Install cloud dependencies without shipping music21's example-score corpus."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

SCORE_ASSETS = {".abc", ".mxl", ".krn", ".xml", ".rntxt", ".musicxml", ".mus", ".musx", ".png", ".psd", ".gz"}


def prune_example_scores(corpus: Path) -> int:
    root = corpus.resolve(strict=True)
    removed = 0
    for resource in root.rglob("*"):
        if resource.is_symlink() or not resource.is_file() or resource.suffix.lower() not in SCORE_ASSETS:
            continue
        # Only delete packaged data beneath the explicitly selected corpus.
        # Python modules remain available to music21's normal imports.
        if not resource.resolve().is_relative_to(root):
            raise RuntimeError("Corpus resource resolved outside the package directory")
        removed += resource.stat().st_size
        resource.unlink()
    return removed


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(project / "requirements-vercel.txt")],
        check=True,
    )
    spec = importlib.util.find_spec("music21")
    if spec is None or spec.origin is None:
        raise RuntimeError("music21 was not installed")
    package = Path(spec.origin).resolve().parent
    removed = prune_example_scores(package / "corpus")
    print(f"Excluded {removed / 1024 ** 2:.1f} MiB of bundled example scores")


if __name__ == "__main__":
    main()
