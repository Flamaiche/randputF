"""Prototype C1 : randomisation des ressources non-infinies.

Les patches items et fluides (gisements finis) ont leur identité fixe à la
seed. Cette phase randomise en plus : la richesse (volume total), le nombre
de blocs/pièces (count), le rayon du cluster. L'identité n'est PAS modifiée
ici : elle est tirée par ``generate_patches``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tool.common import config as _cfg
from tool.prototypes.base import PrototypeConfig


@dataclass
class NonfiniteConfig(PrototypeConfig):
    """Configuration pour la randomisation des ressources non-infinies."""
    enabled: bool = False
    # Facteurs multiplicatifs sur la richesse (bornes)
    richness_factor_min: float = 0.4
    richness_factor_max: float = 2.5
    # Facteurs multiplicatifs sur le count (nombre de blocs/pièces)
    count_factor_min: float = 0.5
    count_factor_max: float = 2.0
    # Facteurs multiplicatifs sur le rayon du cluster
    radius_factor_min: float = 0.6
    radius_factor_max: float = 1.8

    @classmethod
    def from_config(cls, config: dict) -> NonfiniteConfig:
        """Construit la config nonfinite depuis ``config`` — défauts du
yaml, jamais codés en dur par le moteur."""
        cfg = config.get("nonfinite", {})
        return cls(
            enabled=bool(cfg.get("enabled", _cfg.default_value("nonfinite", "enabled"))),
            richness_factor_min=float(cfg.get("richness_factor_min", _cfg.default_value("nonfinite", "richness_factor_min"))),
            richness_factor_max=float(cfg.get("richness_factor_max", _cfg.default_value("nonfinite", "richness_factor_max"))),
            count_factor_min=float(cfg.get("count_factor_min", _cfg.default_value("nonfinite", "count_factor_min"))),
            count_factor_max=float(cfg.get("count_factor_max", _cfg.default_value("nonfinite", "count_factor_max"))),
            radius_factor_min=float(cfg.get("radius_factor_min", _cfg.default_value("nonfinite", "radius_factor_min"))),
            radius_factor_max=float(cfg.get("radius_factor_max", _cfg.default_value("nonfinite", "radius_factor_max"))),
        )


@dataclass
class PatchSpec:
    """Spécification d'un patch (mini-modèle pour le prototype)."""
    kind: str          # "item" | "fluid"
    resource: str      # ex. "iron-ore", "crude-oil"
    richness: int
    center: tuple[int, int] = (0, 0)
    count: int = 0
    cluster_radius: int = 10


def randomise_patches(
    rng: random.Random,
    patches: list[PatchSpec],
    config: NonfiniteConfig,
) -> list[PatchSpec]:
    """Applique la randomisation non-infinie sur une liste de patchs.

    - ``enabled=False`` → liste identique (shallow copy).
    - ``enabled=True`` → re-tire richness, count, cluster_radius avec le PRNG.
    - L'identité (kind + resource) n'est JAMAIS changée.
    - Richesse ≥ 1, count ≥ 1, radius ≥ 3 (bornes de sécurité).
    """
    if not config.enabled:
        return list(patches)

    out: list[PatchSpec] = []
    for p in patches:
        rf = rng.uniform(config.richness_factor_min, config.richness_factor_max)
        cf = rng.uniform(config.count_factor_min, config.count_factor_max)
        rrf = rng.uniform(config.radius_factor_min, config.radius_factor_max)
        new_richness = max(1, int(p.richness * rf))
        new_count = max(1, int(p.count * cf)) if p.count > 0 else p.count
        new_radius = max(3, int(p.cluster_radius * rrf))
        out.append(PatchSpec(
            kind=p.kind,
            resource=p.resource,
            richness=new_richness,
            center=p.center,
            count=new_count,
            cluster_radius=new_radius,
        ))
    return out


def verify_solvability(
    patches: list[PatchSpec],
    required_items: set[str],
    required_fluids: set[str],
) -> list[str]:
    """Vérifie que les ressources obligatoires sont toujours présentes.

    Renvoie la liste des ressources manquantes (vide = OK). Teste les
    identités, pas les quantités.
    """
    present_items = {p.resource for p in patches if p.kind == "item"}
    present_fluids = {p.resource for p in patches if p.kind == "fluid"}
    missing = []
    missing += sorted(required_items - present_items)
    missing += sorted(required_fluids - present_fluids)
    return missing


def no_duplicates(patches: list[PatchSpec]) -> bool:
    """Vérifie l'invariant C6 : chaque ressource apparaît au plus une fois."""
    seen: set[str] = set()
    for p in patches:
        if p.resource in seen:
            return False
        seen.add(p.resource)
    return True
