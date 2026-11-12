"""Le navigateur HTML du dump (« notre Factoriopedia ») : rendu complet du
dump réel, replis propres sur un dump incomplet, structuration pipeline
seule (fluide pompé résolu, packs de science par les faits)."""

from __future__ import annotations

import json
from pathlib import Path

from tool.exporters.dump_html import write_dump_html

DATA = Path(__file__).resolve().parents[1] / "data" / "vanilla_dump.json"


def test_navigateur_du_vrai_dump(tmp_path: Path) -> None:
    dump = json.loads(DATA.read_text(encoding="utf-8"))
    out = tmp_path / "dump.html"
    path = write_dump_html(dump, out)
    html = path.read_text(encoding="utf-8")
    # En-tête et sections.
    assert "Dump Factorio" in html and "navigateur A→Z" in html
    for section in ("Inventaire A→Z", "Tuiles", "Entités", "Items", "Fluides",
                    "Recettes", "Technologies"):
        assert section in html, f"section absente : {section}"
    # Inventaire complet : les tables attendues du dump 0.1.5.
    for table in ("entity", "item", "fluid", "tile", "recipe", "technology"):
        assert f">{table} <span class=\"count\">" in html
    # Tuiles : l'eau et son fluide, les couches.
    assert "water_tile" in html and "badge fluid" in html
    # Pompe : règles de placement rendues + fluide pompé RÉSOLU par le
    # pipeline (aucun littéral dans le dump).
    assert "req " in html
    assert "offshore-pump" in html
    # Les 7 packs vanilla portent le badge science (faits, pas subgroup).
    assert html.count('class="badge science"') == 7
    assert "automation-science-pack" in html
    # Le filtre global est branché.
    assert "dump-filter" in html


def test_navigateur_dump_incomplet(tmp_path: Path) -> None:
    """Sans sections 0.1.5 (inventaire/tuiles), la page dégrade proprement
    au lieu de crasher — les replis sont explicites."""
    dump = {"meta": {"game_version": "2.0.0"}, "items": {"coin": {"type": "item"}}}
    out = tmp_path / "dump.html"
    html = write_dump_html(dump, out).read_text(encoding="utf-8")
    assert "Inventaire absent" in html
    assert "Section tuiles absente" in html
    assert ">coin<" in html
