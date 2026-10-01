"""Configuration : defaults non modifiables + surcharges utilisateur.

``config/defaults.yaml`` est la source UNIQUE de toutes les valeurs de
réglages (jamais un défaut codé dans le moteur). ``config/user.yaml`` porte
les surcharges utilisateur. ``full_config`` fusionne richement les deux puis
VALIDE le résultat contre un schéma strict (types, plages, bornes min<=max,
contraintes croisées) : une clé inconnue, un mauvais type ou une valeur
impossible est un ``ConfigError`` explicite, jamais une génération à l'aveugle.

Un config fusionné est TOUJOURS complet : chaque section/clé lue par le
moteur existe (garantie du defaults), donc aucun module n'a besoin de valeur
de secours.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from tool.common.assets import asset_path


class ConfigError(ValueError):
    """Erreur de configuration (schéma, plage, contrainte croisée)."""


# ── Spécifications du schéma ──────────────────────────────────────────────────
# Spec = tuple dont le 1er élément est le type de validation :
#   ("bool",)
#   ("int", lo, hi)                    entier dans [lo, hi]
#   ("num_ge", lo)                     nombre >= lo
#   ("float01",)                       nombre dans [0, 1]
#   ("str",)
#   ("str_list",)                      liste de chaînes
#   ("nonempty_str_list",)             liste de chaînes non vide
#   ("str_list_list",)                 liste de listes de chaînes (vide OK)
#   ("int_list_inc", lo)               entiers > lo, strictement croissants
#   ("float_list", lo)                 nombres >= lo
#   ("float_bounded_list", lo, hi, nmin, nmax)  nombres dans [lo, hi], comptés
#   ("pair_int", lo, hi)               [a, b] entiers dans [lo, hi], a <= b
#   ("pair_num", lo, hi)               [a, b] nombres dans [lo, hi], a <= b
#   ("dict_num", lo)                   dict {str: nombre >= lo}
#   ("enum", valeur1, valeur2, ...)    dans la liste fermée

_ROOT_SCHEMA: dict[str, tuple] = {
    "factorio_version": ("str",),
}

_SCHEMA: dict[str, dict[str, tuple]] = {
    "paths": {
        "mod_dir": ("str",),
        "vanilla_dump": ("str",),
        "factorio_mods": ("str",),
    },
    "map": {
        "patches_min": ("int", 1, 10_000),
        "patches_max": ("int", 1, 10_000),
        "richness_item": ("pair_num", 1, 1_000_000_000),
        "richness_fluid": ("pair_num", 1, 1_000_000_000),
        "wells_per_patch": ("pair_int", 1, 1_000),
        "item_patch_radius": ("pair_int", 1, 1_000_000),
        "cluster_radius": ("pair_int", 1, 1_000_000),
        "first_center_dist": ("int", 0, 10_000_000),
        "center_ring_step": ("int", 1, 10_000_000),
    },
    "nonfinite": {
        "enabled": ("bool",),
        "richness_factor_min": ("num_ge", 0.0),
        "richness_factor_max": ("num_ge", 0.0),
        "count_factor_min": ("num_ge", 0.0),
        "count_factor_max": ("num_ge", 0.0),
        "radius_factor_min": ("num_ge", 0.0),
        "radius_factor_max": ("num_ge", 0.0),
    },
    "pools": {
        "exclude_items": ("str_list",),
        "exclude_fluids": ("str_list",),
        "exclude_building_types": ("str_list",),
    },
    "weights": {
        "building_types": ("dict_num", 0.0),
        "science_packs": ("dict_num", 0.0),
    },
    "recursive": {
        "weight_transformer": ("num_ge", 0.0),
        "weight_extractor": ("num_ge", 0.0),
        "weight_generator": ("num_ge", 0.0),
        "weight_distribution": ("num_ge", 0.0),
        "weight_combat": ("num_ge", 0.0),
        "weight_science": ("num_ge", 0.0),
        "progressive_factor": ("num_ge", 0.0),
        "excluded_buildings": ("str_list",),
        "max_iterations": ("int", 1, 1_000_000),
        "stall_threshold": ("int", 0, 1_000_000),
        "dist_marks": ("int_list_inc", 0),
        "dist_guaranteed": ("int", 0, 1_000_000),
        "recipes_per_building_min": ("int", 0, 100_000),
        "recipes_per_building_max": ("int", 0, 100_000),
        "tech_count_min": ("int", 0, 100_000),
        "tech_count_max": ("int", 0, 100_000),
        "science_cost_min": ("int", 0, 1_000_000),
        "science_cost_max": ("int", 0, 1_000_000),
        "companions": ("str_list_list",),
        "armed_vehicles": ("str_list",),
        "vehicle_weapons": ("str_list",),
        "vehicle_slots_min": ("int", 0, 10_000),
        "vehicle_slots_max": ("int", 0, 10_000),
        "vehicle_slots_with_replacement": ("bool",),
        "vehicle_range_base_size": ("num_ge", 0.0),
        "vehicle_range_scale": ("num_ge", 0.0),
    },
    "starter": {
        "free_researches_count": ("pair_int", 0, 100_000),
        "ammo_count": ("int", 0, 10_000_000),
        "inserter_chance": ("float01",),
        "spawn_fuel_count": ("int", 1, 10_000_000),
        "deferred": ("str_list_list",),
    },
    "wreck": {
        "t": ("int", 0, 10_000),
        "a": ("int", 0, 10_000),
        "b": ("int", 1, 10_000),
        "loot": ("nonempty_str_list",),
    },
    "lakes": {
        "min": ("int", 0, 100_000),
        "max": ("int", 0, 100_000),
        "richness_fluid": ("pair_num", 1, 1_000_000_000),
    },
    "tree": {
        "group_chances": ("float_bounded_list", 0.0, 1.0, 1, 4),
        "research_time": ("int", 1, 10_000_000),
        "max_cost_packs": ("int", 1, 1_000),
        "max_per_tech": ("int", 1, 1_000),
    },
    "recipes": {
        "weight_1_ingredient": ("int", 0, 1_000_000),
        "weight_2_ingredients": ("int", 0, 1_000_000),
        "weight_3_ingredients": ("int", 0, 1_000_000),
        "weight_1_result": ("int", 0, 1_000_000),
        "weight_2_results": ("int", 0, 1_000_000),
        "energies": ("float_list", 0.1),
        "energy_per_ingredient": ("num_ge", 0.0),
        "balance_min": ("num_ge", 0.0),
        "balance_max": ("num_ge", 0.0),
        "balance_steepness": ("num_ge", 0.0),
        "balance_max_factor": ("num_ge", 0.0),
        "max_overproduced_ratio": ("float01",),
        "balance_iterations": ("int", 0, 100_000),
        "ingredient_amount_min": ("int", 1, 1_000_000),
        "ingredient_amount_max": ("int", 1, 1_000_000),
        "recipe_prefix": ("str",),
        "environmental_weight_rich": ("num_ge", 0.0),
        "environmental_weight_starved": ("num_ge", 0.0),
        "environmental_amount_max": ("int", 0, 1_000_000),
    },
    "relay": {
        "prefix": ("str",),
        "max_dispatch_steps": ("int", 1, 10_000),
    },
    "easeup": {
        "prefix": ("str",),
        "max_recipes": ("int", 0, 1_000_000),
        "depth_threshold": ("int", 1, 1_000_000),
        "unlocks_per_tech": ("int", 1, 1_000_000),
    },
    "usage": {
        "enabled": ("bool",),
        "strict_order": ("bool",),
        "terminal_buildings": ("str_list",),
        "kit_exempt": ("str_list",),
    },
    "craft_quantity": {
        "enabled": ("bool",),
        "mode": ("enum", "symmetric", "asymmetric"),
        "factor_min": ("num_ge", 0.0),
        "factor_max": ("num_ge", 0.0),
        "amount_min": ("int", 1, 1_000_000),
    },
    "late_raws": {
        "enabled": ("bool",),
        "share": ("float01",),
        "pick_chance": ("float01",),
    },
}


class _ConfigStore:
    """Defaults chargés une fois depuis ``config/defaults.yaml``."""

    def __init__(self) -> None:
        self._defaults: dict | None = None
        self._config_dir: Path | None = None

    def _resolve(self) -> Path:
        if self._config_dir is None:
            self._config_dir = Path(asset_path("config"))
        return self._config_dir

    def defaults(self) -> dict:
        return copy.deepcopy(self._merged_defaults())

    def _merged_defaults(self) -> dict:
        if self._defaults is None:
            path = self._resolve() / "defaults.yaml"
            if not path.exists():
                raise ConfigError(f"defaults introuvable: {path}")
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            merged = _deep_merge({}, loaded)
            errors = validate(merged)
            if errors:
                raise ConfigError("defaults.yaml invalide:\n  - " + "\n  - ".join(errors))
            self._defaults = merged
        return self._defaults

    def user_file(self) -> Path | None:
        candidate = self._resolve() / "user.yaml"
        return candidate if candidate.exists() else None


_STORE = _ConfigStore()


def _deep_merge(base: dict, overrides: dict | Any) -> dict:
    """Fusion récursive : les dict s'imbriquent, tout le reste remplace."""
    out = copy.deepcopy(base)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def load_defaults() -> dict:
    """Copie profonde du defaults (jamais muté par les appelants)."""
    return _STORE.defaults()


