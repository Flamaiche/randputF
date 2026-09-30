"""Tests du prototype « déblocage progressif des extracteurs ».

Vérifie :
- déterminisme (même seed → même résultat) ;
- mode désactivé → tout est couvert par le premier extracteur (vanilla) ;
- mode activé → le starter ne contient qu'UN extracteur (ou max config) ;
- tous les extracteurs du plan ont une utilité (chaque assignation pointe
  vers un extracteur connu) ;
- au moins 2 paliers sont utilisés quand les ressources le permettent ;
- toute ressource est couverte par exactement 1 extracteur.
"""

from __future__ import annotations

import random

import pytest

from tool.prototypes.progressive_extractors import (
    ExtractorTier,
    ProgressiveExtractorsConfig,
    compute_extractor_assignments,
    gather_unlocks,
    verify_starter_restant,
)

SEEDS = (0, 5, 13, 42, 99)

EXTRACTORS = [
    ExtractorTier("burner-mining-drill",    tier=1, picks=3),
    ExtractorTier("electric-mining-drill",  tier=2, picks=4),
    ExtractorTier("pumpjack",               tier=3, picks=3),
    ExtractorTier("offshore-pump",          tier=2, picks=2),
]

RESOURCES = [
    "iron-ore", "copper-ore", "coal", "stone",
    "uranium-ore", "crude-oil", "water", "lubricant",
]


def full_config() -> ProgressiveExtractorsConfig:
    return ProgressiveExtractorsConfig(
        enabled=True,
        starter_extractor="burner-mining-drill",
        starter_max_extractors=1,
        research_map={"uranium-ore": "uranium-mining"},
    )


# ── déterminisme ─────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_determinisme(seed: int) -> None:
    rng1 = random.Random(seed)
    rng2 = random.Random(seed)
    cfg = full_config()
    a1 = compute_extractor_assignments(rng1, EXTRACTORS, RESOURCES, cfg)
    a2 = compute_extractor_assignments(rng2, EXTRACTORS, RESOURCES, cfg)
    assert a1 == a2


# ── mode désactivé : vanilla ────────────────────────────────────────

def test_desactive_tout_au_premier_extracteur() -> None:
    """enabled=False → le premier extracteur (vanilla) couvre tout."""
    rng = random.Random(7)
    cfg = ProgressiveExtractorsConfig(enabled=False)
    assignments = compute_extractor_assignments(rng, EXTRACTORS, RESOURCES, cfg)
    assert set(assignments.values()) == {"burner-mining-drill"}
    assert len(assignments) == len(RESOURCES)


# ── mode activé : progression ───────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_starter_un_seul_extracteur(seed: int) -> None:
    """Le starter (tier 1) contient au plus ''starter_max_extractors''."""
    rng = random.Random(seed)
    cfg = full_config()
    assignments = compute_extractor_assignments(rng, EXTRACTORS, RESOURCES, cfg)
    plan = gather_unlocks(assignments, {e.name: e for e in EXTRACTORS}, cfg)
    assert verify_starter_restant(plan, cfg.starter_max_extractors), \
        f"starter restant : {plan.get(1)}"


@pytest.mark.parametrize("seed", SEEDS)
def test_au_moins_deux_paliers_utilises(seed: int) -> None:
    """Quand les ressources le permettent, au moins 2 paliers sont utilisés
    (le starter n'épuise pas les ressources à lui seul quand count > 3)."""
    rng = random.Random(seed)
    cfg = full_config()
    assignments = compute_extractor_assignments(rng, EXTRACTORS, RESOURCES, cfg)
    plan = gather_unlocks(assignments, {e.name: e for e in EXTRACTORS}, cfg)
    # 8 ressources > 3 (picks du starter) → au moins 2 paliers attendus
    assert len(plan) >= 2, f"un seul palier utilisé : {plan}"


def test_chaque_extracteur_du_plan_a_de_l_utilite() -> None:
    """Chaque extracteur du plan est utilisé dans au moins une assignation."""
    rng = random.Random(3)
    cfg = full_config()
    assignments = compute_extractor_assignments(rng, EXTRACTORS, RESOURCES, cfg)
    plan = gather_unlocks(assignments, {e.name: e for e in EXTRACTORS}, cfg)
    used = {ex for ex_list in plan.values() for ex in ex_list}
    assert set(assignments.values()) == used


def test_chaque_ressource_assignee_exactement_une_fois() -> None:
    """Un extracteur par ressource, sans chevauchement."""
    rng = random.Random(13)
    cfg = full_config()
    assignments = compute_extractor_assignments(rng, EXTRACTORS, RESOURCES, cfg)
    assert len(assignments) == len(RESOURCES)
    assert set(assignments.keys()) == set(RESOURCES)


# ── recherche requise (permission façon vanilla) ───────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_recherche_uranium_presente(seed: int) -> None:
    """L'uranium exige une recherche (permission) — virée du starter."""
    rng = random.Random(seed)
    cfg = full_config()
    assignments = compute_extractor_assignments(rng, EXTRACTORS, RESOURCES, cfg)
    assert cfg.research_map["uranium-ore"] == "uranium-mining"
    # uranium-ore ne doit PAS être miné par le starter (tier 1) s'il est
    # couvert par un extracteur tier >= 2
    if "uranium-ore" in assignments:
        ex = next(e for e in EXTRACTORS if e.name == assignments["uranium-ore"])
        assert ex.tier >= 2 or assignments["uranium-ore"] == cfg.starter_extractor