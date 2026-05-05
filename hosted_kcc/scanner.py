from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".cbz",
    ".zip",
    ".cbr",
    ".rar",
    ".cb7",
    ".7z",
    ".pdf",
}


def discover_files(input_roots: list[Path]) -> list[Path]:
    discovered: list[Path] = []
    for root in input_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                discovered.append(path)
    return sorted(discovered, key=lambda item: str(item).lower())