def user_config_file() -> Path | None:
    """Chemin du fichier de surcharge utilisateur (None s'il est absent)."""
    return _STORE.user_file()


def default_value(section: str, key: str):
    """Valeur par défaut (source UNIQUE = defaults.yaml) pour un module appelé
    avec un dict de config partiel. Jamais de littéral dupliqué dans le code."""
    body = _STORE._merged_defaults().get(section)
    if not isinstance(body, dict):
        raise ConfigError(f"defaults : section inconnue {section!r}")
    if key not in body:
        raise ConfigError(f"defaults : clé inconnue {section}.{key}")
    return copy.deepcopy(body[key])


def full_config(overrides: dict | None = None, *, strict_sections: bool = True) -> dict:
    """Defaults fusionnés avec ``overrides`` puis VALIDÉS.

    Le résultat est complet (toutes les sections/clés présentes) et conforme
    au schéma ; sans ``overrides`` il vaut exactement le defaults.

    ``strict_sections=False`` ignore les sections racine INCONNUES des
    surcharges (usage programmatique : ``pipeline.generate_seed`` reçoit des
    dict d'appelants divers) — mais le contenu de TOUTES les sections connues
    est tout de même validé strictement (types, plages, bornes).
    """
    merged = _deep_merge(_STORE.defaults(), overrides)
    errors = validate(merged, strict_sections=strict_sections)
    if errors:
        raise ConfigError(
            "Configuration invalide :\n  - " + "\n  - ".join(errors)
        )
    return merged


