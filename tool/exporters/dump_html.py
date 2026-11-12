"""Navigateur HTML du dump : « notre Factoriopedia », alimentée par le dump.

Le jeu n'expose AUCUNE API Lua pour lire la Factoriopedia (elle n'est qu'une
vue sur les prototypes) ; cette page est la nôtre : l'inventaire A→Z des 39
tables de prototypes, les tuiles (couches de collision + fluide), les
entités avec leurs faits structurels (catégories, fluidboxes, énergie,
règles de placement sur tuiles), les items/fluides (avec le badge « science »
issu des faits), les recettes et les technologies.

Le dump reste la seule source : aucun nom, aucune valeur inventée. La
seule structuration est celle du pipeline (``inject_pumped_fluids`` pour le
fluide pompé des sources, ``science_pack_names`` pour les packs), toutes
deux dérivées des faits du dump.

Une boîte de filtre (JS inline, sans dépendance) cache les lignes qui ne
correspondent pas, dans toutes les tables de la page."""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from tool.parsers.vanilla import inject_pumped_fluids, science_pack_names

_CSS = """
:root{
  --bg:#141419;--panel:#1e1e26;--line:#3a3a45;--txt:#d7d7e0;--muted:#8f8fa0;
  --accent:#6f6fe6;--ok:#4caf50;--warn:#ff9800;--bad:#f44336;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);
  font-family:"Segoe UI",system-ui,-apple-system,sans-serif}
header{padding:24px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{margin:0;font-size:22px}
.sub{color:var(--muted);font-size:12px;margin-top:4px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.stat{border:1px solid var(--line);border-radius:10px;padding:10px 14px;
  background:rgba(255,255,255,.04)}
.stat .lab{color:var(--muted);font-size:10px;text-transform:uppercase;
  letter-spacing:.06em}
.stat .val{font-size:18px;font-weight:700;font-variant-numeric:tabular-nums}
.filterbar{position:sticky;top:0;z-index:5;background:var(--bg);
  padding:10px 24px;border-bottom:1px solid var(--line)}
.filterbar input{width:100%;padding:8px 12px;border-radius:8px;
  border:1px solid var(--line);background:var(--panel);color:var(--txt);
  font-size:14px}
main{padding:0 24px 48px}
section{margin-top:28px}
section > h2{font-size:16px;border-bottom:1px solid var(--line);
  padding-bottom:6px;color:var(--accent)}
table{width:100%;border-collapse:collapse;font-size:12px}
th{color:var(--muted);text-align:left;font-weight:600;padding:6px 8px;
  border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:5px 8px;border-bottom:1px solid rgba(255,255,255,.05)}
tr:hover td{background:rgba(255,255,255,.03)}
code,.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px}
.chip{display:inline-block;border:1px solid var(--line);border-radius:6px;
  padding:0 6px;margin:1px 2px 1px 0;font-size:10px;color:var(--muted);
  font-family:ui-monospace,Menlo,Consolas,monospace}
.badge{display:inline-block;border-radius:6px;padding:0 6px;
  font-size:10px;font-weight:700;letter-spacing:.04em}
.badge.science{background:rgba(79,195,247,.15);color:#4fc3f7;
  border:1px solid rgba(79,195,247,.4)}
.badge.fluid{background:rgba(41,182,246,.12);color:#29b6f6;
  border:1px solid rgba(41,182,246,.35)}
details.inv{border:1px solid var(--line);border-radius:8px;
  margin:6px 0;background:var(--panel)}
details.inv > summary{cursor:pointer;padding:8px 12px;font-size:12px;
  font-family:ui-monospace,Menlo,Consolas,monospace}
details.inv[open] > summary{border-bottom:1px solid var(--line)}
.names{padding:10px 14px;line-height:2}
.muted{color:var(--muted)}
.count{color:var(--muted);font-weight:400}
"""

