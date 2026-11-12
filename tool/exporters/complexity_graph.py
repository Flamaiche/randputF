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

from tool.exporters.html_ui import TIP_HTML, UI_CSS, UI_SCRIPT, th as _th

# ---------------------------------------------------------------------------
# Vitesses de craft
# ---------------------------------------------------------------------------

HAND = "main"


def _crafting_speeds(db: Any = None) -> dict[str, float]:
    """Vitesses de craft : uniquement celles du dump.

    Tout bâtiment absent du dump (la main notamment) est à vitesse 1 :
    valeur neutre, sans connaissance vanilla.
    """
    speeds: dict[str, float] = {}
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

    # Traits verticaux aux positions des technologies (repères de lecture).
    if count:
        stride_v = max(1, math.ceil(count / 40))
        for i in range(0, count, stride_v):
            x = px(i)
            parts.append(
                f'<line x1="{x:.1f}" y1="{_MT}" x2="{x:.1f}" '
                f'y2="{_MT + plot_h:.1f}" class="grid grid-v"/>'
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
        # Points et valeurs numériques (échantillonnées si trop nombreux).
        stride_label = max(1, math.ceil(count / 20))
        for i, value in enumerate(values):
            cx, cy = px(i), py(value)
            parts.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.6" fill="{color}"/>'
                f'<title>{_html.escape(labels[i] if i < len(labels) else "")}</title>'
            )
            if i % stride_label == 0 or i == count - 1:
                label_y = cy - 7 if cy - 7 > _MT + 8 else cy + 14
                parts.append(
                    f'<text x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle" '
                    f'class="point-label">{_html.escape(_format_number(value))}</text>'
                )

    # Graduations X : etiquettes des technologies (au plus 20 pour la lisibilité).
    if count:
        stride = max(1, math.ceil(count / 20))
        for i in range(0, count, stride):
            label = labels[i] if i < len(labels) else ""
            # Truncation simple si trop long.
            if len(label) > 30:
                label = label[:27] + "..."
            parts.append(
                f'<text x="{px(i):.1f}" y="{_H - 14}" text-anchor="middle" '
                f'class="tick" title="{_html.escape(label)}">{_html.escape(label)}</text>'
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
.grid-v{stroke:rgba(255,255,255,.10);stroke-dasharray:2 5}
.tick{fill:var(--muted);font-size:10px}
.point-label{fill:var(--txt);font-size:9px;paint-order:stroke;
  stroke:var(--bg);stroke-width:2px;stroke-linejoin:round}
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

# Le rapport complet réutilise ``_CSS`` : les styles d'infobulle et de tri
# doivent donc y être inclus, pas seulement dans le document autonome.
_CSS = _CSS + UI_CSS


def _stat(lab: str, val: str, cls: str = "", hint: str = "") -> str:
    hint_html = f'<div class="hint">{_html.escape(hint)}</div>' if hint else ""
    return (
        f'<div class="stat"><div class="lab">{_html.escape(lab)}</div>'
        f'<div class="val {cls}">{_html.escape(val)}</div>{hint_html}</div>'
    )


def render_complexity_html(
    seed: dict, db: Any = None, *, title: str | None = None
) -> str:
    """Rend (chaîne) le rapport de complexité autonome de la seed."""
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
            f"<tr><td class='num' data-key='num' data-value='{row['num']}'>"
            f"{row['num']}</td>"
            f"<td data-key='name'><div class='tech-name'>"
            f"{_html.escape(row['name'])}</div>"
            f"<div class='tech-id'>{_html.escape(row['id'])}</div></td>"
            f"<td data-key='type'><span class='badge {badge}'>{label}</span></td>"
            f"<td class='num' data-key='research' data-value='{row['research_time']}'>"
            f"{_format_number(row['research_time'])}</td>"
            f"<td class='num' data-key='packs' data-value='{row['packs']}'>"
            f"{_format_number(row['packs'])}</td>"
            f"<td class='num' data-key='raw' data-value='{row['raw_total']}'>"
            f"{_format_number(row['raw_total'])}</td>"
            f"<td class='num' data-key='buildings' data-value='{row['building_count']}'>"
            f"{row['building_count']}</td>"
            f"<td class='num' data-key='ratio' data-value='{row['ratio']}'>"
            f"{_format_number(row['ratio'])}</td>"
            f"<td class='num' data-key='crafts' data-value='{row['crafts']}'>"
            f"{_format_number(row['crafts'])}</td>"
            f"<td data-key='used'>{buildings}</td></tr>"
        )

    unknown_note = ""
    if data["unknown_terminals"]:
        names = ", ".join(_html.escape(n) for n in data["unknown_terminals"])
        unknown_note = (
            '<div class="note">Ingrédients sans recette ni ressource brute '
            f"(traités comme bruts) : {names}</div>"
        )

    if title is None:
        title = f"randputF seed {data['seed_value']}"
    document = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>{_html.escape(title)} - complexité</title>"
        f"<style>{_CSS}</style></head><body>{TIP_HTML}"
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
        "<section><details class='table-fold' id='complexite-detail-table'>"
        "<summary>Détail par technologie</summary>"
        "<div class='scroll'><table data-table "
        "data-default-sort='[{\"key\":\"num\",\"dir\":1}]'><thead><tr>"
        + _th("#", "num", "num", "Ordre de progression de la technologie.",
              style="width:36px")
        + _th("Technologie", "name", "text", "Nom et identifiant de la technologie.")
        + _th("Type", "type", "text", "Tech gratuite (starter) ou payante en packs.")
        + _th("Recherche (s)", "research", "num",
              "Temps de recherche de la technologie.")
        + _th("Packs", "packs", "num",
              "Nombre total de packs de science exigés.")
        + _th("Ressources", "raw", "num",
              "Ressources brutes nécessaires aux packs de cette tech.")
        + _th("Ateliers", "buildings", "num",
              "Nombre d'ateliers de fabrication distincts utilisés.")
        + _th("Ratio", "ratio", "num",
              "Ressources brutes par atelier distinct.")
        + _th("Crafts", "crafts", "num",
              "Nombre de crafts nécessaires aux packs de cette tech.")
        + _th("Ateliers utilisés", "used", "text",
              "Ateliers de fabrication employés pour cette tech.")
        + "</tr></thead><tbody>"
        + "".join(table_rows)
        + "</tbody></table></div></details></section></main>"
        + UI_SCRIPT
        + "</body></html>"
    )
    return document


