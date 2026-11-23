"""Synchronise le témoin courant de la seed 5 dans la CI et les documents."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI_REL = ".github/workflows/ci.yml"
FILES = (
    CI_REL,
    "CHANGELOG.md",
    "README.md",
    "README_EN.md",
    "atelier/roadmap-redressement.md",
    "docs/DEVIANCES.md",
    "docs/developpement.md",
    "docs/etat-code.md",
    "docs/graphe-interactif.md",
    "docs/release.md",
    "docs/witness.md",
    "notes/v0.0.2.md",
)

HASH_RE = re.compile(r"[0-9a-f]{32}")
EXPECT_RE = re.compile(r"randputf witness --seed 5 --expect ([0-9a-f]{32})")


def current_hash(root: Path = ROOT) -> str:
    text = (root / CI_REL).read_text(encoding="utf-8")
    match = EXPECT_RE.search(text)
    if match is None:
        raise ValueError(f"témoin introuvable dans {CI_REL}")
    return match.group(1)


def sync_text(text: str, old: str, new: str) -> str:
    return text.replace(old, new)


def sync_files(root: Path, old: str, new: str) -> list[str]:
    changed: list[str] = []
    for rel in FILES:
        path = root / rel
        text = path.read_text(encoding="utf-8")
        updated = sync_text(text, old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(rel)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hash", help="nouveau témoin md5 sur 32 caractères")
    args = parser.parse_args()
    if HASH_RE.fullmatch(args.hash) is None:
        parser.error("le témoin doit être un md5 hexadécimal de 32 caractères")
    old = current_hash()
    changed = sync_files(ROOT, old, args.hash)
    print(f"témoin {old} -> {args.hash}")
    print(f"fichiers mis à jour : {len(changed)}")
    for rel in changed:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
