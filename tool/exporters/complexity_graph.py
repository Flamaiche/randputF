"""Export du rapport de complexité d'une seed randputF.

Génère ``seed.complexity.html`` à côté de ``seed/seed.json`` lors de
l'export ``--out``. Le fichier est **autonome** : CSS et SVG sont générés en
Python, aucun CDN, aucun JavaScript, donc il s'ouvre hors ligne comme
``seed.graph.html``.

Le modèle suit ce que ferait réellement un joueur pour terminer l'arbre :

* pour chaque technologie, on prend les packs de science exigés par son
  ``unit`` (``count × amount``) ;
* on déplie récursivement la recette de chaque pack jusqu'aux
  ``pools.raw_resources`` / au kit de départ, en comptant les crafts ;
* chaque craft utilise l'atelier ``crafted_in`` de la recette (ou la main) ;
* le temps de craft d'un craft vaut ``energy / crafting_speed`` du bâtiment.

Mesures produites :

- courbes par tech : temps de recherche, ressources brutes consommées,
  nombre d'ateliers de fabrication distincts, ratio ressources / atelier ;
- résumé : score de complexité, temps de craft total (comme si un joueur
  faisait tous les crafts), temps de recherche total, fabricateur le plus
  utilisé et ressource la plus consommée pendant la partie.

Le fichier est indépendant du témoin de déterminisme (il n'entre pas dans
le hash md5) et est régénéré à chaque export.
"""

from __future__ import annotations

import html as _html
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Vitesses de craft
# ---------------------------------------------------------------------------

# Repli vanilla, utilisé SEULEMENT quand le dump ne fournit pas
# ``crafting_speed`` (ancien dump). Dès que l'exporteur émet le champ, la
# valeur du dump gagne. La main est à vitesse 1.
_FALLBACK_SPEEDS: dict[str, float] = {
    "assembling-machine-1": 0.5,
    "assembling-machine-2": 0.75,
    "assembling-machine-3": 1.25,
    "stone-furnace": 1.0,
    "steel-furnace": 2.0,
    "electric-furnace": 2.0,
    "chemical-plant": 1.0,
    "oil-refinery": 1.0,
    "centrifuge": 1.0,
    "rocket-silo": 1.0,
    "nuclear-reactor": 1.0,
    "heat-exchanger": 1.0,
    "boiler": 1.0,
    "electric-mining-drill": 0.5,
    "burner-mining-drill": 0.5,
    "pumpjack": 1.0,
    "offshore-pump": 1.0,
}

HAND = "main"


def _crafting_speeds(db: Any = None) -> dict[str, float]:
    """Vitesses de craft : dump (si présent) puis repli vanilla."""
    speeds = dict(_FALLBACK_SPEEDS)
    buildings = getattr(db, "buildings", None) if db is not None else None
    if buildings:
        for name, building in buildings.items():
            speed = getattr(building, "crafting_speed", None)
            if speed:
                speeds[name] = float(speed)
    return speeds


# ---------------------------------------------------------------------------
# Dépliage des recettes (modèle joueur)
# ---------------------------------------------------------------------------


@dataclass
class _Expansion:
    """Consommation cumulée d'un dépliage de recettes."""

    crafts: Counter = field(default_factory=Counter)
    raw: Counter = field(default_factory=Counter)
    buildings: Counter = field(default_factory=Counter)
    hand_crafts: int = 0
    machine_seconds: float = 0.0
    unknown: set[str] = field(default_factory=set)

    def add(self, other: "_Expansion") -> None:
        self.crafts.update(other.crafts)
        self.raw.update(other.raw)
        self.buildings.update(other.buildings)
        self.hand_crafts += other.hand_crafts
        self.machine_seconds += other.machine_seconds
        self.unknown |= other.unknown


