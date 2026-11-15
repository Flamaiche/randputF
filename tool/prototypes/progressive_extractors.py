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
    """Palier d'extracteur du modèle de déblocage progressif.

    ``name`` identifie l'extracteur, ``tier`` son rang (1 = starter, 2+ =
    récursion), ``picks`` le nombre de patchs qu'il peut prendre en charge et
    ``research_required`` la technologie qui le débloque (``None`` si aucune).
    """
    name: str
    tier: int            # 1 = starter, 2+ = récursion
    picks: int           # nombre de patchs pris en charge
    research_required: str | None = None  # "uranium-mining" par ex.


@dataclass
class ProgressiveExtractorsConfig(PrototypeConfig):
    """Configuration du déblocage progressif des extracteurs.

    ``enabled`` active le mode, ``starter_extractor`` nomme la foreuse de départ, ``starter_max_extractors`` borne le nombre d'extracteurs au starter et ``research_map`` associe une ressource à sa recherche requise.
    """
    enabled: bool = False
    # Nom du starter extractor (le plus primitif qui couvre au moins 1 patch)
    starter_extractor: str = "burner-mining-drill"
    # Nombre max d'extracteurs différents au starter (1 = strict)
    starter_max_extractors: int = 1
    # Recherches requises par ressource (permission façon vanilla)
    research_map: dict[str, str] | None = None

    @classmethod
    def from_config(cls, config: dict) -> ProgressiveExtractorsConfig:
        """Construit la configuration ``progressive_extractors`` depuis le dict complet.

        ``config`` peut être partiel ; les clés absentes prennent les défauts du YAML. Retourne une configuration validée, avec ``research_map`` initialisé à un dict vide si absent.
        """
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
    """Regroupe les extracteurs utilisés par palier.

    ``assignments`` associe une ressource à un extracteur, ``extractors`` fournit les paliers et ``config`` la configuration. Retourne ``{tier: [noms]}`` trié, en ne gardant que les extracteurs réellement assignés.
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
    """Vérifie la limite d'extracteurs au starter.

    ``unlock_plan`` est le plan groupé par palier et ``starter_max`` la limite du tier 1. Retourne ``True`` si le tier 1 contient au plus ``starter_max`` extracteurs.
    """
    return len(unlock_plan.get(1, [])) <= starter_max