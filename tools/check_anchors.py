"""Vérifie que les ancres des liens Markdown existent.

Calcule les ancres GitHub de chaque titre, puis compare les liens internes
``fichier.md#ancre`` et ``#ancre`` aux ancres réellement présentes. Les liens
externes et le contenu des blocs de code sont ignorés. Le script sort en erreur
dès qu'une cible ou une ancre manque, avec le fichier et la ligne fautifs.

Usage :
    python tools/check_anchors.py [chemins...]

Sans argument, tous les fichiers Markdown du dépôt sont vérifiés, sauf les
dossiers générés ou hors versionnement.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "node_modules",
    "output",
}

FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
HTML_ANCHOR_RE = re.compile(
    r"<a\s+[^>]*(?:name|id)=[\"']([^\"']+)[\"']", re.IGNORECASE
)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def github_slug(text: str, seen: dict[str, int]) -> str:
    """Transforme un titre en ancre GitHub, doublons compris."""
    code_spans: list[str] = []

    def protect_code(match: re.Match[str]) -> str:
        code_spans.append(match.group(0)[1:-1])
        return f"\x00{len(code_spans) - 1}\x00"

    text = html.unescape(text)
    text = IMAGE_RE.sub(r"\1", text)
    text = MD_LINK_RE.sub(r"\1", text)
    text = INLINE_CODE_RE.sub(protect_code, text)
    text = HTML_TAG_RE.sub("", text)
    text = re.sub(
        r"\x00(\d+)\x00",
        lambda match: code_spans[int(match.group(1))],
        text,
    )
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s", "-", text)
    base = text or "section"
    count = seen.get(base, 0)
    seen[base] = count + 1
    return base if count == 0 else f"{base}-{count}"


def anchors_for(path: Path) -> set[str]:
    """Retourne les ancres d'un fichier Markdown."""
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    in_fence = False
    fence_marker = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            anchors.add(github_slug(heading.group(2), seen))
        for match in HTML_ANCHOR_RE.finditer(line):
            anchors.add(match.group(1))
    return anchors


def iter_links(path: Path):
    """Produit (ligne, cible) pour chaque lien inline hors blocs de code."""
    in_fence = False
    fence_marker = ""
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)[0]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        line = INLINE_CODE_RE.sub("", line)
        for match in LINK_RE.finditer(line):
            yield lineno, match.group(1).strip()


def resolve_target(doc: Path, target: str) -> tuple[Path | None, str]:
    """Sépare fichier et ancre, puis résout le chemin relatif au document."""
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split(maxsplit=1)[0]
    if not target or target.startswith(
        ("http://", "https://", "mailto:", "tel:", "data:", "//")
    ):
        return None, ""
    path_part, separator, anchor = target.partition("#")
    if not separator or not anchor:
        return None, ""
    path_part = unquote(path_part.split("?", 1)[0])
    anchor = unquote(anchor)
    if not path_part:
        return doc, anchor
    candidate = Path(path_part)
    if candidate.is_absolute():
        resolved = (ROOT / candidate.as_posix().lstrip("/")).resolve()
    else:
        resolved = (doc.parent / candidate).resolve()
    if not resolved.exists():
        root_candidate = (ROOT / candidate).resolve()
        if root_candidate.exists():
            resolved = root_candidate
    return resolved, anchor


def display_path(path: Path) -> str:
    """Affiche un chemin relativement au dépôt quand c'est possible."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def markdown_files(paths: list[str]) -> list[Path]:
    """Liste les fichiers Markdown à vérifier, sans doublons."""
    roots = [Path(path) for path in paths] if paths else [ROOT]
    files: set[Path] = set()
    for path in roots:
        candidate = path if path.is_absolute() else ROOT / path
        if candidate.is_dir():
            for found in candidate.rglob("*.md"):
                relative = found.relative_to(ROOT) if found.is_relative_to(ROOT) else found
                if not any(part in EXCLUDED_DIRS for part in relative.parts):
                    files.add(found.resolve())
        elif candidate.suffix.lower() == ".md":
            files.add(candidate.resolve())
    return sorted(files)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI du vérificateur d'ancres."""
    parser = argparse.ArgumentParser(
        description="Vérifie les ancres des liens Markdown."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="fichiers ou dossiers à vérifier (défaut : tout le dépôt)",
    )
    args = parser.parse_args(argv)

    files = markdown_files(args.paths)
    cache: dict[Path, set[str]] = {}
    errors: list[str] = []

    for doc in files:
        try:
            anchors = anchors_for(doc)
        except OSError as exc:
            errors.append(f"{doc}: lecture impossible ({exc})")
            continue
        cache[doc] = anchors
        for lineno, target in iter_links(doc):
            resolved, anchor = resolve_target(doc, target)
            if resolved is None:
                continue
            if resolved.suffix.lower() != ".md":
                continue
            if not resolved.exists():
                errors.append(
                    f"{display_path(doc)}:{lineno}: fichier cible introuvable "
                    f"({target})"
                )
                continue
            if resolved not in cache:
                try:
                    cache[resolved] = anchors_for(resolved)
                except OSError as exc:
                    errors.append(f"{resolved}: lecture impossible ({exc})")
                    continue
            if anchor not in cache[resolved]:
                errors.append(
                    f"{display_path(doc)}:{lineno}: ancre introuvable "
                    f"({target})"
                )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(
            f"{len(errors)} erreur(s) d'ancre sur {len(files)} fichier(s) Markdown",
            file=sys.stderr,
        )
        return 1

    print(f"Ancres Markdown OK ({len(files)} fichiers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