class _RecipeIndex:
    """Index des recettes, avec choix déterministe d'une recette par produit.

    Plusieurs recettes peuvent produire le même item (variantes ``ease``).
    On préfère la recette de base (sans ``ease``), puis la première par nom,
    pour que le résultat ne dépende pas de l'ordre du JSON.
    """

    def __init__(self, recipes: list[dict]) -> None:
        self.by_name: dict[str, dict] = {
            r["name"]: r for r in recipes if r.get("name")
        }
        self._producers: dict[str, list[dict]] = defaultdict(list)
        for recipe in recipes:
            for result in recipe.get("results") or []:
                name = result.get("name")
                if name:
                    self._producers[name].append(recipe)
        self._chosen: dict[str, dict | None] = {}

    def chosen(self, item: str) -> dict | None:
        if item in self._chosen:
            return self._chosen[item]
        candidates = self._producers.get(item) or []
        chosen = None
        if candidates:
            ordered = sorted(
                candidates,
                key=lambda r: ("ease" in r["name"], r["name"]),
            )
            chosen = ordered[0]
        self._chosen[item] = chosen
        return chosen

    @staticmethod
    def output_amount(recipe: dict, item: str) -> int:
        total = sum(
            int(result.get("amount", 0) or 0)
            for result in recipe.get("results") or []
            if result.get("name") == item
        )
        return total or 1


def _expand(
    index: _RecipeIndex,
    speeds: dict[str, float],
    item: str,
    amount: int,
    *,
    terminal: set[str],
    exp: _Expansion,
    stack: tuple[str, ...],
    max_depth: int = 64,
) -> None:
    """Ajoute à ``exp`` ce qu'il faut pour produire ``amount`` unités de ``item``."""
    if amount <= 0:
        return
    if item in terminal:
        exp.raw[item] += amount
        return
    if item in stack or len(stack) >= max_depth:
        exp.raw[item] += amount
        return

    recipe = index.chosen(item)
    if recipe is None:
        exp.raw[item] += amount
        exp.unknown.add(item)
        return

    per_craft = index.output_amount(recipe, item)
    crafts = math.ceil(amount / per_craft)
    exp.crafts[recipe["name"]] += crafts

    crafted_in = recipe.get("crafted_in")
    energy = float(recipe.get("energy", 0) or 0)
    if crafted_in:
        speed = speeds.get(crafted_in, 1.0) or 1.0
        exp.buildings[crafted_in] += crafts
    else:
        speed = 1.0
        exp.hand_crafts += crafts
    exp.machine_seconds += crafts * energy / speed

    for ingredient in recipe.get("ingredients") or []:
        name = ingredient.get("name")
        if not name:
            continue
        qty = int(ingredient.get("amount", 0) or 0)
        _expand(
            index,
            speeds,
            name,
            crafts * qty,
            terminal=terminal,
            exp=exp,
            stack=stack + (item,),
            max_depth=max_depth,
        )


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------


def _tech_seconds(tech: dict) -> float:
    unit = tech.get("unit") or {}
    try:
        count = int(unit.get("count", 0) or 0)
    except (TypeError, ValueError):
        count = 0
    try:
        time = float(unit.get("time", 0) or 0)
    except (TypeError, ValueError):
        time = 0.0
    return max(count, 0) * max(time, 0.0)


def _science_requirements(tech: dict) -> list[tuple[str, int]]:
    """Packs de science (nom, quantité totale) exigés par la tech."""
    unit = tech.get("unit") or {}
    try:
        count = int(unit.get("count", 0) or 0)
    except (TypeError, ValueError):
        count = 0
    out: list[tuple[str, int]] = []
    for ingredient in unit.get("ingredients") or []:
        name = ingredient.get("name")
        if not name:
            continue
        amount = int(ingredient.get("amount", 0) or 0)
        out.append((name, max(count, 0) * amount))
    return out


def _format_seconds(value: float) -> str:
    seconds = max(0, int(round(value)))
    hours, rest = divmod(seconds, 3600)
    minutes, sec = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"