def runtime_config() -> dict:
    """Default + fichier ``user.yaml`` (les surcharges persistantes)."""
    user_path = _STORE.user_file()
    overrides = None
    if user_path is not None:
        loaded = yaml.safe_load(user_path.read_text(encoding="utf-8")) or {}
        overrides = loaded if isinstance(loaded, dict) else {}
    return full_config(overrides=overrides)


# ── Validation ────────────────────────────────────────────────────────────────


def _expect(cond: bool, errors: list[str], where: str, message: str) -> None:
    if not cond:
        errors.append(f"{where}: {message}")


def _check_value(errors: list[str], where: str, value: Any, spec: tuple) -> None:
    kind = spec[0]
    if kind == "bool":
        _expect(isinstance(value, bool), errors, where, "attendu un booléen")
    elif kind == "int":
        ok = type(value) is int and spec[1] <= value <= spec[2]
        _expect(ok, errors, where, f"attendu un entier dans [{spec[1]}, {spec[2]}]")
    elif kind == "num_ge":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) and value >= spec[1]
        _expect(ok, errors, where, f"attendu un nombre >= {spec[1]}")
    elif kind == "float01":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= value <= 1.0
        _expect(ok, errors, where, "attendu un nombre dans [0, 1]")
    elif kind == "str":
        _expect(isinstance(value, str), errors, where, "attendu une chaîne")
    elif kind == "str_list":
        _expect(
            isinstance(value, list) and all(isinstance(v, str) for v in value),
            errors, where, "attendu une liste de chaînes",
        )
    elif kind == "nonempty_str_list":
        _expect(
            isinstance(value, list)
            and len(value) >= 1
            and all(isinstance(v, str) for v in value),
            errors, where, "attendu une liste de chaînes NON vide",
        )
    elif kind == "str_list_list":
        _expect(
            isinstance(value, list)
            and all(
                isinstance(g, list)
                and len(g) >= 1
                and all(isinstance(m, str) for m in g)
                for g in value
            ),
            errors, where, "attendu une liste de listes de chaînes non vides",
        )
    elif kind == "int_list_inc":
        ok = isinstance(value, list) and value and all(type(v) is int and v > spec[1] for v in value)
        if ok:
            ok = all(a < b for a, b in zip(value, value[1:]))
        _expect(ok, errors, where, f"entiers > {spec[1]}, strictement croissants")
    elif kind == "float_list":
        lo = spec[1]
        ok = isinstance(value, list) and value and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and v >= lo
            for v in value
        )
        _expect(ok, errors, where, f"attendu une liste non vide de nombres >= {lo}")
    elif kind == "float_bounded_list":
        lo, hi, nmin, nmax = spec[1], spec[2], spec[3], spec[4]
        ok = (
            isinstance(value, list)
            and nmin <= len(value) <= nmax
            and all(
                isinstance(v, (int, float))
                and not isinstance(v, bool)
                and lo <= v <= hi
                for v in value
            )
        )
        _expect(ok, errors, where,
                f"attendu {nmin}..{nmax} nombres dans [{lo}, {hi}]")
    elif kind in ("pair_int", "pair_num"):
        lo, hi = spec[1], spec[2]
        if isinstance(value, list) and len(value) == 2:
            a, b = value
            ok_a = (type(a) is int) if kind == "pair_int" else isinstance(a, (int, float)) and not isinstance(a, bool)
            ok_b = (type(b) is int) if kind == "pair_int" else isinstance(b, (int, float)) and not isinstance(b, bool)
            in_range = ok_a and ok_b and lo <= a <= hi and lo <= b <= hi
            _expect(in_range, errors, where,
                    f"attendu une paire [a, b] de nombres dans [{lo}, {hi}]")
            if in_range:
                _expect(a <= b, errors, where, "min > max interdit (attendu a <= b)")
        else:
            _expect(False, errors, where,
                    f"attendu une paire [a, b] de nombres dans [{lo}, {hi}]")
    elif kind == "dict_num":
        ok = (
            isinstance(value, dict)
            and all(
                isinstance(k, str)
                and isinstance(v, (int, float))
                and not isinstance(v, bool)
                and v >= spec[1]
                for k, v in value.items()
            )
        )
        _expect(ok, errors, where, f"attendu un dict {{str: nombre >= {spec[1]}}}")
    elif kind == "enum":
        _expect(value in spec[1:], errors, where,
                f"attendu l'une des valeurs {spec[1:]!r}")


