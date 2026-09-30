"""Prototype « ressources rares au début » (mode exploration).

Mode (constante on/off) qui rend les ressources rares/précieuses au départ :
peu de gisements près du spawn → chercher plus loin (patchs plus denses).
Richesse et densité de blocs selon la distance au spawn : réduites près du
spawn (< ``near_radius``), augmentées loin (> ``far_radius``), interpolation
linéaire entre les deux.

Solvabilité : au moins un gisement de chaque ressource obligatoire (iron,
copper, coal, water) reste proche du spawn, à densité mini (jamais 0, jamais
de suppression).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tool.prototypes.base import PrototypeConfig


@dataclass
class RareResourcesConfig(PrototypeConfig):
    """Configuration pour le mode « ressources rares au début »."""
    enabled: bool = False
    # Rayons (en tuiles) qui délimitent les zones proche / lointaine.
    near_radius: int = 40
    far_radius: int = 120
    # Facteurs multiplicatifs appliqués aux patchs proches / lointains.
    near_richness_factor: float = 0.4
    near_count_factor: float = 0.5
    far_richness_factor: float = 2.0
    far_count_factor: float = 1.8
    # Ressources obligatoires du bootstrap : toujours au moins 1 gisement
    # proche du spawn (solvabilité).
    required_resources: tuple[str, ...] = ("iron-ore", "copper-ore", "coal", "water")

    @classmethod
    def from_config(cls, config: dict) -> RareResourcesConfig:
        """Construit la config rare_resources depuis ``config`` — défauts du
yaml, jamais codés en dur par le moteur."""
        cfg = config.get("rare_resources", {})
        return cls(
            enabled=bool(cfg.get("enabled", False)),
            near_radius=int(cfg.get("near_radius", 40)),
            far_radius=int(cfg.get("far_radius", 120)),
            near_richness_factor=float(cfg.get("near_richness_factor", 0.4)),
            near_count_factor=float(cfg.get("near_count_factor", 0.5)),
            far_richness_factor=float(cfg.get("far_richness_factor", 2.0)),
            far_count_factor=float(cfg.get("far_count_factor", 1.8)),
            required_resources=tuple(cfg.get("required_resources",
                                             ("iron-ore", "copper-ore", "coal", "water"))),
        )


@dataclass
class RarePatch:
    """Un patch dans le mode rareté (mini-modèle)."""
    resource: str
    richness: int
    count: int
    distance_to_spawn: int  # en tuiles


def distance(center: tuple[int, int]) -> int:
    """Distance euclidienne au spawn (0, 0), arrondie."""
    import math
    return int(math.hypot(center[0], center[1]))


def terrain_factor(
    dist: int,
    config: RareResourcesConfig,
) -> tuple[float, float]:
    """Facteurs (richesse, count) selon la distance au spawn.

    Interpolation linéaire entre les zones proche et lointaine.
    """
    if dist <= config.near_radius:
        return config.near_richness_factor, config.near_count_factor
    if dist >= config.far_radius:
        return config.far_richness_factor, config.far_count_factor
    t = (dist - config.near_radius) / (config.far_radius - config.near_radius)
    richness = config.near_richness_factor + t * (
        config.far_richness_factor - config.near_richness_factor
    )
    count = config.near_count_factor + t * (
        config.far_count_factor - config.near_count_factor
    )
    return richness, count


def apply_rare_mode(
    rng: random.Random,
    patches: list[RarePatch],
    config: RareResourcesConfig,
) -> list[RarePatch]:
    """Applique le mode rareté.

    - ``enabled=False`` → liste identique.
    - ``enabled=True`` → richness/count multipliés selon la distance ;
      les ressources obligatoires restent proches avec au moins 1 bloc.
    """
    if not config.enabled:
        return list(patches)

    out: list[RarePatch] = []
    # ressources obligatoires : placées proches, richesse mini garantie
    required_seen: set[str] = set()
    for p in patches:
        dist = p.distance_to_spawn
        if p.resource in set(config.required_resources) and p.resource not in required_seen:
            dist = min(dist, 15)  # forcer la proximité pour la première occurrence
            required_seen.add(p.resource)
        rf, cf = terrain_factor(dist, config)
        new_richness = max(500, int(p.richness * rf))
        new_count = max(1, int(p.count * cf))
        out.append(RarePatch(p.resource, new_richness, new_count, dist))
    return out


def verify_required_near_spawn(
    patches: list[RarePatch],
    required: tuple[str, ...],
    near_radius: int,
) -> bool:
    """Toutes les ressources obligatoires ont au moins un gisement ≤ near_radius."""
    for res in required:
        found = any(p.resource == res and p.distance_to_spawn <= near_radius for p in patches)
        if not found:
            return False
    return True


def verify_no_zero(patches: list[RarePatch]) -> bool:
    """Aucun patch sans richesse ni bloc."""
    return all(p.richness >= 500 and p.count >= 1 for p in patches)