def _format_number(value: float) -> str:
    if value >= 100:
        return f"{value:,.0f}".replace(",", " ")
    if value >= 10:
        return f"{value:,.1f}".replace(",", " ").replace(".0", "")
    return f"{value:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def analyze_complexity(seed: dict, db: Any = None) -> dict:
    """Calcule le rapport de complexité complet de ``seed``."""
    recipes = seed.get("recipes") or []
    technologies = seed.get("technologies") or []
    progression = list(seed.get("progression_order") or [])
    free = set(seed.get("free_researches") or [])
    starter = {
        item.get("name")
        for item in (seed.get("starter_kit") or [])
        if item.get("name")
    }
    pools = seed.get("pools") or {}
    raw_resources = set(pools.get("raw_resources") or ())

    index = _RecipeIndex(recipes)
    # Le kit de départ sert d'amorce : ses objets coupent les cycles de
    # recettes (fonte → foreuse → pompe → …). Ils sont donc terminaux.
    terminal = raw_resources | starter
    speeds = _crafting_speeds(db)
    tech_by_id = {t.get("id"): t for t in technologies if t.get("id")}

    global_exp = _Expansion()
    tech_rows: list[dict] = []
    seen_buildings: set[str] = set()
    cumulative = {
        "time": 0.0,
        "packs": 0,
        "raw": 0,
        "craft_seconds": 0.0,
        "crafts": 0,
    }

    for position, tech_id in enumerate(progression, start=1):
        tech = tech_by_id.get(tech_id)
        if not tech:
            continue

        tech_exp = _Expansion()
        packs: list[dict] = []
        pack_total = 0
        for name, amount in _science_requirements(tech):
            packs.append({"name": name, "amount": amount})
            pack_total += amount
            if amount > 0:
                _expand(
                    index,
                    speeds,
                    name,
                    amount,
                    terminal=terminal,
                    exp=tech_exp,
                    stack=(),
                )
        global_exp.add(tech_exp)

        research_time = _tech_seconds(tech)
        raw_total = sum(tech_exp.raw.values())
        buildings = {b for b in tech_exp.buildings}
        crafts_total = sum(tech_exp.crafts.values()) + tech_exp.hand_crafts
        ratio = raw_total / max(len(buildings), 1)

        cumulative["time"] += research_time
        cumulative["packs"] += pack_total
        cumulative["raw"] += raw_total
        cumulative["craft_seconds"] += tech_exp.machine_seconds
        cumulative["crafts"] += crafts_total
        seen_buildings |= buildings
        cumulative_score = (
            cumulative["time"]
            + cumulative["craft_seconds"]
            + 0.5 * cumulative["packs"]
            + 10 * len(seen_buildings)
        )

        tech_rows.append(
            {
                "num": position,
                "id": tech_id,
                "name": tech.get("localised_name") or tech_id,
                "free": tech_id in free,
                "research_time": round(research_time, 2),
                "packs": pack_total,
                "pack_list": packs,
                "raw_total": raw_total,
                "buildings": sorted(buildings),
                "building_count": len(buildings),
                "ratio": round(ratio, 2),
                "crafts": crafts_total,
                "craft_seconds": round(tech_exp.machine_seconds, 2),
                "hand_crafts": tech_exp.hand_crafts,
                "cumulative_time": round(cumulative["time"], 2),
                "cumulative_packs": cumulative["packs"],
                "cumulative_raw": cumulative["raw"],
                "cumulative_buildings": len(seen_buildings),
                "cumulative_craft_seconds": round(cumulative["craft_seconds"], 2),
                "cumulative_crafts": cumulative["crafts"],
                "cumulative_score": round(cumulative_score, 2),
            }
        )

    total_research = cumulative["time"]
    total_craft_seconds = global_exp.machine_seconds
    total_packs = cumulative["packs"]
    total_raw = sum(global_exp.raw.values())
    distinct_buildings = len(global_exp.buildings)
    total_crafts = sum(global_exp.crafts.values()) + global_exp.hand_crafts

    # Score : temps de recherche + temps de craft + packs + variété d'ateliers.
    complexity_score = (
        total_research + total_craft_seconds + 0.5 * total_packs + 10 * distinct_buildings
    )

    building_usage = global_exp.buildings.most_common()
    resource_usage = global_exp.raw.most_common()

    return {
        "seed_value": (seed.get("meta") or {}).get("seed", "?"),
        "generator_version": (seed.get("meta") or {}).get("generator_version", "?"),
        "tech_count": len(tech_rows),
        "free_count": len(free),
        "total_research_seconds": round(total_research, 2),
        "total_research_label": _format_seconds(total_research),
        "total_craft_seconds": round(total_craft_seconds, 2),
        "total_craft_label": _format_seconds(total_craft_seconds),
        "total_packs": total_packs,
        "total_raw": total_raw,
        "total_crafts": total_crafts,
        "hand_crafts": global_exp.hand_crafts,
        "complexity_score": round(complexity_score, 1),
        "distinct_buildings": distinct_buildings,
        "most_used_fabricator": building_usage[0][0] if building_usage else None,
        "most_used_fabricator_crafts": building_usage[0][1] if building_usage else 0,
        "most_used_resource": resource_usage[0][0] if resource_usage else None,
        "most_used_resource_amount": resource_usage[0][1] if resource_usage else 0,
        "building_usage": building_usage,
        "resource_usage": resource_usage,
        "unknown_terminals": sorted(global_exp.unknown),
        "tech_rows": tech_rows,
    }


