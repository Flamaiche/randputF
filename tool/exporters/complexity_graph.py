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
  faisait tous les crafts), temps de recherche total, profondeur maximale,
  temps critique de la chaîne de recettes, fabricateur le plus utilisé et
  ressource la plus consommée pendant la partie.

Le fichier est indépendant du témoin de déterminisme (il n'entre pas dans
le hash md5) et est régénéré à chaque export.
"""

from __future__ import annotations

import html as _html
import json
import math
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tool.audit.graph import Expansion, GraphAnalysis, analyze_graph, clean_number
from tool.exporters.html_ui import TIP_HTML, UI_CSS, UI_SCRIPT, th as _th

_Expansion = Expansion

# ---------------------------------------------------------------------------
# Vitesses de craft
# ---------------------------------------------------------------------------

HAND = "main"


def _progress_slice(
    on_progress: Callable[[int, str], None] | None, low: int, high: int
) -> Callable[[int, str], None] | None:
    if on_progress is None:
        return None
    span = high - low
    return lambda percent, detail: on_progress(low + percent * span // 100, detail)


def _format_steps(value: int) -> str:
    return f"{value:,}".replace(",", " ")


class _StepProgress:
    """Progression monotone d'une phase dont le nombre d'étapes est inconnu."""

    def __init__(
        self,
        on_progress: Callable[[int, str], None] | None,
        low: int,
        high: int,
        detail: str,
        interval: float = 0.15,
    ) -> None:
        self.on_progress = on_progress
        self.low = low
        self.high = high
        self.detail = detail
        self.value = low
        self.steps = 0
        self.checked = 0
        self.interval = interval
        self.last = time.monotonic()
        self.position = ""

    def tick(
        self,
        item: str = "",
        amount: int = 0,
        stack: tuple[str, ...] = (),
        max_depth: int = 0,
    ) -> None:
        if self.on_progress is None:
            return
        self.steps += 1
        self.checked += 1
        if item:
            path = " → ".join((*stack[-3:], item))
            depth = min(len(stack) + 1, max_depth)
            self.position = (
                f"profondeur {depth}/{max_depth} · {path} · {_format_steps(amount)} unités"
            )
        if self.checked < 64:
            return
        self.checked = 0
        now = time.monotonic()
        if now - self.last < self.interval:
            return
        self.last = now
        if self.value < self.high:
            self.value += 1
        label = f"{self.detail} · {_format_steps(self.steps)} étapes"
        if self.position:
            label += f" · {self.position}"
        self.on_progress(self.value, label)

    def done(self) -> None:
        if self.on_progress is not None:
            label = f"{self.detail} · {_format_steps(self.steps)} étapes"
            if self.position:
                label += f" · {self.position}"
            self.on_progress(self.high, label)


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
    """Consommation cumulée d'un dépliage de recettes.

    ``crafts`` compte les crafts par recette, ``raw`` les ressources brutes consommées, ``buildings`` les bâtiments utilisés, ``hand_crafts``/``machine_seconds`` les temps associés et ``unknown`` les items sans recette. Sert à agréger plusieurs branches d'un même calcul.
    """

    crafts: Counter = field(default_factory=Counter)
    raw: Counter = field(default_factory=Counter)
    buildings: Counter = field(default_factory=Counter)
    hand_crafts: int = 0
    machine_seconds: float = 0.0
    unknown: set[str] = field(default_factory=set)

    def add(self, other: "_Expansion") -> None:
        """Fusionne les compteurs d'une autre expansion dans celle-ci.

        Utilisé pour agréger plusieurs branches de recettes sans perdre les
        temps machine, les crafts à la main ni les items inconnus.
        """
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
        """Indexe les recettes par nom et par produit.

        Aucun choix de recette n'est figé ici : :meth:`chosen` décide ensuite
        de façon déterministe, ce qui garde le résultat indépendant de l'ordre
        des recettes dans le JSON.
        """
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
        """Retourne la recette retenue pour produire ``item``, ou ``None``.

        Le choix privilégie une recette homonyme, puis une recette hors
        variantes ``ease``, puis l'ordre alphabétique. Le résultat est mémorisé
        pour éviter de recalculer le tri à chaque dépliage.
        """
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
        """Quantité de ``item`` produite par un craft de ``recipe``.

        Retourne 1 quand le dump ne déclare aucune quantité exploitable, pour
        éviter une division par zéro dans le calcul du nombre de crafts.
        """
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
    tick: Callable[[str, int, tuple[str, ...], int], None] | None = None,
) -> None:
    """Ajoute à ``exp`` ce qu'il faut pour produire ``amount`` unités de ``item``.

    ``index`` fournit les recettes, ``speeds`` les vitesses machines, ``terminal`` les produits considérés bruts, ``stack`` la pile de récursion et ``max_depth`` la profondeur maximale. ``tick`` reçoit un signal à chaque étape de dépliage avec la position courante. Les cycles et les produits sans recette sont repliés en ressources brutes. Retourne ``None`` et mute ``exp``.
    """
    if tick is not None:
        tick(item, amount, stack, max_depth)
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
            tick=tick,
        )


# ---------------------------------------------------------------------------
# Analyse
# ---------------------------------------------------------------------------


def _tech_seconds(tech: dict) -> float:
    """Temps de recherche théorique d'une technologie.

    Il vaut ``unit.count × unit.time`` ; les valeurs absentes ou invalides
    sont ramenées à zéro pour ne jamais fausser les totaux.
    """
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
    """Retourne les packs de science exigés par une technologie.

    ``tech`` est la fiche du seed ; le résultat est une liste de couples ``(nom, quantité totale)`` calculée comme ``unit.count × amount``. Une unité absente ou invalide donne une liste vide.
    """
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


def _counter_delta(
    previous: dict[str, Any], current: dict[str, Any]
) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in set(previous) | set(current):
        delta = float(current.get(name, 0) or 0) - float(previous.get(name, 0) or 0)
        if delta > 0:
            out[name] = delta
    return out


def _format_seconds(value: float) -> str:
    """Formate une durée en ``mm:ss``, ``h:mm:ss`` ou unités plus lisibles.

    ``value`` est un nombre de secondes (négatif ramené à zéro). Retourne la chaîne destinée à l'affichage HTML, sans dépendance externe.
    """
    seconds = max(0, int(round(value)))
    hours, rest = divmod(seconds, 3600)
    minutes, sec = divmod(rest, 60)
    if hours:
        if hours < 24:
            return f"{hours}:{minutes:02d}:{sec:02d}"
        days = seconds / 86400
        years = days / 365.2425
        if years >= 1_000_000:
            formatted = f"{years / 1_000_000:,.1f} M d'années"
        elif years >= 1_000:
            formatted = f"{years / 1_000:,.1f} k ans"
        elif years >= 1:
            formatted = f"{years:,.1f} ans"
        else:
            formatted = f"{days:,.1f} j"
        return formatted.replace(",", " ").replace(".", ",")
    return f"{minutes}:{sec:02d}"


def _format_number(value: float) -> str:
    """Formate un nombre pour les graphiques.

    Le séparateur de milliers est une espace et le nombre de décimales
    s'adapte à l'ordre de grandeur pour garder des graduations lisibles.
    """
    if value >= 100:
        return f"{value:,.0f}".replace(",", " ")
    if value >= 10:
        return f"{value:,.1f}".replace(",", " ").replace(".0", "")
    return f"{value:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def _format_ratio(value: Any, reference: Any) -> str | None:
    try:
        current = float(value)
        base = float(reference)
    except (TypeError, ValueError):
        return None
    if base <= 0:
        return None
    ratio = current / base
    if ratio >= 1000:
        text = f"{ratio:,.0f}"
    elif ratio >= 100:
        text = f"{ratio:.0f}"
    elif ratio >= 10:
        text = f"{ratio:.1f}"
    elif ratio >= 0.01:
        text = f"{ratio:.2f}"
    else:
        text = f"{ratio:.4f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "×" + text.replace(",", " ").replace(".", ",")


def _length_fields(analysis: GraphAnalysis | None) -> dict:
    axes = {}
    if analysis is not None:
        profile = analysis.profile or {}
        axes = profile.get("raw_axes") or profile.get("axes") or {}
    depth = (axes.get("structure") or {}).get("depth")
    critical = (axes.get("critical") or {}).get("critical_seconds")
    return {
        "chain_depth": clean_number(depth) if depth is not None else None,
        "critical_seconds": clean_number(critical) if critical is not None else None,
        "critical_label": (
            _format_seconds(float(critical)) if critical is not None else None
        ),
    }


def _complexity_from_playthrough(
    seed: dict,
    playthrough: dict,
    on_progress: Callable[[int, str], None] | None = None,
    *,
    graph: GraphAnalysis | None = None,
) -> dict:
    if on_progress is not None:
        on_progress(0, "complexité depuis la simulation")
    rows = playthrough["rows"]
    resource_counter = Counter(
        {name: float(value) for name, value in (playthrough.get("resources") or {}).items()}
    )
    building_counter = Counter(
        {name: int(value) for name, value in (playthrough.get("buildings") or {}).items()}
    )
    total_research = sum(float(row.get("research_time", 0) or 0) for row in rows)
    total_craft_seconds = sum(float(row.get("craft_seconds", 0) or 0) for row in rows)
    total_packs = sum(int(row.get("packs", 0) or 0) for row in rows)
    total_crafts = sum(float(row.get("crafts", 0) or 0) for row in rows)
    hand_crafts = sum(float(row.get("hand_crafts", 0) or 0) for row in rows)
    total_raw = sum(resource_counter.values())
    distinct_buildings = len(building_counter)
    complexity_score = (
        total_research + total_craft_seconds + 0.5 * total_packs + 10 * distinct_buildings
    )
    building_usage = [
        (name, clean_number(value)) for name, value in building_counter.most_common()
    ]
    resource_usage = [
        (name, clean_number(value)) for name, value in resource_counter.most_common()
    ]
    if on_progress is not None:
        on_progress(100, "complexité depuis la simulation terminée")
    return {
        "seed_value": (seed.get("meta") or {}).get("seed", "?"),
        "generator_version": (seed.get("meta") or {}).get("generator_version", "?"),
        "tech_count": len(rows),
        "free_count": len(seed.get("free_researches") or []),
        "total_research_seconds": round(total_research, 2),
        "total_research_label": _format_seconds(total_research),
        "total_craft_seconds": round(total_craft_seconds, 2),
        "total_craft_label": _format_seconds(total_craft_seconds),
        "total_packs": total_packs,
        "total_raw": clean_number(total_raw),
        "total_crafts": clean_number(total_crafts),
        "hand_crafts": clean_number(hand_crafts),
        "complexity_score": round(complexity_score, 1),
        "distinct_buildings": distinct_buildings,
        "most_used_fabricator": building_usage[0][0] if building_usage else None,
        "most_used_fabricator_crafts": building_usage[0][1] if building_usage else 0,
        "most_used_resource": resource_usage[0][0] if resource_usage else None,
        "most_used_resource_amount": resource_usage[0][1] if resource_usage else 0,
        "building_usage": building_usage,
        "resource_usage": resource_usage,
        "unknown_terminals": playthrough.get("unknown_terminals", []),
        "tech_rows": rows,
        **_length_fields(graph),
    }


def analyze_complexity(
    seed: dict,
    db: Any = None,
    on_progress: Callable[[int, str], None] | None = None,
    *,
    graph: GraphAnalysis | None = None,
    playthrough: dict | None = None,
) -> dict:
    """Calcule le rapport de complexité complet d'une seed."""
    if playthrough is not None and playthrough.get("rows"):
        return _complexity_from_playthrough(
            seed, playthrough, on_progress, graph=graph
        )
    analysis = graph if graph is not None else analyze_graph(seed, db, on_progress)
    free = set(seed.get("free_researches") or [])
    tech_by_id = {t.get("id"): t for t in seed.get("technologies") or [] if t.get("id")}

    def clean_counter(counter: Counter) -> list[tuple[str, Any]]:
        return [(name, clean_number(value)) for name, value in counter.most_common()]

    global_exp = Expansion()
    tech_rows: list[dict] = []
    seen_buildings: set[str] = set()
    cumulative = {
        "time": 0.0,
        "packs": 0,
        "raw": 0.0,
        "craft_seconds": 0.0,
        "crafts": 0.0,
    }

    for position, tech_id in enumerate(analysis.progression, start=1):
        tech = tech_by_id.get(tech_id)
        if not tech:
            continue
        tech_exp = analysis.tech_expansions.get(tech_id, Expansion())
        global_exp.add(tech_exp)
        packs = [
            {"name": name, "amount": amount}
            for name, amount in _science_requirements(tech)
        ]
        pack_total = sum(pack["amount"] for pack in packs)
        research_time = _tech_seconds(tech)
        raw_total = sum(tech_exp.raw.values())
        buildings = set(tech_exp.buildings)
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
                "raw_total": clean_number(raw_total),
                "buildings": sorted(buildings),
                "building_count": len(buildings),
                "ratio": round(ratio, 2),
                "crafts": clean_number(crafts_total),
                "craft_seconds": round(tech_exp.machine_seconds, 2),
                "hand_crafts": clean_number(tech_exp.hand_crafts),
                "cumulative_time": round(cumulative["time"], 2),
                "cumulative_packs": cumulative["packs"],
                "cumulative_raw": clean_number(cumulative["raw"]),
                "cumulative_buildings": len(seen_buildings),
                "cumulative_craft_seconds": round(cumulative["craft_seconds"], 2),
                "cumulative_crafts": clean_number(cumulative["crafts"]),
                "cumulative_score": round(cumulative_score, 2),
            }
        )

    total_research = cumulative["time"]
    total_craft_seconds = global_exp.machine_seconds
    total_packs = cumulative["packs"]
    total_raw = sum(global_exp.raw.values())
    distinct_buildings = len(global_exp.buildings)
    total_crafts = sum(global_exp.crafts.values()) + global_exp.hand_crafts
    complexity_score = (
        total_research + total_craft_seconds + 0.5 * total_packs + 10 * distinct_buildings
    )
    building_usage = clean_counter(global_exp.buildings)
    resource_usage = clean_counter(global_exp.raw)

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
        "total_raw": clean_number(total_raw),
        "total_crafts": clean_number(total_crafts),
        "hand_crafts": clean_number(global_exp.hand_crafts),
        "complexity_score": round(complexity_score, 1),
        "distinct_buildings": distinct_buildings,
        "most_used_fabricator": building_usage[0][0] if building_usage else None,
        "most_used_fabricator_crafts": building_usage[0][1] if building_usage else 0,
        "most_used_resource": resource_usage[0][0] if resource_usage else None,
        "most_used_resource_amount": resource_usage[0][1] if resource_usage else 0,
        "building_usage": building_usage,
        "resource_usage": resource_usage,
        "unknown_terminals": analysis.unknown,
        "tech_rows": tech_rows,
        **_length_fields(analysis),
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
    """Construit un graphique ligne SVG d'une série par technologie.

    ``title`` est le titre, ``values``/``labels`` les points et leurs abscisses, ``color`` la couleur de la ligne et ``cumulative_label`` l'étiquette de la série cumulée. Retourne le fragment SVG complet (viewBox 1000×260).
    """
    plot_w = _W - _ML - _MR
    plot_h = _H - _MT - _MB
    count = len(values)
    top = max(values) if values else 0
    top = top if top > 0 else 1
    top *= 1.08

    def px(index: int) -> float:
        """Retourne la position horizontale SVG d'un point.

        ``index`` est l'indice du point dans la série ; le résultat est réparti linéairement entre les marges du graphique. Un seul point est centré.
        """
        if count <= 1:
            return _ML + plot_w / 2
        return _ML + (index / (count - 1)) * plot_w

    def py(value: float) -> float:
        """Retourne la position verticale SVG d'une valeur.

        ``value`` est la mesure à placer ; l'échelle est fixée par le maximum de la série et les marges du graphique. Retourne un ``float`` en coordonnées SVG.
        """
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