_JS = """
(function(){
  var input = document.getElementById('dump-filter');
  if (!input) return;
  input.addEventListener('input', function(){
    var q = this.value.trim().toLowerCase();
    document.querySelectorAll('main table tbody tr, details.inv').forEach(function(el){
      var hay = (el.getAttribute('data-search') || el.textContent).toLowerCase();
      el.style.display = (!q || hay.indexOf(q) !== -1) ? '' : 'none';
    });
  });
})();
"""


def _esc(value: Any) -> str:
    return _html.escape(str(value)) if value is not None else ""


def _chips(values: Any) -> str:
    if not values:
        return '<span class="muted">—</span>'
    return "".join(f'<span class="chip">{_esc(v)}</span>' for v in values)


def _fluidbox_summary(boxes: Any) -> str:
    if not isinstance(boxes, dict):
        return '<span class="muted">—</span>'
    detail = boxes.get("detail")
    parts: list[str] = []
    if isinstance(detail, dict):
        for box in detail.values():
            if not isinstance(box, dict):
                continue
            ptype = box.get("production_type", "?")
            filt = box.get("filter")
            parts.append(
                f'{_esc(ptype)}'
                + (f'&nbsp;<span class="chip">{_esc(filt)}</span>' if filt else "")
            )
    if not parts:
        parts.append(f'in:{boxes.get("input", 0)} out:{boxes.get("output", 0)}')
    return " · ".join(parts) or '<span class="muted">—</span>'


def _ingredients_list(entries: Any) -> str:
    if not entries:
        return '<span class="muted">—</span>'
    parts = []
    for ing in entries:
        if isinstance(ing, dict):
            parts.append(f'{_esc(ing.get("name"))} ×{int(ing.get("amount", 1) or 0)}')
    return " + ".join(parts)


def _stat(label: str, value: Any) -> str:
    return (
        f'<div class="stat"><div class="lab">{_esc(label)}</div>'
        f'<div class="val">{_esc(value)}</div></div>'
    )


def _section(title: str, anchor: str, body: str) -> str:
    return f'<section id="{anchor}"><h2>{_esc(title)}</h2>{body}</section>'


def _inventory_fragment(inventory: dict) -> str:
    if not inventory:
        return '<p class="muted">Inventaire absent (dump &lt; 0.1.5).</p>'
    blocks = []
    empty = "<span class='muted'>vide</span>"
    for table in sorted(inventory):
        names = inventory[table] or []
        chips = "".join(f'<span class="chip">{_esc(n)}</span>' for n in names)
        blocks.append(
            f'<details class="inv" data-search="{_esc(table)} '
            f'{_esc(" ".join(names))}">'
            f"<summary>{_esc(table)} "
            f'<span class="count">({len(names)})</span></summary>'
            f'<div class="names">{chips or empty}</div>'
            f"</details>"
        )
    return "".join(blocks)


def _tiles_fragment(tiles: dict) -> str:
    if not tiles:
        return '<p class="muted">Section tuiles absente (dump &lt; 0.1.5).</p>'
    rows = []
    for name in sorted(tiles):
        entry = tiles[name] or {}
        layers = entry.get("collision_layers") or []
        fluid = entry.get("fluid")
        fluid_cell = (
            f"<span class='badge fluid'>{_esc(fluid)}</span>"
            if fluid
            else "<span class='muted'>—</span>"
        )
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(name)}</td>"
            f"<td>{_chips(layers)}</td>"
            f"<td>{fluid_cell}</td>"
            f"</tr>"
        )
    return (
        "<table><thead><tr><th>Tuile</th><th>Couches de collision</th>"
        "<th>Fluide</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _placement_summary(rules: Any) -> str:
    """Règles de placement sur tuiles : couches requises / en collision."""
    if not rules:
        return '<span class="muted">—</span>'
    parts = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        req = rule.get("required_tiles") or []
        coll = rule.get("colliding_tiles") or []
        remove = " (retire tuiles)" if rule.get("remove_on_collision") else ""
        parts.append(
            f"req {_chips(req)} · coll {_chips(coll)}{remove}"
        )
    return "<br>".join(parts) if parts else '<span class="muted">—</span>'


def _entities_fragment(entities: dict) -> str:
    rows = []
    for name in sorted(entities):
        e = entities[name] or {}
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(name)}</td>"
            f"<td>{_esc(e.get('type'))}</td>"
            f"<td>{_chips(e.get('crafting_categories'))}</td>"
            f"<td>{_chips(e.get('resource_categories'))}</td>"
            f"<td>{_fluidbox_summary(e.get('fluidboxes'))}</td>"
            f"<td>{_esc(e.get('energy_source', {}).get('type') if isinstance(e.get('energy_source'), dict) else '')}</td>"
            f"<td>{_placement_summary(e.get('tile_buildability_rules'))}</td>"
            f"<td class='mono'>{_esc(e.get('pumped_fluid') or '—')}</td>"
            "</tr>"
        )
    head = (
        "<table><thead><tr><th>Entité</th><th>Type</th>"
        "<th>Catégories de craft</th><th>Catégories de ressource</th>"
        "<th>Fluidboxes</th><th>Énergie</th><th>Placement (tuiles)</th>"
        "<th>Fluide pompé</th>"
        "</tr></thead><tbody>"
    )
    return head + "".join(rows) + "</tbody></table>"