# ---------------------------------------------------------------------------
# SVG (aucune dépendance, aucun CDN)
# ---------------------------------------------------------------------------

_W = 1000
_H = 260
_ML = 92
_MR = 24
_MT = 34
_MB = 44


def _chart_svg(
    title: str,
    values: list[float],
    labels: list[str],
    color: str,
    *,
    cumulative_label: str = "",
) -> str:
    """Graphique ligne SVG (viewBox 1000×260) d'une série par tech."""
    plot_w = _W - _ML - _MR
    plot_h = _H - _MT - _MB
    count = len(values)
    top = max(values) if values else 0
    top = top if top > 0 else 1
    top *= 1.08

    def px(index: int) -> float:
        if count <= 1:
            return _ML + plot_w / 2
        return _ML + (index / (count - 1)) * plot_w

    def py(value: float) -> float:
        return _MT + plot_h - (value / top) * plot_h

    parts: list[str] = [
        f'<svg class="chart" viewBox="0 0 {_W} {_H}" role="img" '
        f'aria-label="{_html.escape(title)}">',
        f'<text x="{_ML}" y="20" class="chart-title">{_html.escape(title)}</text>',
    ]

    # Grille + graduations Y (4 niveaux).
    for step in range(5):
        fraction = step / 4
        y = _MT + plot_h - fraction * plot_h
        value = top * fraction
        parts.append(
            f'<line x1="{_ML}" y1="{y:.1f}" x2="{_W - _MR}" y2="{y:.1f}" '
            f'class="grid"/>'
        )
        parts.append(
            f'<text x="{_ML - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'class="tick">{_html.escape(_format_number(value))}</text>'
        )

    # Points + aire + ligne.
    if count:
        points = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(values))
        area = (
            f"{_ML:.1f},{_MT + plot_h:.1f} "
            + points
            + f" {px(count - 1):.1f},{_MT + plot_h:.1f}"
        )
        parts.append(f'<polygon points="{area}" fill="{color}" opacity="0.12"/>')
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    # Graduations X : au plus 12 étiquettes.
    if count:
        stride = max(1, math.ceil(count / 12))
        for i in range(0, count, stride):
            parts.append(
                f'<text x="{px(i):.1f}" y="{_H - 14}" text-anchor="middle" '
                f'class="tick">{_html.escape(labels[i] if i < len(labels) else "")}</text>'
            )

    if cumulative_label:
        parts.append(
            f'<text x="{_W - _MR}" y="20" text-anchor="end" class="chart-sub">'
            f"{_html.escape(cumulative_label)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def _bar_list(title: str, rows: list[tuple[str, float]], color: str) -> str:
    if not rows:
        return f'<p class="muted">{_html.escape(title)} : aucune donnée.</p>'
    top = max(value for _, value in rows) or 1
    items = []
    for name, value in rows:
        width = max(2.0, (value / top) * 100)
        items.append(
            '<div class="bar-row">'
            f'<div class="bar-name">{_html.escape(name)}</div>'
            f'<div class="bar-bg"><div class="bar-fill" '
            f'style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="bar-val">{_html.escape(_format_number(value))}</div>'
            "</div>"
        )
    return (
        f'<h3>{_html.escape(title)}</h3><div class="bar-wrap">'
        + "".join(items)
        + "</div>"
    )


_CSS = """
:root{
  --bg:#141419;--panel:#1e1e26;--line:#3a3a45;--txt:#d7d7e0;--muted:#8f8fa0;
  --accent:#6f6fe6;--ok:#4caf50;--warn:#ff9800;--bad:#f44336;--hl4:#5c6bc0;
  --hl5:#29b6f6;--hl6:#26a69a;--hl7:#9ccc65;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);
  font-family:"Segoe UI",system-ui,-apple-system,sans-serif}
header{padding:24px;border-bottom:1px solid var(--line);background:var(--panel)}
h1{margin:0;font-size:22px}
.sub{color:var(--muted);font-size:12px;margin-top:4px}
.stats{display:flex;flex-wrap:wrap;gap:12px;margin-top:18px}
.stat{border:1px solid var(--line);border-radius:10px;padding:12px 16px;
  background:rgba(255,255,255,.04);min-width:170px;flex:1 1 170px}
.stat .lab{color:var(--muted);font-size:10px;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:6px}
.stat .val{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums}
.stat .hint{color:var(--muted);font-size:10px;margin-top:3px}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.acc{color:var(--accent)}
main{padding:24px;max-width:1400px;margin:0 auto}
section{margin-bottom:36px}
h2{font-size:17px;margin:0 0 14px;padding-bottom:8px;
  border-bottom:1px solid var(--line)}
h3{font-size:13px;color:var(--muted);margin:0 0 8px;font-weight:600}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:1000px){.charts{grid-template-columns:1fr}}
.card{border:1px solid var(--line);border-radius:10px;padding:10px;
  background:rgba(255,255,255,.02)}
.chart{width:100%;height:auto;display:block}
.chart-title{fill:var(--txt);font-size:13px;font-weight:600}
.chart-sub{fill:var(--muted);font-size:11px}
.grid{stroke:rgba(255,255,255,.07);stroke-width:1}
.tick{fill:var(--muted);font-size:10px}
table{width:100%;border-collapse:collapse;font-size:12px}
th{position:sticky;top:0;background:var(--panel);text-align:left;
  color:var(--muted);font-size:10px;text-transform:uppercase;
  letter-spacing:.06em;padding:9px 10px;border-bottom:1px solid var(--line)}
td{padding:7px 10px;border-bottom:1px solid var(--line)}
tbody tr:hover{background:rgba(255,255,255,.03)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.tech-name{font-weight:600;overflow-wrap:anywhere}
.tech-id{color:var(--muted);font-size:10px}
.badge{display:inline-block;padding:1px 7px;border-radius:10px;
  font-size:9px;font-weight:700}
.badge.free{background:rgba(76,175,80,.15);color:var(--ok)}
.badge.pay{background:rgba(255,152,0,.15);color:var(--warn)}
.tag{display:inline-block;padding:1px 6px;margin:1px;border-radius:10px;
  background:rgba(255,255,255,.07);border:1px solid var(--line);
  color:var(--muted);font-size:10px}
.bar-wrap{margin-top:8px}
.bar-row{display:flex;align-items:center;gap:10px;margin:5px 0}
.bar-name{width:170px;flex:none;font-size:11px;color:var(--muted);
  overflow-wrap:anywhere}
.bar-bg{flex:1;height:10px;background:rgba(255,255,255,.08);
  border-radius:5px;overflow:hidden}
.bar-fill{height:100%;border-radius:5px}
.bar-val{width:90px;flex:none;font-size:11px;text-align:right;
  font-variant-numeric:tabular-nums}
.muted{color:var(--muted);font-size:11px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}
@media(max-width:1000px){.two{grid-template-columns:1fr}}
.note{border-left:3px solid var(--accent);padding:8px 12px;margin-top:14px;
  color:var(--muted);font-size:11px;background:rgba(111,111,230,.06)}
"""


def _stat(lab: str, val: str, cls: str = "", hint: str = "") -> str:
    hint_html = f'<div class="hint">{_html.escape(hint)}</div>' if hint else ""
    return (
        f'<div class="stat"><div class="lab">{_html.escape(lab)}</div>'
        f'<div class="val {cls}">{_html.escape(val)}</div>{hint_html}</div>'
    )


def write_complexity_html(seed: dict, path: Path, db: Any = None) -> None:
    """Écrit ``path`` (HTML autonome) du rapport de complexité de la seed."""
    data = analyze_complexity(seed, db)
    rows = data["tech_rows"]
    labels = [str(row["num"]) for row in rows]

    header_stats = "".join(
        [
            _stat("Score de complexité", _format_number(data["complexity_score"]), "bad"),
            _stat(
                "Temps de craft total",
                data["total_craft_label"],
                "acc",
                "somme des crafts, 1 machine",
            ),
            _stat(
                "Temps de recherche",
                data["total_research_label"],
                "acc",
                "toutes les techs",
            ),
            _stat("Packs de science", _format_number(data["total_packs"]), "acc"),
            _stat(
                "Fabricateur le plus utilisé",
                data["most_used_fabricator"] or "—",
                "ok",
                f"{_format_number(data['most_used_fabricator_crafts'])} crafts",
            ),
            _stat(
                "Ressource la plus consommée",
                data["most_used_resource"] or "—",
                "warn",
                f"{_format_number(data['most_used_resource_amount'])} unités",
            ),
        ]
    )

    charts = "".join(
        [
            f'<div class="card">{_chart_svg("Temps de recherche par tech (s)", [r["research_time"] for r in rows], labels, "#5c6bc0")}</div>',
            f'<div class="card">{_chart_svg("Ressources brutes par tech", [r["raw_total"] for r in rows], labels, "#29b6f6")}</div>',
            f'<div class="card">{_chart_svg("Ateliers de fabrication distincts par tech", [r["building_count"] for r in rows], labels, "#4caf50")}</div>',
            f'<div class="card">{_chart_svg("Ratio ressources / atelier par tech", [r["ratio"] for r in rows], labels, "#ff9800")}</div>',
            f'<div class="card">{_chart_svg("Score de complexité cumulé", [r["cumulative_score"] for r in rows], labels, "#6f6fe6")}</div>',
            f'<div class="card">{_chart_svg("Crafts cumulés", [r["cumulative_crafts"] for r in rows], labels, "#26a69a")}</div>',
        ]
    )

    building_rows = _bar_list(
        "Ateliers les plus utilisés (crafts)",
        data["building_usage"][:12],
        "var(--accent)",
    )
    resource_rows = _bar_list(
        "Ressources brutes les plus consommées",
        data["resource_usage"][:12],
        "var(--hl5)",
    )

    table_rows = []
    for row in rows:
        badge = "free" if row["free"] else "pay"
        label = "Starter" if row["free"] else "Payante"
        buildings = "".join(
            f'<span class="tag">{_html.escape(b)}</span>' for b in row["buildings"]
        ) or '<span class="muted">—</span>'
        table_rows.append(
            f"<tr><td class='num'>{row['num']}</td>"
            f"<td><div class='tech-name'>{_html.escape(row['name'])}</div>"
            f"<div class='tech-id'>{_html.escape(row['id'])}</div></td>"
            f"<td><span class='badge {badge}'>{label}</span></td>"
            f"<td class='num'>{_format_number(row['research_time'])}</td>"
            f"<td class='num'>{_format_number(row['packs'])}</td>"
            f"<td class='num'>{_format_number(row['raw_total'])}</td>"
            f"<td class='num'>{row['building_count']}</td>"
            f"<td class='num'>{_format_number(row['ratio'])}</td>"
            f"<td class='num'>{_format_number(row['crafts'])}</td>"
            f"<td>{buildings}</td></tr>"
        )

    unknown_note = ""
    if data["unknown_terminals"]:
        names = ", ".join(_html.escape(n) for n in data["unknown_terminals"])
        unknown_note = (
            '<div class="note">Ingrédients sans recette ni ressource brute '
            f"(traités comme bruts) : {names}</div>"
        )

    title = f"randputF seed {data['seed_value']}"
    document = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>{_html.escape(title)} - complexité</title>"
        f"<style>{_CSS}</style></head><body>"
        f"<header><h1>{_html.escape(title)} — complexité</h1>"
        "<div class='sub'>Modèle joueur : packs de science dépliés jusqu'aux "
        "ressources brutes, crafts comptés par atelier.</div>"
        f"<div class='stats'>{header_stats}</div></header><main>"
        "<section><h2>Courbes par technologie</h2>"
        f"<div class='charts'>{charts}</div>"
        "<div class='note'>Le temps de craft total est la somme des temps de "
        "tous les crafts nécessaires pour tous les packs de science, comme si "
        "une seule machine les enchaînait. Le score ajoute le temps de "
        "recherche, 0,5 × packs et 10 × ateliers distincts.</div></section>"
        "<section><div class='two'>"
        f"<div>{building_rows}</div><div>{resource_rows}</div>"
        f"</div>{unknown_note}</section>"
        "<section><h2>Détail par technologie</h2><table><thead><tr>"
        "<th style='width:36px'>#</th><th>Technologie</th><th>Type</th>"
        "<th class='num'>Recherche (s)</th><th class='num'>Packs</th>"
        "<th class='num'>Ressources</th><th class='num'>Ateliers</th>"
        "<th class='num'>Ratio</th><th class='num'>Crafts</th>"
        "<th>Ateliers utilisés</th></tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table></section></main></body></html>"
    )
    path.write_text(document, encoding="utf-8")


__all__ = ["write_complexity_html", "analyze_complexity"]
