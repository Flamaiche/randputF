"""Prototype « déblocage progressif des extracteurs » (IDEES §D).

Constat : au spawn, le joueur accède d'un coup à `burner-mining-drill`,
`electric-mining-drill`, `pumpjack` et `offshore-pump` — trop d'extraction
d'un coup, la progression ne se lit pas.

Ce prototype échelonne l'extraction :
1. un SEUL extracteur (le plus primitif compatible avec la phase) au
   starter ;
2. les foreuses plus évoluées se débloquent PAR la récursion (jamais en
   vrac au départ) ;
3. la « permission de miner » façon vanilla : une ressource n'est minable
   que si (a) son extracteur compatible est débloqué ET (b) la recherche
   nécessaire est faite (uranium → recherche requis).

**Constante on/off** (``enabled``) : quand ``false``, tous les extracteurs
sont au starter (comportement actuel).
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

    Retourne un dict ``{resource: extracteur_name}``.
    Les extracteurs sont consommés dans l'ordre des paliers ; le starter
    ne prend qu'UN extracteur (``starter_max_extractors``) qui couvre les
    premiers patchs.  Quand ``enabled=False``, tout est couvert par le
    premier extracteur (comportement actuel, pas de progression).
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
    """Regroupe les extracteurs par tech d'unlock (palier).

    Retourne ``{tier: [extracteur_names]}`` — uniquement les extracteurs
    utilisés dans les assignments.
    """
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