def _items_fragment(items: dict, science: set[str]) -> str:
    rows = []
    for name in sorted(items):
        entry = items[name] or {}
        science_badge = (
            '<span class="badge science">science</span>' if name in science else ""
        )
        fuel = entry.get("fuel_value") or 0
        launches = entry.get("rocket_launch_products")
        launch_txt = (
            " + ".join(
                f"{_esc(p.get('name'))} ×{int(p.get('amount', 1) or 0)}"
                for p in launches
                if isinstance(p, dict)
            )
            if launches
            else ""
        )
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(name)}{science_badge}</td>"
            f"<td>{_esc(entry.get('display_type') or entry.get('type'))}</td>"
            f"<td class='mono'>{_esc(entry.get('subgroup') or '—')}</td>"
            f"<td class='mono'>{_esc(entry.get('stack_size') or '—')}</td>"
            f"<td class='mono'>{_esc(fuel) if fuel else '—'}</td>"
            f"<td class='mono'>{launch_txt or '—'}</td>"
            "</tr>"
        )
    head = (
        "<table><thead><tr><th>Item</th><th>Type</th><th>Subgroup</th>"
        "<th>Stack</th><th>Fuel (kJ)</th><th>Produits de lancement</th>"
        "</tr></thead><tbody>"
    )
    return head + "".join(rows) + "</tbody></table>"


def _fluids_fragment(fluids: dict, science: set[str]) -> str:
    rows = []
    for name in sorted(fluids):
        entry = fluids[name] or {}
        science_badge = (
            '<span class="badge science">science</span>' if name in science else ""
        )
        fuel = entry.get("fuel_value") or 0
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(name)}{science_badge}</td>"
            f"<td class='mono'>{_esc(entry.get('subgroup') or '—')}</td>"
            f"<td class='mono'>{_esc(entry.get('default_temperature', '—'))}</td>"
            f"<td class='mono'>{_esc(fuel) if fuel else '—'}</td>"
            "</tr>"
        )
    head = (
        "<table><thead><tr><th>Fluide</th><th>Subgroup</th>"
        "<th>Temp. par défaut</th><th>Fuel (kJ)</th></tr></thead><tbody>"
    )
    return head + "".join(rows) + "</tbody></table>"


def _recipes_fragment(recipes: dict) -> str:
    rows = []
    for name in sorted(recipes):
        r = recipes[name] or {}
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(name)}</td>"
            f"<td class='mono'>{_esc(r.get('category') or '—')}</td>"
            f"<td>{_ingredients_list(r.get('ingredients'))}</td>"
            f"<td>{_ingredients_list(r.get('products') or r.get('results'))}</td>"
            f"<td class='mono'>{_esc(r.get('energy') or '—')}</td>"
            "</tr>"
        )
    head = (
        "<table><thead><tr><th>Recette</th><th>Catégorie</th>"
        "<th>Ingrédients</th><th>Produits</th><th>Énergie (s)</th>"
        "</tr></thead><tbody>"
    )
    return head + "".join(rows) + "</tbody></table>"