def validate(merged: dict, *, strict_sections: bool = True) -> list[str]:
    """Valide le config fusionné contre le schéma. Renvoie la liste d'erreurs
    (vide si tout est bon). ``strict_sections=False`` : les sections racine
    inconnues ne sont pas signalées (contenu des sections connues validé
    quand même)."""
    errors: list[str] = []

    for section, body in merged.items():
        if section in _ROOT_SCHEMA:
            _check_value(errors, section, body, _ROOT_SCHEMA[section])
            continue
        if section not in _SCHEMA:
            if strict_sections:
                errors.append(f"[{section}] section inconnue")
            continue
        if not isinstance(body, dict):
            errors.append(f"[{section}] attendu un dictionnaire")
            continue
        for key, value in body.items():
            spec = _SCHEMA[section].get(key)
            if spec is None:
                # Une clé inconnue DANS une section connue est toujours une
                # faute de frappe (jamais tolérée, même en mode lenient).
                errors.append(f"[{section}.{key}] clé inconnue")
                continue
            _check_value(errors, f"{section}.{key}", value, spec)
        body_keys = set(body)
        for known in _SCHEMA[section]:
            if known not in body_keys:
                # Le defaults est garanti complet : une clé absente ici est un
                # défaut de maintenance (jamais accepté silencieusement).
                errors.append(f"[{section}.{known}] clé obligatoire absente")

    # Contraintes croisées (min <= max entre deux clés d'une même paire).
    _pair_order(errors, merged, "map", "patches_min", "patches_max")
    _pair_order(errors, merged, "recursive", "recipes_per_building_min",
                "recipes_per_building_max")
    _pair_order(errors, merged, "recursive", "tech_count_min", "tech_count_max")
    _pair_order(errors, merged, "recursive", "science_cost_min", "science_cost_max")
    _pair_order(errors, merged, "recursive", "vehicle_slots_min", "vehicle_slots_max")
    _pair_order(errors, merged, "craft_quantity", "factor_min", "factor_max")
    _pair_order(errors, merged, "nonfinite", "richness_factor_min",
                "richness_factor_max")
    _pair_order(errors, merged, "nonfinite", "count_factor_min", "count_factor_max")
    _pair_order(errors, merged, "nonfinite", "radius_factor_min", "radius_factor_max")
    _pair_order(errors, merged, "recipes", "balance_min", "balance_max")
    _pair_order(errors, merged, "recipes", "ingredient_amount_min",
                "ingredient_amount_max")
    _pair_order(errors, merged, "lakes", "min", "max")

    _wreck_constraints(errors, merged)
    return errors