def _bar_list(
    title: str,
    rows: list[tuple[str, float]],
    color: str,
    baseline: dict[str, float] | None = None,
    baseline_label: str = "vanilla",
) -> str:
    """Génère un classement en barres horizontales pour la complexité.

    Les barres sont normalisées sur la plus grande valeur et affichent la
    valeur formatée à droite.
    """
    if not rows:
        return f'<p class="muted">{_html.escape(title)} : aucune donnée.</p>'
    top = max(value for _, value in rows) or 1
    references = baseline or {}
    items = []
    for name, value in rows:
        width = max(2.0, (value / top) * 100)
        ratio = _format_ratio(value, references.get(name)) if references else None
        ratio_html = (
            f'<span class="ratio"> {ratio} {_html.escape(baseline_label)}</span>'
            if ratio
            else ""
        )
        items.append(
            '<div class="bar-row">'
            f'<div class="bar-name">{_html.escape(name)}</div>'
            f'<div class="bar-bg"><div class="bar-fill" '
            f'style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="bar-val">{_html.escape(_format_number(value))}{ratio_html}</div>'
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
.ratio{color:var(--accent);font-variant-numeric:tabular-nums}
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


def _stat(
    lab: str,
    val: str,
    cls: str = "",
    hint: str = "",
    ratio: str | None = None,
    baseline_label: str = "vanilla",
) -> str:
    """Génère une tuile du bandeau de statistiques de complexité.

    ``cls`` choisit la couleur de la valeur et ``hint`` ajoute une infobulle
    discrète sous celle-ci.
    """
    parts = []
    if hint:
        parts.append(_html.escape(hint))
    if ratio:
        parts.append(
            f'<span class="ratio">{ratio} {_html.escape(baseline_label)}</span>'
        )
    hint_html = f'<div class="hint">{" · ".join(parts)}</div>' if parts else ""
    return (
        f'<div class="stat"><div class="lab">{_html.escape(lab)}</div>'
        f'<div class="val {cls}">{_html.escape(val)}</div>{hint_html}</div>'
    )


def render_complexity_html(
    seed: dict,
    db: Any = None,
    *,
    title: str | None = None,
    data: dict | None = None,
    graph: GraphAnalysis | None = None,
    baseline: dict | None = None,
    baseline_label: str = "vanilla",
    on_progress: Callable[[int, str], None] | None = None,
) -> str:
    """Rend le rapport de complexité autonome d'une seed."""
    if data is None:
        data = analyze_complexity(
            seed,
            db,
            graph=graph,
            on_progress=_progress_slice(on_progress, 0, 70),
        )
    rows = data["tech_rows"]
    labels = [str(row["num"]) for row in rows]
    chain_depth = data.get("chain_depth")
    critical_label = data.get("critical_label")
    reference = baseline or {}

    def ratio(field: str) -> str | None:
        return _format_ratio(data.get(field), reference.get(field)) if reference else None

    header_stats = "".join(
        [
            _stat(
                "Score de complexité",
                _format_number(data["complexity_score"]),
                "bad",
                ratio=ratio("complexity_score"),
                baseline_label=baseline_label,
            ),
            _stat(
                "Temps de craft total",
                data["total_craft_label"],
                "acc",
                "somme des crafts, 1 machine",
                ratio("total_craft_seconds"),
                baseline_label,
            ),
            _stat(
                "Temps de recherche",
                data["total_research_label"],
                "acc",
                "toutes les techs",
                ratio("total_research_seconds"),
                baseline_label,
            ),
            _stat(
                "Packs de science",
                _format_number(data["total_packs"]),
                "acc",
                ratio=ratio("total_packs"),
                baseline_label=baseline_label,
            ),
            _stat(
                "Profondeur max",
                _format_number(chain_depth) if chain_depth is not None else "—",
                "acc",
                "chaîne de recettes la plus longue",
                ratio("chain_depth"),
                baseline_label,
            ),
            _stat(
                "Temps critique",
                critical_label or "—",
                "warn",
                "machine la plus lente de la chaîne",
                ratio("critical_seconds"),
                baseline_label,
            ),
            _stat(
                "Fabricateur le plus utilisé",
                data["most_used_fabricator"] or "—",
                "ok",
                f"{_format_number(data['most_used_fabricator_crafts'])} crafts",
                ratio("most_used_fabricator_crafts"),
                baseline_label,
            ),
            _stat(
                "Ressource la plus consommée",
                data["most_used_resource"] or "—",
                "warn",
                f"{_format_number(data['most_used_resource_amount'])} unités",
                ratio("most_used_resource_amount"),
                baseline_label,
            ),
        ]
    )

    chart_specs = [
        ("Temps de recherche par tech (s)", [r["research_time"] for r in rows], "#5c6bc0"),
        ("Ressources brutes par tech", [r["raw_total"] for r in rows], "#29b6f6"),
        ("Ateliers de fabrication distincts par tech", [r["building_count"] for r in rows], "#4caf50"),
        ("Ratio ressources / atelier par tech", [r["ratio"] for r in rows], "#ff9800"),
        ("Score de complexité cumulé", [r["cumulative_score"] for r in rows], "#6f6fe6"),
        ("Crafts cumulés", [r["cumulative_crafts"] for r in rows], "#26a69a"),
    ]
    chart_parts: list[str] = []
    for position, (title, values, color) in enumerate(chart_specs, start=1):
        chart_parts.append(
            f'<div class="card">{_chart_svg(title, values, labels, color)}</div>'
        )
        if on_progress is not None:
            on_progress(
                70 + position * 5 // len(chart_specs), "graphiques de complexité"
            )
    charts = "".join(chart_parts)

    baseline_buildings = dict(reference.get("building_usage") or [])
    baseline_resources = dict(reference.get("resource_usage") or [])
    building_rows = _bar_list(
        "Ateliers les plus utilisés (crafts)",
        data["building_usage"][:12],
        "var(--accent)",
        baseline_buildings if reference else None,
        baseline_label,
    )
    resource_rows = _bar_list(
        "Ressources brutes les plus consommées",
        data["resource_usage"][:12],
        "var(--hl5)",
        baseline_resources if reference else None,
        baseline_label,
    )

    table_rows = []
    total_rows = max(1, len(rows))
    for position, row in enumerate(rows, start=1):
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
        if on_progress is not None:
            on_progress(75 + position * 25 // total_rows, "tableau de complexité")
    if on_progress is not None:
        on_progress(100, "complexité prête")

    unknown_note = ""
    if data["unknown_terminals"]:
        names = ", ".join(_html.escape(n) for n in data["unknown_terminals"])
        unknown_note = (
            '<div class="note">Ingrédients sans recette ni ressource brute '
            f"(traités comme bruts) : {names}</div>"
        )
    comparison_note = ""
    if reference:
        comparison_note = (
            "<div class='note'>Les « ×N » comparent chaque valeur à "
            f"{_html.escape(baseline_label)}. Pour le profil de difficulté, "
            "les volumes et temps sont comparés en échelle logarithmique : "
            "le ratio affiché mesure l'écart de difficulté, pas le rapport brut.</div>"
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
        "<section id='complexite-courbes'><h2>Courbes par technologie</h2>"
        f"<div class='charts'>{charts}</div>"
        f"{comparison_note}"
        "<div class='note'>Le temps de craft total est la somme des temps de "
        "tous les crafts nécessaires pour tous les packs de science, comme si "
        "une seule machine les enchaînait. La profondeur max est la chaîne de "
        "recettes la plus longue ; le temps critique est le temps machine de "
        "cette chaîne la plus lente, sans parallélisme ni attente réelle. Le "
        "score ajoute le temps de recherche, 0,5 × packs et 10 × ateliers "
        "distincts.</div></section>"
        "<section id='complexite-ateliers'><div class='two'>"
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


def write_complexity_html(
    seed: dict,
    path: Path,
    db: Any = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> None:
    """Écrit le rapport de complexité d'une seed dans ``path``.

    ``seed`` est la seed, ``path`` le fichier HTML de sortie et ``db`` une base optionnelle. ``on_progress`` est transmis au rendu. Crée/écrase le fichier et retourne ``None``.
    """
    document = render_complexity_html(seed, db, on_progress=on_progress)
    path.write_text(document, encoding="utf-8")


# ---------------------------------------------------------------------------
# Joueur simulé (partie sans map)
# ---------------------------------------------------------------------------

# ``energy_usage`` du dump est en joules par tick (60 ticks/s) : J/tick × 60 / 1000.
_ENERGY_KW_FACTOR = 0.06
_ITEM_AMOUNTS_CACHE: dict[int, tuple[Any, tuple[tuple[str, int | float], ...]]] = {}
_ITEM_AMOUNTS_CACHE_LIMIT = 200_000


def _amount(value: Any) -> int | float:
    """Convertit un montant du dump en nombre exploitable.

    ``value`` peut être un nombre ou une chaîne ; retourne un ``int`` quand la valeur est entière, sinon un ``float``. Une valeur absente ou invalide donne ``0``.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return number


def _item_amounts(entries: Any) -> tuple[tuple[str, int | float], ...]:
    """Convertit des entrées ``{name, amount}`` du dump en couples exploitables.

    Les entrées sans nom sont ignorées et les quantités passent par
    :func:`_amount`, qui normalise les valeurs numériques du dump.
    """
    key = id(entries)
    cached = _ITEM_AMOUNTS_CACHE.get(key)
    if cached is not None and cached[0] is entries:
        return cached[1]
    out: list[tuple[str, int | float]] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        out.append((str(name), _amount(entry.get("amount", 0))))
    result = tuple(out)
    if len(_ITEM_AMOUNTS_CACHE) >= _ITEM_AMOUNTS_CACHE_LIMIT:
        _ITEM_AMOUNTS_CACHE.clear()
    _ITEM_AMOUNTS_CACHE[key] = (entries, result)
    return result


def _number(value: Any) -> int | float:
    """Arrondit une mesure pour l'affichage.

    ``value`` est convertie en ``float`` ; retourne un ``int`` si la valeur est entière à 1e-9 près, sinon un ``float`` arrondi à trois décimales.
    """
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

    def __init__(
        self,
        seed: dict,
        db: Any = None,
        on_progress: Callable[[int, str], None] | None = None,
    ) -> None:
        """Prépare l'état complet de la simulation.

        L'index recense recettes, producteurs, entités, fluides, sources
        pompées, conversions, technologies, déblocages, gisements, foreuses et
        compteurs. ``on_progress`` reçoit un pourcentage pendant :meth:`run`.
        Aucune ressource n'est produite ici : :meth:`run` déroule ensuite la
        progression technologique.
        """
        self.seed = seed
        self.db = db
        self.on_progress = on_progress
        self.progress_step: _StepProgress | None = None
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
        # Fluides pompés déclarés par l'extracteur (``pumped_fluid`` ou
        # ensemble canonique ``pumped_fluids`` fourni par mod-data).
        self.fluid_sources: dict[str, list[str]] = defaultdict(list)
        for name, entry in self.entities.items():
            pumped = entry.get("pumped_fluid")
            if pumped:
                self.fluid_sources[str(pumped)].append(name)
            for fluid in entry.get("pumped_fluids") or ():
                if str(fluid) != pumped:
                    self.fluid_sources[str(fluid)].append(name)
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
        self.recipe_ingredients = {
            recipe["name"]: set(self._ingredient_names(recipe)) for recipe in self.recipes
        }
        self._recipe_choices: dict[tuple[str, int], list[dict]] = {}
        self._recipe_choice_version = 0
        self._output_amounts: dict[tuple[str, str], int | float] = {}
        self._recipe_seconds_per_craft: dict[str, float] = {}
        self._power_by_building: dict[str, float] = {}
        self._power_by_recipe: dict[str, float] = {}
        self._drills_by_category: dict[Any, dict | None] = {}
        self._mine_sources: dict[str, tuple[dict, dict | None] | None] = {}
        self._rocket_parts_cache: tuple[int | None] | None = None

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
        self.building_crafts: dict[str, int] = defaultdict(int)
        self.hand_crafts = 0
        self.complexity_rows: list[dict] = []
        self.complexity_resources: dict[str, float] = defaultdict(float)
        self.complexity_buildings: dict[str, int] = defaultdict(int)
        self.complexity_cumulative = {
            "time": 0.0,
            "packs": 0,
            "raw": 0.0,
            "craft_seconds": 0.0,
            "crafts": 0.0,
        }
        self.complexity_seen_buildings: set[str] = set()

    # -- disponibilité des recettes -----------------------------------------

    def _is_available(self, recipe_name: str) -> bool:
        """Indique si une recette est accessible à ce stade de la partie.

        Une recette sans technologie de déblocage est toujours disponible ;
        sinon, sa technologie doit déjà figurer dans ``processed``.
        """
        tech = self.unlocked_by.get(recipe_name)
        return tech is None or tech in self.processed

    @staticmethod
    def _ingredient_names(recipe: dict) -> set[str]:
        """Retourne l'ensemble des noms d'ingrédients d'une recette.

        ``recipe`` est une fiche du seed ; les entrées sans nom sont ignorées. Sert à détecter les cycles avant de choisir une recette.
        """
        return {name for name, _qty in _item_amounts(recipe.get("ingredients"))}

    def _choose(self, item: str, stack: tuple[str, ...]) -> dict | None:
        """Choisit la meilleure recette disponible pour produire ``item``.

        Les recettes qui créeraient un cycle sont écartées quand une
        alternative existe. À défaut, on privilégie l'homonyme, puis les
        recettes hors variantes ``ease``, puis l'ordre alphabétique.
        """
        key = (item, self._recipe_choice_version)
        candidates = self._recipe_choices.get(key)
        if candidates is None:
            candidates = sorted(
                (
                    r
                    for r in self.producers.get(item, [])
                    if self._is_available(r["name"])
                ),
                key=lambda r: (r["name"] != item, "ease" in r["name"], r["name"]),
            )
            self._recipe_choices[key] = candidates
        if not candidates:
            return None
        stack_set = set(stack)
        for recipe in candidates:
            names = self.recipe_ingredients.get(recipe["name"], set())
            if item not in names and not stack_set.intersection(names):
                return recipe
        return candidates[0]

    @staticmethod
    def _output_amount(recipe: dict, item: str) -> int | float:
        """Retourne la quantité de ``item`` produite par un craft.

        ``recipe`` est la fiche de recette et ``item`` le nom recherché. Additionne les résultats correspondants et retourne au moins ``1`` pour éviter une division par zéro.
        """
        total: int | float = 0
        for name, qty in _item_amounts(recipe.get("results")):
            if name == item:
                total += qty
        return total or 1

    # -- minage --------------------------------------------------------------

    def _building_power_kw(self, name: str | None) -> float:
        """Retourne la puissance électrique d'un bâtiment en kW.

        ``name`` est le nom de l'entité ; la valeur vient du dump ou, à défaut, de ``self.db``. Une puissance absente ou invalide donne ``0.0``.
        """
        if not name:
            return 0.0
        if name not in self._power_by_building:
            entry = self.entities.get(name) or {}
            usage = entry.get("energy_usage")
            if usage is None and self.db is not None:
                buildings = getattr(self.db, "buildings", None) or {}
                usage = getattr(buildings.get(name), "energy_usage", None)
            try:
                self._power_by_building[name] = float(usage) * _ENERGY_KW_FACTOR
            except (TypeError, ValueError):
                self._power_by_building[name] = 0.0
        return self._power_by_building[name]

    def _recipe_power_kw(self, recipe: dict) -> float:
        """Retourne la puissance électrique du bâtiment qui exécute ``recipe``.

        ``recipe`` porte ``crafted_in`` ; la conversion J/tick → kW est déléguée à ``_building_power_kw``. Retourne ``0.0`` si le bâtiment est inconnu.
        """
        name = recipe["name"]
        if name not in self._power_by_recipe:
            self._power_by_recipe[name] = self._building_power_kw(
                recipe.get("crafted_in")
            )
        return self._power_by_recipe[name]

    def _best_drill(self, category: Any) -> dict | None:
        """Sélectionne la foreuse la plus rapide pour une catégorie de ressource.

        Les foreuses incompatibles sont ignorées ; à vitesse égale, le nom
        alphabétique départage pour garder un résultat déterministe.
        """
        if category not in self._drills_by_category:
            best = None
            for drill in self.drills:
                if category and category not in drill["categories"]:
                    continue
                if (
                    best is None
                    or drill["speed"] > best["speed"]
                    or (
                        drill["speed"] == best["speed"]
                        and drill["name"] < best["name"]
                    )
                ):
                    best = drill
            self._drills_by_category[category] = best
        return self._drills_by_category[category]

    def _mine(self, item: str, amount: float) -> bool:
        """Extrait ``amount`` d'une ressource minable.

        Le meilleur gisement (rendement puis nom) et la meilleure foreuse sont
        choisis depuis le dump. L'inventaire, la production, le temps de
        minage et l'énergie sont mis à jour. Retourne ``False`` si aucun
        gisement ne produit cet item.
        """
        if item not in self._mine_sources:
            sources = self.mineables.get(item) or []
            if not sources:
                self._mine_sources[item] = None
                return False
            source = sorted(sources, key=lambda s: (-s["yield"], s["name"]))[0]
            # Sans catégorie de forage (arbre récolté à la main) : aucune foreuse,
            # vitesse de base 1.
            drill = (
                self._best_drill(source["category"]) if source["category"] else None
            )
            self._mine_sources[item] = (source, drill)
        choice = self._mine_sources[item]
        if choice is None:
            return False
        source, drill = choice
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
        """Comptabilise une fourniture hors chaîne de craft.

        Pompage, récolte ou orbite : la quantité est marquée comme produite
        et ajoutée à l'inventaire sans recette ni minage.
        """
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
        """Produit un fluide par conversion déclarée par les fluidboxes.

        Les fluides d'entrée sont consommés récursivement. Retourne ``False``
        si aucune conversion connue ne produit ``item``.
        """
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
        """Temps machine nécessaire pour ``crafts`` exécutions d'une recette.

        La vitesse du bâtiment est lue dans les prototypes ; un craft à la main
        utilise une vitesse de 1.
        """
        name = recipe["name"]
        per_craft = self._recipe_seconds_per_craft.get(name)
        if per_craft is None:
            crafted_in = recipe.get("crafted_in")
            speed = 1.0
            if crafted_in:
                speed = self.speeds.get(crafted_in, 1.0) or 1.0
            energy = float(recipe.get("energy", 0) or 0)
            per_craft = energy / speed
            self._recipe_seconds_per_craft[name] = per_craft
        return crafts * per_craft

    def _craft(self, recipe: dict, crafts: int, stack: tuple[str, ...]) -> None:
        """Exécute ``crafts`` fois une recette.

        Les ingrédients sont consommés, les produits ajoutés à l'inventaire et
        les compteurs de crafts, de temps et de bâtiments utilisés sont mis à
        jour.
        """
        if crafts <= 0:
            return
        self.recipe_crafts[recipe["name"]] += crafts
        crafted_in = recipe.get("crafted_in")
        if crafted_in:
            self.used_buildings.add(crafted_in)
            self.building_crafts[crafted_in] += crafts
        else:
            self.hand_crafts += crafts
        seconds = self._recipe_seconds(recipe, crafts)
        self.total_craft_seconds += seconds
        for name, qty in _item_amounts(recipe.get("ingredients")):
            self._require(name, crafts * qty, stack)
        for name, qty in _item_amounts(recipe.get("results")):
            self.inv[name] += crafts * qty
            self.produced[name] += crafts * qty

    def _produce(self, item: str, amount: float, stack: tuple[str, ...] = ()) -> None:
        """Produit ``item`` par la première voie applicable.

        L'ordre est : ressource minable, fluide pompé, recette débloquée,
        lancement de fusée, conversion de fluide, puis fourniture externe.
        Tous les compteurs de simulation sont mis à jour au passage.
        """
        if self.progress_step is not None:
            self.progress_step.tick()
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
            amount_key = (recipe["name"], item)
            per_craft = self._output_amounts.get(amount_key)
            if per_craft is None:
                per_craft = self._output_amount(recipe, item)
                self._output_amounts[amount_key] = per_craft
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
        """Consomme ``amount`` de ``item`` en produisant le manque.

        ``item`` est le nom, ``amount`` la quantité et ``stack`` la pile de récursion. Puise d'abord dans l'inventaire, puis produit ou fournit en externe ; les compteurs de consommation/production sont mis à jour. Retourne ``None``.
        """
        if self.progress_step is not None:
            self.progress_step.tick()
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
        """Nom du produit minable associé à une entité.

        Si le dump ne déclare pas de produit minable, le nom de l'entité est
        renvoyé pour conserver un identifiant exploitable.
        """
        entry = self.entities.get(entity_name)
        if entry:
            for name, _qty in _item_amounts(entry.get("mineable_products")):
                return name
        return entity_name

    def _rocket_parts_required(self) -> int | None:
        """Nombre de pièces par fusée : déclaré par un bâtiment du dump.

        ``None`` si aucun bâtiment ne le dit : sans cette donnée on ne lance
        pas (pas de valeur vanilla inventée).
        """
        if self._rocket_parts_cache is None:
            parts = [
                int(entry["rocket_parts_required"])
                for entry in self.entities.values()
                if entry.get("rocket_parts_required")
            ]
            self._rocket_parts_cache = (max(parts) if parts else None,)
        return self._rocket_parts_cache[0]

    def _find_rocket_part(self) -> str | None:
        """Retourne l'item fabriqué par un bâtiment de lancement.

        Un bâtiment de lancement se reconnaît à ``rocket_parts_required`` ;
        ses recettes viennent de ``crafted_in`` ou de ses catégories de craft.
        Retourne le nom du produit ou ``None`` si le dump ne décrit pas cette
        chaîne.
        """
        for building, entry in self.entities.items():
            if not entry.get("rocket_parts_required"):
                continue
            categories = {str(c) for c in entry.get("crafting_categories") or ()}
            for recipe in self.recipes:
                crafted_in = recipe.get("crafted_in")
                if crafted_in != building and recipe.get("category") not in categories:
                    continue
                results = [
                    name for name, _qty in _item_amounts(recipe.get("results"))
                ]
                main_product = str(recipe.get("main_product") or "")
                if main_product in results:
                    return main_product
                if results:
                    return results[0]
        return None

    def _launch_products(self, payload: str | None = None) -> tuple[tuple[str, int | float], ...]:
        """Produits d'un lancement déclarés par le dump (vide si absent).

        Source de vérité : l'ITEM lancé (``rocket_launch_products`` sur le
        prototype de l'item, ex. satellite). Repli : une entité du dump qui
        déclare ces produits (bâtiment de lancement ou équivalent)."""
        if payload is not None:
            entry = self.items.get(payload) or {}
            products = _item_amounts(entry.get("rocket_launch_products"))
            if products:
                return products
        for entry in self.entities.values():
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
        """Simule le déclencheur de recherche d'une technologie.

        Selon le type, la simulation mine une entité, craft un item ou lance
        un payload en orbite. ``tech_id`` est conservé pour le contexte mais
        le déclencheur reste piloté uniquement par les faits du dump.
        """
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
        """Traite une technologie dans l'ordre de progression.

        Un déclencheur dédié est simulé s'il existe ; sinon les packs de
        science sont consommés par le laboratoire, dans les quantités
        déclarées par le dump.
        """
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
        """Fabrique récursivement les bâtiments utilisés par la simulation.

        La boucle s'arrête quand plus aucun bâtiment nouveau n'apparaît ; la
        liste triée est ensuite exposée dans le résultat.
        """
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

    def _complexity_snapshot(self) -> dict:
        return {
            "mined": dict(self.mined),
            "external": dict(self.external),
            "buildings": dict(self.building_crafts),
            "crafts": sum(self.recipe_crafts.values()),
            "machine_seconds": self.total_craft_seconds,
            "hand_crafts": self.hand_crafts,
        }

    def _record_complexity(
        self, tech: dict, tech_id: str, position: int, before: dict
    ) -> None:
        packs = [
            {"name": name, "amount": amount}
            for name, amount in _science_requirements(tech)
        ]
        pack_total = sum(pack["amount"] for pack in packs)
        research_time = _tech_seconds(tech)
        mined_delta = _counter_delta(before["mined"], self.mined)
        external_delta = _counter_delta(before["external"], self.external)
        buildings_delta = _counter_delta(before["buildings"], self.building_crafts)
        raw_total = sum(mined_delta.values()) + sum(external_delta.values())
        buildings = sorted(buildings_delta)
        crafts_total = (
            sum(self.recipe_crafts.values())
            - before["crafts"]
            + self.hand_crafts
            - before["hand_crafts"]
        )
        machine_seconds = self.total_craft_seconds - before["machine_seconds"]
        ratio = raw_total / max(len(buildings), 1)
        cumulative = self.complexity_cumulative
        cumulative["time"] += research_time
        cumulative["packs"] += pack_total
        cumulative["raw"] += raw_total
        cumulative["craft_seconds"] += machine_seconds
        cumulative["crafts"] += crafts_total
        self.complexity_seen_buildings.update(buildings)
        cumulative_score = (
            cumulative["time"]
            + cumulative["craft_seconds"]
            + 0.5 * cumulative["packs"]
            + 10 * len(self.complexity_seen_buildings)
        )
        self.complexity_rows.append(
            {
                "num": position,
                "id": tech_id,
                "name": tech.get("localised_name") or tech_id,
                "free": tech_id in set(self.seed.get("free_researches") or []),
                "research_time": round(research_time, 2),
                "packs": pack_total,
                "pack_list": packs,
                "raw_total": clean_number(raw_total),
                "buildings": buildings,
                "building_count": len(buildings),
                "ratio": round(ratio, 2),
                "crafts": clean_number(crafts_total),
                "craft_seconds": round(machine_seconds, 2),
                "hand_crafts": clean_number(
                    self.hand_crafts - before["hand_crafts"]
                ),
                "cumulative_time": round(cumulative["time"], 2),
                "cumulative_packs": cumulative["packs"],
                "cumulative_raw": clean_number(cumulative["raw"]),
                "cumulative_buildings": len(self.complexity_seen_buildings),
                "cumulative_craft_seconds": round(cumulative["craft_seconds"], 2),
                "cumulative_crafts": clean_number(cumulative["crafts"]),
                "cumulative_score": round(cumulative_score, 2),
            }
        )
        for name, amount in mined_delta.items():
            self.complexity_resources[name] += amount
        for name, amount in external_delta.items():
            self.complexity_resources[name] += amount
        for name, count in buildings_delta.items():
            self.complexity_buildings[name] += int(count)

    # -- résultat -----------------------------------------------------------

    def _result(self) -> dict:
        """Assemble le résultat final de la simulation.

        Le dictionnaire contient les statistiques par item, les totaux, les
        bâtiments, les recettes verrouillées, les ressources inutilisées et
        l'inventaire restant, dans un format directement consommé par les
        exporteurs HTML.
        """
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
            "complexity_stats": {
                "rows": self.complexity_rows,
                "resources": {
                    name: clean_number(value)
                    for name, value in sorted(self.complexity_resources.items())
                },
                "buildings": {
                    name: int(value)
                    for name, value in sorted(self.complexity_buildings.items())
                },
                "unknown_terminals": sorted(self.external),
            },
        }

    def run(self) -> dict:
        """Déroule la progression technologique puis finalise la simulation.

        Les technologies sont traitées dans l'ordre déclaré, les bâtiments
        nécessaires sont fabriqués, puis les statistiques finales sont
        retournées.
        """
        if self.on_progress is not None:
            self.on_progress(0, "simulation technologique")
        total_techs = max(1, len(self.progression))
        for position, tech_id in enumerate(self.progression, start=1):
            step = _StepProgress(
                self.on_progress,
                (position - 1) * 90 // total_techs,
                position * 90 // total_techs,
                "simulation technologique",
            )
            self.progress_step = step
            tech = self.tech_by_id.get(tech_id)
            if tech is None:
                step.done()
                continue
            before = self._complexity_snapshot()
            self._process_tech(tech)
            self.processed.add(tech_id)
            self._recipe_choice_version += 1
            self._record_complexity(tech, tech_id, position, before)
            step.done()
        self.progress_step = None
        if self.on_progress is not None:
            self.on_progress(92, "bâtiments utilisés")
        self._craft_used_buildings()
        if self.on_progress is not None:
            self.on_progress(100, "partie simulée")
        return self._result()


def analyze_playthrough(
    seed: dict,
    db: Any = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> dict:
    """Simule une partie complète sans carte et renvoie les statistiques.

    Contrairement à :func:`analyze_complexity`, l'inventaire est porté d'une
    technologie à l'autre : un sous-produit (huile lourde, uranium 238…) est
    réutilisé au lieu d'être recrafté, les déclencheurs de recherche (miner,
    crafter, lancer une fusée) sont simulés, et le craquage du pétrole réduit
    la consommation de brut. ``on_progress`` reçoit un pourcentage de la
    simulation.
    """
    return _Playthrough(seed, db, on_progress=on_progress).run()


__all__ = [
    "write_complexity_html",
    "render_complexity_html",
    "analyze_complexity",
    "analyze_playthrough",
]