def write_complexity_html(seed: dict, path: Path, db: Any = None) -> None:
    """Écrit ``path`` (HTML autonome) du rapport de complexité de la seed."""
    document = render_complexity_html(seed, db)
    path.write_text(document, encoding="utf-8")


# ---------------------------------------------------------------------------
# Joueur simulé (partie sans map)
# ---------------------------------------------------------------------------

# ``energy_usage`` du dump est en joules par tick (60 ticks/s) : J/tick × 60 / 1000.
_ENERGY_KW_FACTOR = 0.06


def _amount(value: Any) -> int | float:
    """Convertit un montant du dump en nombre (entier quand c'est exact)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return number


def _item_amounts(entries: Any) -> list[tuple[str, int | float]]:
    out: list[tuple[str, int | float]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        out.append((str(name), _amount(entry.get("amount", 0))))
    return out


def _number(value: Any) -> int | float:
    """Arrondit une mesure : entier si exact, sinon 3 décimales."""
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return round(number, 3)


class _Playthrough:
    """Simulation d'une partie : minage, crafts, sous-produits, déclencheurs.

    L'inventaire est porté d'une technologie à l'autre. Un besoin est d'abord
    satisfait par l'inventaire, puis par la meilleure recette débloquée, ou par
    le minage quand l'objet est une ressource brute, ou enfin par une
    fourniture externe (pompage, récolte, orbite).
    """

    def __init__(self, seed: dict, db: Any = None) -> None:
        self.seed = seed
        self.db = db
        self.recipes = [
            r for r in (seed.get("recipes") or []) if isinstance(r, dict) and r.get("name")
        ]
        self.recipe_by_name = {r["name"]: r for r in self.recipes}
        self.producers: dict[str, list[dict]] = defaultdict(list)
        for recipe in self.recipes:
            for name, _qty in _item_amounts(recipe.get("results")):
                self.producers[name].append(recipe)

        self.entities = {
            str(name): entry
            for name, entry in (seed.get("entities") or {}).items()
            if isinstance(entry, dict)
        }
        # Fluides pompés déclarés par l'extracteur (``pumped_fluid``).
        self.fluid_sources: dict[str, list[str]] = defaultdict(list)
        for name, entry in self.entities.items():
            pumped = entry.get("pumped_fluid")
            if pumped:
                self.fluid_sources[str(pumped)].append(name)
        self.fluids = {
            str(name): entry
            for name, entry in (seed.get("fluids") or {}).items()
            if isinstance(entry, dict)
        }
        self.items = {
            str(name): entry
            for name, entry in (seed.get("items") or {}).items()
            if isinstance(entry, dict)
        }
        self.fluid_conversions = self._find_fluid_conversions()
        self.raw_resources = set((seed.get("pools") or {}).get("raw_resources") or ())
        self.techs = [
            t for t in (seed.get("technologies") or []) if isinstance(t, dict) and t.get("id")
        ]
        self.tech_by_id = {t["id"]: t for t in self.techs}
        self.progression = list(seed.get("progression_order") or [])

        # Lancement de fusée : une techno dont le déclencheur envoie un objet
        # en orbite produit les packs déclarés par le payload
        # (``rocket_launch_products`` de l'item lancé). La clé est le PRODUIT,
        # pas l'id de techno : le pack reste produisible même si la techno ne
        # s'appelle pas comme lui.
        self.launch_requirements: dict[str, str] = {}
        for tech in self.techs:
            trigger = tech.get("research_trigger")
            if not (
                isinstance(trigger, dict)
                and trigger.get("type") == "send-item-to-orbit"
                and trigger.get("item")
            ):
                continue
            payload = str(trigger["item"])
            for product, _qty in self._launch_products(payload):
                self.launch_requirements[product] = payload
        self.rocket_part = self._find_rocket_part()

        # Recettes débloquées par une technologie.
        self.unlocked_by: dict[str, str] = {}
        for tech in self.techs:
            for effect in tech.get("effects") or []:
                if (
                    isinstance(effect, dict)
                    and effect.get("type") == "unlock-recipe"
                    and effect.get("recipe")
                ):
                    self.unlocked_by.setdefault(str(effect["recipe"]), tech["id"])
        self.processed: set[str] = set()

        # Gisements minables : produit -> gisement. Toute entité du dump
        # déclarant des produits minables compte (gisements, arbres…).
        self.mineables: dict[str, list[dict]] = defaultdict(list)
        for name, entry in self.entities.items():
            for product, qty in _item_amounts(entry.get("mineable_products")):
                self.mineables[product].append(
                    {
                        "name": name,
                        "category": entry.get("resource_category"),
                        "time": float(entry.get("mineable_time", 0) or 0),
                        "yield": qty or 1,
                    }
                )

        # Foreuses disponibles.
        self.drills: list[dict] = []
        for name, entry in self.entities.items():
            if entry.get("type") != "mining-drill":
                continue
            self.drills.append(
                {
                    "name": name,
                    "categories": entry.get("resource_categories") or [],
                    "speed": float(entry.get("mining_speed", 1) or 1),
                }
            )

        self.speeds = _crafting_speeds(db)

        self.inv: dict[str, float] = defaultdict(float)
        self.produced: dict[str, float] = defaultdict(float)
        self.consumed: dict[str, float] = defaultdict(float)
        self.mined: dict[str, float] = defaultdict(float)
        self.mining_seconds: dict[str, float] = defaultdict(float)
        self.crafts: dict[str, int] = defaultdict(int)
        self.craft_seconds: dict[str, float] = defaultdict(float)
        self.external: dict[str, float] = defaultdict(float)
        self.energy_kj: dict[str, float] = defaultdict(float)
        self.power_kw: dict[str, float] = defaultdict(float)
        self.recipe_crafts: dict[str, int] = defaultdict(int)
        self.used_buildings: set[str] = set()
        self.buildings: list[str] = []
        self.total_craft_seconds = 0.0

    # -- disponibilité des recettes -----------------------------------------

    def _is_available(self, recipe_name: str) -> bool:
        tech = self.unlocked_by.get(recipe_name)
        return tech is None or tech in self.processed

    @staticmethod
    def _ingredient_names(recipe: dict) -> set[str]:
        return {name for name, _qty in _item_amounts(recipe.get("ingredients"))}

    def _choose(self, item: str, stack: tuple[str, ...]) -> dict | None:
        candidates = [
            r for r in self.producers.get(item, []) if self._is_available(r["name"])
        ]
        if not candidates:
            return None

        def cyclic(recipe: dict) -> bool:
            names = self._ingredient_names(recipe)
            return item in names or any(name in stack for name in names)

        usable = [r for r in candidates if not cyclic(r)] or candidates
        # Recette homonyme d'abord, puis hors variantes ``ease``, puis ordre.
        return sorted(
            usable,
            key=lambda r: (r["name"] != item, "ease" in r["name"], r["name"]),
        )[0]

    @staticmethod
    def _output_amount(recipe: dict, item: str) -> int | float:
        total: int | float = 0
        for name, qty in _item_amounts(recipe.get("results")):
            if name == item:
                total += qty
        return total or 1

    # -- minage --------------------------------------------------------------

    def _building_power_kw(self, name: str | None) -> float:
        """Puissance électrique d'un bâtiment, en kW."""
        if not name:
            return 0.0
        entry = self.entities.get(name) or {}
        usage = entry.get("energy_usage")
        if usage is None and self.db is not None:
            buildings = getattr(self.db, "buildings", None) or {}
            usage = getattr(buildings.get(name), "energy_usage", None)
        try:
            return float(usage) * _ENERGY_KW_FACTOR
        except (TypeError, ValueError):
            return 0.0

    def _recipe_power_kw(self, recipe: dict) -> float:
        return self._building_power_kw(recipe.get("crafted_in"))

    def _best_drill(self, category: Any) -> dict | None:
        best = None
        for drill in self.drills:
            if category and category not in drill["categories"]:
                continue
            if (
                best is None
                or drill["speed"] > best["speed"]
                or (drill["speed"] == best["speed"] and drill["name"] < best["name"])
            ):
                best = drill
        return best

    def _mine(self, item: str, amount: float) -> bool:
        sources = self.mineables.get(item) or []
        if not sources:
            return False
        source = sorted(sources, key=lambda s: (-s["yield"], s["name"]))[0]
        # Sans catégorie de forage (arbre récolté à la main) : aucune foreuse,
        # vitesse de base 1.
        drill = self._best_drill(source["category"]) if source["category"] else None
        speed = drill["speed"] if drill else 1.0
        if drill:
            self.used_buildings.add(drill["name"])
        yield_per_cycle = source["yield"] or 1
        cycles = math.ceil(amount / yield_per_cycle)
        got = cycles * yield_per_cycle
        self.mined[item] += got
        self.produced[item] += got
        self.inv[item] += got
        if speed > 0:
            seconds = cycles * source["time"] / speed
            self.mining_seconds[item] += seconds
            power = self._building_power_kw(drill["name"]) if drill else 0.0
            self.energy_kj[item] += power * seconds
            self.power_kw[item] = max(self.power_kw[item], power)
        return True

    # -- production ---------------------------------------------------------

    def _supply_external(self, item: str, amount: float) -> None:
        self.external[item] += amount
        self.produced[item] += amount
        self.inv[item] += amount

    def _find_fluid_conversions(self) -> dict[str, dict]:
        """Convertit un fluide en un autre (ex. chaudière : eau -> vapeur).

        La correspondance est déduite des ``fluidboxes`` du dump : une entrée
        filtrée et une sortie filtrée unique suffisent à identifier la
        conversion, sans nom d'entité ni de fluide codé en dur.
        """
        conversions: dict[str, dict] = {}
        for name, entry in self.entities.items():
            boxes = entry.get("fluidboxes")
            detail = boxes.get("detail") if isinstance(boxes, dict) else None
            if not isinstance(detail, dict):
                continue
            inputs: list[str] = []
            outputs: list[str] = []
            for box in detail.values():
                if not isinstance(box, dict) or not box.get("filter"):
                    continue
                kind = box.get("production_type")
                if kind == "input":
                    inputs.append(str(box["filter"]))
                elif kind == "output":
                    outputs.append(str(box["filter"]))
            if len(outputs) == 1 and inputs:
                conversions.setdefault(
                    outputs[0], {"entity": name, "inputs": inputs}
                )
        return conversions

    def _convert_fluid(
        self, item: str, amount: float, stack: tuple[str, ...] = ()
    ) -> bool:
        conversion = self.fluid_conversions.get(item)
        if conversion is None:
            return False
        self.used_buildings.add(conversion["entity"])
        for fluid in conversion["inputs"]:
            self._require(fluid, amount, stack + (item,))
        self.produced[item] += amount
        self.inv[item] += amount
        return True

    def _recipe_seconds(self, recipe: dict, crafts: int) -> float:
        crafted_in = recipe.get("crafted_in")
        speed = 1.0
        if crafted_in:
            speed = self.speeds.get(crafted_in, 1.0) or 1.0
        energy = float(recipe.get("energy", 0) or 0)
        return crafts * energy / speed

    def _craft(self, recipe: dict, crafts: int, stack: tuple[str, ...]) -> None:
        if crafts <= 0:
            return
        self.recipe_crafts[recipe["name"]] += crafts
        crafted_in = recipe.get("crafted_in")
        if crafted_in:
            self.used_buildings.add(crafted_in)
        seconds = self._recipe_seconds(recipe, crafts)
        self.total_craft_seconds += seconds
        for name, qty in _item_amounts(recipe.get("ingredients")):
            self._require(name, crafts * qty, stack)
        for name, qty in _item_amounts(recipe.get("results")):
            self.inv[name] += crafts * qty
            self.produced[name] += crafts * qty

    def _produce(self, item: str, amount: float, stack: tuple[str, ...] = ()) -> None:
        if amount <= 0:
            return
        if item in stack:
            self._supply_external(item, amount)
            return
        if item in self.raw_resources:
            if self._mine(item, amount):
                return
        # Fluide pompé depuis la carte : la source (pompe + fluide) vient du
        # dump (``pumped_fluid``), sans minage ni temps de craft.
        if item in self.fluids and self.fluid_sources.get(item):
            pump = sorted(self.fluid_sources[item])[0]
            self.used_buildings.add(pump)
            self.produced[item] += amount
            self.inv[item] += amount
            return
        recipe = self._choose(item, stack)
        if recipe is not None:
            per_craft = self._output_amount(recipe, item)
            crafts = math.ceil(amount / per_craft)
            self.crafts[item] += crafts
            seconds = self._recipe_seconds(recipe, crafts)
            self.craft_seconds[item] += seconds
            power = self._recipe_power_kw(recipe)
            self.energy_kj[item] += power * seconds
            self.power_kw[item] = max(self.power_kw[item], power)
            self._craft(recipe, crafts, stack + (item,))
            return
        if self._launch(item, amount, stack):
            return
        if self._convert_fluid(item, amount, stack):
            return
        # Ressource brute non minable et non convertible (bois ramassé…) :
        # fourniture externe.
        self._supply_external(item, amount)

    def _require(self, item: str, amount: float, stack: tuple[str, ...] = ()) -> None:
        """Consomme ``amount`` de ``item``, en produisant le manque au besoin."""
        if amount <= 0:
            return
        if item in stack:
            self.consumed[item] += amount
            self.external[item] += amount
            self.produced[item] += amount
            return
        remaining = float(amount)
        guard = 0
        while remaining > 1e-9:
            guard += 1
            if guard > 100000:
                break
            have = self.inv.get(item, 0.0)
            if have > 0:
                used = min(have, remaining)
                self.inv[item] = have - used
                self.consumed[item] += used
                remaining -= used
                continue
            before = self.produced.get(item, 0.0)
            self._produce(item, remaining, stack)
            if (
                self.produced.get(item, 0.0) <= before
                and self.inv.get(item, 0.0) <= 0
            ):
                self._supply_external(item, remaining)

    # -- technologies et déclencheurs ---------------------------------------

    def _resource_product(self, entity_name: str) -> str:
        entry = self.entities.get(entity_name)
        if entry:
            for name, _qty in _item_amounts(entry.get("mineable_products")):
                return name
        return entity_name

    def _rocket_parts_required(self) -> int | None:
        """Nombre de pièces par fusée : déclaré par le silo du dump.

        ``None`` si le dump ne le dit pas : sans cette donnée on ne lance
        pas (pas de valeur vanilla inventée).
        """
        for entry in self.entities.values():
            if entry.get("type") == "rocket-silo":
                parts = entry.get("rocket_parts_required")
                if parts:
                    return int(parts)
        return None

    def _find_rocket_part(self) -> str | None:
        """Item fabriqué par le silo : recette de sa catégorie de craft."""
        silo = next(
            (
                name
                for name, entry in self.entities.items()
                if entry.get("type") == "rocket-silo"
            ),
            None,
        )
        if silo is None:
            return None
        for recipe in self.recipes:
            if recipe.get("crafted_in") != silo:
                continue
            results = [name for name, _qty in _item_amounts(recipe.get("results"))]
            if results:
                return results[0]
        return None

    def _launch_products(self, payload: str | None = None) -> list[tuple[str, int | float]]:
        """Produits d'un lancement déclarés par le dump (vide si absent).

        Source de vérité : l'ITEM lancé (``rocket_launch_products`` sur le
        prototype de l'item, ex. satellite). Repli : le prototype du silo."""
        if payload is not None:
            entry = self.items.get(payload) or {}
            products = _item_amounts(entry.get("rocket_launch_products"))
            if products:
                return products
        for entry in self.entities.values():
            if entry.get("type") != "rocket-silo":
                continue
            products = _item_amounts(entry.get("rocket_launch_products"))
            if products:
                return products
        return []

    def _launch(
        self, product: str, amount: float, stack: tuple[str, ...] = ()
    ) -> bool:
        """Produit ``product`` par lancement(s) de fusée.

        Le payload et le pack produit sont déduits du déclencheur
        ``send-item-to-orbit`` de la technologie correspondante. La quantité
        produite par lancement vient du dump (``rocket_launch_products`` de
        l'item lancé) : sans elle, on ne lance pas.
        """
        payload = self.launch_requirements.get(product)
        parts = self._rocket_parts_required()
        if payload is None or self.rocket_part is None or parts is None:
            return False
        per_launch = None
        for name, qty in self._launch_products(payload):
            if name == product and qty:
                per_launch = qty
                break
        if per_launch is None:
            return False
        launches = math.ceil(amount / per_launch)
        for _ in range(launches):
            self._require(self.rocket_part, parts, stack + (product,))
            self._require(payload, 1, stack + (product,))
        got = launches * per_launch
        self.produced[product] += got
        self.inv[product] += got
        self.crafts[product] += launches
        return True

    def _process_trigger(
        self, trigger: dict, tech_id: str | None = None
    ) -> None:
        kind = trigger.get("type")
        if kind == "mine-entity":
            for entity_name in trigger.get("entities") or []:
                product = self._resource_product(str(entity_name))
                self._produce(product, 1)
        elif kind == "craft-item":
            item = trigger.get("item")
            if item:
                self._produce(str(item), _amount(trigger.get("count", 1) or 1))
        elif kind == "send-item-to-orbit":
            payload = trigger.get("item")
            if payload:
                # Le déclencheur lance un payload : ses produits de lancement
                # déclarés par le dump sont produits, sans nom supposé.
                for product, qty in self._launch_products(str(payload)):
                    self._produce(str(product), _amount(qty or 1))

    def _process_tech(self, tech: dict) -> None:
        trigger = tech.get("research_trigger")
        if isinstance(trigger, dict) and trigger.get("type"):
            self._process_trigger(trigger, tech.get("id"))
            return
        unit = tech.get("unit") or {}
        try:
            count = int(unit.get("count", 0) or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            return
        self.used_buildings.add("lab")
        for name, qty in _item_amounts(unit.get("ingredients")):
            self._require(name, count * qty)

    def _craft_used_buildings(self) -> None:
        crafted: set[str] = set()
        for _ in range(100):
            pending = sorted(
                name
                for name in self.used_buildings
                if name in self.recipe_by_name and name not in crafted
            )
            if not pending:
                break
            for name in pending:
                crafted.add(name)
                self._produce(name, 1)
        self.buildings = sorted(crafted)

    # -- résultat -----------------------------------------------------------

    def _result(self) -> dict:
        keys = (
            set(self.produced)
            | set(self.consumed)
            | set(self.mined)
            | set(self.external)
            | set(self.crafts)
            | set(self.inv)
        )
        item_stats = {}
        for name in sorted(keys):
            item_stats[name] = {
                "mined": _number(self.mined.get(name, 0)),
                "mining_seconds": _number(self.mining_seconds.get(name, 0)),
                "produced": _number(self.produced.get(name, 0)),
                "consumed": _number(self.consumed.get(name, 0)),
                "crafts": int(self.crafts.get(name, 0)),
                "craft_seconds": _number(self.craft_seconds.get(name, 0)),
                "external": _number(self.external.get(name, 0)),
                "power_kw": _number(self.power_kw.get(name, 0)),
                "energy_kj": _number(self.energy_kj.get(name, 0)),
            }

        raw_resources = sorted(self.raw_resources)
        unused_raw = [name for name in raw_resources if name not in item_stats]
        locked = sorted(
            {
                recipe
                for recipe, tech in self.unlocked_by.items()
                if tech not in self.processed
            }
        )
        inventory_left = {
            name: _number(value)
            for name, value in self.inv.items()
            if value > 1e-9
        }
        return {
            "item_stats": item_stats,
            "total_raw": _number(sum(self.mined.values())),
            "mining_seconds": _number(sum(self.mining_seconds.values())),
            "external_items": sorted(self.external),
            "unknown_items": [],
            "inventory_left": inventory_left,
            "buildings": self.buildings,
            "locked_recipes": locked,
            "recipe_crafts": dict(sorted(self.recipe_crafts.items())),
            "raw_resources": raw_resources,
            "unused_raw_resources": unused_raw,
            "total_crafts": int(sum(self.recipe_crafts.values())),
            "total_produced": _number(sum(self.produced.values())),
            "total_consumed": _number(sum(self.consumed.values())),
            "total_craft_seconds": _number(self.total_craft_seconds),
        }

    def run(self) -> dict:
        for tech_id in self.progression:
            tech = self.tech_by_id.get(tech_id)
            if tech is None:
                continue
            self._process_tech(tech)
            self.processed.add(tech_id)
        self._craft_used_buildings()
        return self._result()


def analyze_playthrough(seed: dict, db: Any = None) -> dict:
    """Simule une partie complète sans carte et renvoie les statistiques.

    Contrairement à :func:`analyze_complexity`, l'inventaire est porté d'une
    technologie à l'autre : un sous-produit (huile lourde, uranium 238…) est
    réutilisé au lieu d'être recrafté, les déclencheurs de recherche (miner,
    crafter, lancer une fusée) sont simulés, et le craquage du pétrole réduit
    la consommation de brut.
    """
    return _Playthrough(seed, db).run()


__all__ = [
    "write_complexity_html",
    "render_complexity_html",
    "analyze_complexity",
    "analyze_playthrough",
]
