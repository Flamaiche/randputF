"""Prototype « déblocage progressif des extracteurs ».

Échelonne l'extraction au lieu d'exposer d'un coup tous les extracteurs :
1. un seul extracteur (le plus primitif compatible avec la phase) au starter ;
2. les foreuses plus évoluées se débloquent PAR la récursion ;
3. permission de miner façon vanilla : minable si son extracteur est débloqué
   et la recherche nécessaire faite (uranium → recherche requis).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from tool.prototypes.base import PrototypeConfig


@dataclass
class ExtractorTier:
    """Un palier d'extracteur (mini-modèle)."""
    name: str
    tier: int            # 1 = starter, 2+ = récursion
    picks: int           # nombre de patchs pris en charge
    research_required: str | None = None  # "uranium-mining" par ex.


@dataclass
class ProgressiveExtractorsConfig(PrototypeConfig):
    """Configuration pour le déblocage progressif des extracteurs."""
    enabled: bool = False
    # Nom du starter extractor (le plus primitif qui couvre au moins 1 patch)
    starter_extractor: str = "burner-mining-drill"
    # Nombre max d'extracteurs différents au starter (1 = strict)
    starter_max_extractors: int = 1
    # Recherches requises par ressource (permission façon vanilla)
    research_map: dict[str, str] | None = None

    @classmethod
    def from_config(cls, config: dict) -> ProgressiveExtractorsConfig:
        """Construit la config progressive_extractors depuis ``config`` — défauts du
yaml, jamais codés en dur par le moteur."""
        cfg = config.get("progressive_extractors", {})
        return cls(
            enabled=bool(cfg.get("enabled", False)),
            starter_extractor=str(cfg.get("starter_extractor", "burner-mining-drill")),
            starter_max_extractors=int(cfg.get("starter_max_extractors", 1)),
            research_map=cfg.get("research_map") or {},
        )


def compute_extractor_assignments(
    rng: random.Random,
    extractors: list[ExtractorTier],
    resources: list[str],
    config: ProgressiveExtractorsConfig,
) -> dict[str, str]:
    """Assigne (extracteur → ressources) selon le mode progressif.

    Retourne ``{resource: extracteur_name}``. Extracteurs consommés dans
    l'ordre des paliers ; le starter couvre les premiers patchs.
    ``enabled=False`` → tout couvert par le premier extracteur.
    """
    if not config.enabled:
        # comportement vanilla : tout est couvert par le premier extracteur
        return {res: extractors[0].name for res in resources}

    # Le starter (le plus primitif) prend ses picks en premier
    starter = next((e for e in extractors if e.name == config.starter_extractor), extractors[0])
    sorted_extractors = sorted(extractors, key=lambda e: e.tier)

    remaining = list(resources)
    assignments: dict[str, str] = {}

    # 1. le starter prend exactement ``picks`` ressources (jamais de reste).
    for res in remaining[:starter.picks]:
        assignments[res] = starter.name
    remaining = remaining[starter.picks:]

    # 2. les paliers suivants, dans l'ordre croissant de tier, prennent
    #    chacun ``picks`` ressources — le starter est sauté (déjà consommé).
    for e in sorted_extractors:
        if e.name == starter.name:
            continue
        if not remaining:
            break
        take = min(len(remaining), e.picks)
        for res in remaining[:take]:
            assignments[res] = e.name
        remaining = remaining[take:]

    return assignments


def gather_unlocks(
    assignments: dict[str, str],
    extractors: dict[str, ExtractorTier],
    config: ProgressiveExtractorsConfig,
) -> dict[int, list[str]]:
    """Regroupe les extracteurs par palier : ``{tier: [extracteur_names]}``
    (uniquement ceux utilisés dans les assignments)."""
    tiers: dict[int, list[str]] = {}
    for res, ex in assignments.items():
        tier = extractors[ex].tier
        tiers.setdefault(tier, [])
        if ex not in tiers[tier]:
            tiers[tier].append(ex)
    return {k: sorted(tiers[k]) for k in sorted(tiers)}


def verify_starter_restant(
    unlock_plan: dict[int, list[str]],
    starter_max: int,
) -> bool:
    """Le starter (tier 1) contient au plus ``starter_max`` extracteurs."""
    return len(unlock_plan.get(1, [])) <= starter_max