def _pair_order(
    errors: list[str],
    merged: dict,
    section: str,
    key_a: str,
    key_b: str,
) -> None:
    sec = merged.get(section)
    if not isinstance(sec, dict):
        return
    a, b = sec.get(key_a), sec.get(key_b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        _expect(a <= b, errors, f"{section}",
                f"{key_a} ({a}) > {key_b} ({b}) interdit")


def _wreck_constraints(errors: list[str], merged: dict) -> None:
    sec = merged.get("wreck")
    if not isinstance(sec, dict):
        return
    t = sec.get("t")
    a = sec.get("a")
    b = sec.get("b")
    if isinstance(t, int) and isinstance(a, int) and isinstance(b, int):
        c3, c2 = t, t + a
        c1 = 100 - 5 * t - 2 * a
        c0 = c1 + b
        if not (b >= 1):
            _expect(False, errors, "wreck", "b >= 1 requis")
        if any(c < 0 for c in (c0, c1, c2, c3)):
            _expect(False, errors, "wreck", "comptes négatifs (6t + 3a < 100 requis)")
        if not (c0 > c1 > c2 > c3):
            _expect(False, errors, "wreck",
                    "formule non strictement décroissante (exiger 6t + 3a < 100)")


__all__ = [
    "ConfigError",
    "default_value",
    "full_config",
    "load_defaults",
    "runtime_config",
    "user_config_file",
    "validate",
]