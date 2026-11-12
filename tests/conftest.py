"""Helpers partagés entre les fichiers de tests."""

import json
from pathlib import Path

DUMP_PATH = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"


def dump_has_fuel_categories() -> bool:
    """True si le dump exporte ``fuel_categories`` sur les items (2.1.20).

    Sans ce champ, les combustibles n'ont pas de catégorie connue : le
    réacteur nucléaire n'est pas routable en recette fixe. Les tests qui le
    couvrent sont sautés en attendant un ré-export avec l'exporter corrigé."""
    dump = json.loads(DUMP_PATH.read_text(encoding="utf-8"))
    return any(
        isinstance(entry, dict) and entry.get("fuel_categories")
        for entry in (dump.get("items") or {}).values()
    )
