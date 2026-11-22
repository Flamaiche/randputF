"""Profil de difficulté multi-axes normalisé contre une référence."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from tool.audit.graph import GraphAnalysis, analyze_graph

AXIS_WEIGHTS = {
    "structure": 0.25,
    "volume": 0.20,
    "critical": 0.20,
    "novelty": 0.20,
    "infrastructure": 0.15,
}

AXIS_LABELS = {
    "structure": "Structure du graphe",
    "volume": "Volume de production",
    "critical": "Temps critique",
    "novelty": "Nouveauté",
    "infrastructure": "Infrastructure",
}

INDICATOR_LABELS = {
    "recipes": "Recettes atteignables",
    "items": "Items atteignables",
    "links": "Liens ingrédients",
    "raw_inputs": "Ressources brutes",
    "depth": "Profondeur max",
    "buildings": "Ateliers distincts",
    "crafts_log": "log10 crafts",
    "raw_units_log": "log10 unités brutes",
    "machine_seconds_log": "log10 secondes machine",
    "critical_seconds_log": "log10 temps critique",
    "new_items": "Nouveaux items",
    "new_recipes": "Nouvelles recettes",
    "new_buildings": "Nouveaux ateliers",
    "new_fluids": "Nouveaux fluides",
    "fluids": "Fluides distincts",
    "wide_recipes": "Recettes à 4 ingrédients+",
}

_LOG_TO_RAW = {
    "crafts_log": "crafts",
    "raw_units_log": "raw_units",
    "machine_seconds_log": "machine_seconds",
    "critical_seconds_log": "critical_seconds",
}


def _log(value: float) -> float:
    return round(math.log10(1 + max(0.0, value)), 4)


def _ratio(value: float, reference: float) -> float | None:
    if reference > 0:
        return value / reference
    if value == 0:
        return 1.0
    return None


def _aggregate(values: dict[str, float], references: dict[str, float] | None) -> float | None:
    if references is None:
        return None
    ratios = []
    for key, value in values.items():
        ratio = _ratio(float(value), float(references.get(key, 0)))
        if ratio is not None and ratio > 0:
            ratios.append(ratio)
    if not ratios:
        return None
    return math.exp(sum(math.log(ratio) for ratio in ratios) / len(ratios))


def difficulty_profile(
    seed: dict,
    db: Any = None,
    *,
    baseline_seed: dict | None = None,
    baseline_db: Any = None,
    baseline_label: str = "vanilla",
    graph: GraphAnalysis | None = None,
    baseline_graph: GraphAnalysis | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> dict[str, Any]:
    """Retourne le profil multi-axes d'une seed, comparé à une référence si fournie."""
    if on_progress is not None:
        on_progress(0)
    analysis = graph if graph is not None else analyze_graph(seed, db, None)
    profile = analysis.profile
    axes: dict[str, dict[str, Any]] = {}
    for key, values in profile["axes"].items():
        if key not in ("volume", "critical"):
            display = values
        else:
            display = dict(values)
            for indicator in list(display):
                if indicator.endswith("_log"):
                    continue
                display[f"{indicator}_log"] = _log(float(display.pop(indicator)))
        raw_values = profile["raw_axes"][key]
        axes[key] = {
            "label": AXIS_LABELS[key],
            "values": display,
            "raw_values": {
                indicator: raw_values.get(
                    _LOG_TO_RAW.get(indicator, indicator.removesuffix("_log"))
                )
                for indicator in display
            },
            "reference": None,
            "reference_raw": None,
            "ratio": None,
        }

    if baseline_seed is not None or baseline_graph is not None:
        baseline_analysis = (
            baseline_graph
            if baseline_graph is not None
            else analyze_graph(baseline_seed, baseline_db, None)
        )
        baseline = baseline_analysis.profile
        for key, axis in axes.items():
            references = dict(baseline["axes"][key])
            if key in ("volume", "critical"):
                for indicator in list(references):
                    if indicator.endswith("_log"):
                        continue
                    references[f"{indicator}_log"] = _log(
                        float(references.pop(indicator))
                    )
            raw_references = baseline["raw_axes"][key]
            axis["reference"] = references
            axis["reference_raw"] = {
                indicator: raw_references.get(
                    _LOG_TO_RAW.get(indicator, indicator.removesuffix("_log"))
                )
                for indicator in references
            }
            axis["ratio"] = _aggregate(axis["values"], references)

    ratios = [axis["ratio"] for axis in axes.values() if axis["ratio"] is not None]
    score = None
    if len(ratios) == len(axes):
        weight = sum(AXIS_WEIGHTS.values())
        score = math.exp(
            sum(AXIS_WEIGHTS[key] * math.log(axis["ratio"]) for key, axis in axes.items())
            / weight
        )

    return {
        "axes": axes,
        "weights": dict(AXIS_WEIGHTS),
        "score": score,
        "baseline_label": baseline_label,
        "unknown": profile["unknown"],
    }