def _technologies_fragment(technologies: dict) -> str:
    rows = []
    for tech_id in sorted(technologies):
        tech = technologies[tech_id] or {}
        unit = tech.get("unit") or {}
        costs = " + ".join(
            f"{_esc(i.get('name'))} ×{int(i.get('amount', 1) or 0)}"
            for i in unit.get("ingredients") or []
            if isinstance(i, dict)
        )
        rows.append(
            "<tr>"
            f"<td class='mono'>{_esc(tech_id)}</td>"
            f"<td class='mono'>{_esc(unit.get('count', '—'))} × ({costs or '—'})</td>"
            f"<td>{_chips(tech.get('prerequisites'))}</td>"
            f"<td class='mono'>{_esc(len(tech.get('effects') or []))}</td>"
            "</tr>"
        )
    head = (
        "<table><thead><tr><th>Technologie</th><th>Coût unitaire</th>"
        "<th>Prérequis</th><th>Effets</th></tr></thead><tbody>"
    )
    return head + "".join(rows) + "</tbody></table>"


def write_dump_html(dump: dict, out: Path) -> Path:
    """Écrit le navigateur du dump (inventaire A→Z + sections profondes).

    ``out`` reçoit la page HTML autonome ; retourne le chemin écrit. La
    structuration appliquée est celle du pipeline (fluide pompé résolu par
    tuiles/filtres, packs de science par les faits), rien d'autre."""
    dump = dict(dump)
    inject_pumped_fluids(dump)
    science = science_pack_names(dump)

    items = dump.get("items") or {}
    fluids = dump.get("fluids") or {}
    entities = dump.get("entities") or {}
    recipes = dump.get("recipes") or {}
    technologies = dump.get("technologies") or {}
    tiles = dump.get("tiles") or {}
    inventory = dump.get("inventory") or {}
    meta = dump.get("meta") or {}

    stats = "".join(
        [
            _stat("Version du jeu", meta.get("game_version", "?")),
            _stat("Tables (inventaire)", len(inventory)),
            _stat("Tuiles", len(tiles)),
            _stat("Items", len(items)),
            _stat("Fluides", len(fluids)),
            _stat("Entités", len(entities)),
            _stat("Recettes", len(recipes)),
            _stat("Technologies", len(technologies)),
        ]
    )

    document = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>Dump Factorio {_esc(meta.get('game_version', '?'))} — navigateur A→Z</title>"
        f"<style>{_CSS}</style></head><body>"
        "<header><h1>Dump Factorio — navigateur A→Z</h1>"
        f"<div class='sub'>L'inventaire complet des prototypes, tel qu'exporté par le mod compagnon. "
        f"Structuration du pipeline uniquement (fluide pompé par tuiles, packs de science par les faits) — aucune valeur inventée.</div>"
        f"<div class='stats'>{stats}</div></header>"
        "<div class='filterbar'><input id='dump-filter' type='text' "
        "placeholder='Filtrer partout (items, entités, tuiles, recettes, techs…)'></div>"
        "<main>"
        + _section("Inventaire A→Z (toutes les tables de prototypes)", "inventaire",
                   _inventory_fragment(inventory))
        + _section("Tuiles (couches + fluide)", "tuiles", _tiles_fragment(tiles))
        + _section("Entités", "entites", _entities_fragment(entities))
        + _section("Items", "items", _items_fragment(items, science))
        + _section("Fluides", "fluides", _fluids_fragment(fluids, science))
        + _section("Recettes", "recettes", _recipes_fragment(recipes))
        + _section("Technologies", "technologies", _technologies_fragment(technologies))
        + "</main>"
        f"<script>{_JS}</script></body></html>"
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(document, encoding="utf-8")
    return out
