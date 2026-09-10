"""Tests du prototype C1 : randomisation des ressources non-infinies.

Vérifie :
- déterminisme (même seed → même résultat) ;
- identités préservées (kind + resource inchangés) ;
- invariants de bornes (richness ≥ 1, count ≥ 1, radius ≥ 3) ;
- aucun doublon de ressource (C6) ;
- solvabilité : les ressources obligatoires du bootstrap restent présentes ;
- mode désactivé : aucune modification.
"""

from __future__ import annotations

import random

import pytest

from tool.prototypes.nonfinite_randomisation import (
    NonfiniteConfig,
    PatchSpec,
    no_duplicates,
    randomise_patches,
    verify_solvability,
)

SEEDS = (0, 5, 13, 42, 99)

# Patchs de test : un échantillon réaliste (4 items + 2 fluides)
BASE_PATCHES = [
    PatchSpec("item", "iron-ore",    richness=800000, center=(25, 30),  count=6, cluster_radius=12),
    PatchSpec("item", "copper-ore",  richness=600000, center=(-10, 50), count=5, cluster_radius=10),
    PatchSpec("item", "coal",        richness=500000, center=(40, -20), count=4, cluster_radius=9),
    PatchSpec("item", "stone",       richness=300000, center=(15, 15),  count=3, cluster_radius=8),
    PatchSpec("fluid", "water",      richness=0, center=(0, 0), count=0, cluster_radius=0),
    PatchSpec("fluid", "crude-oil",  richness=200000, center=(-30, 40), count=7, cluster_radius=11),
]

REQUIRED_ITEMS = {"iron-ore", "copper-ore", "coal"}
REQUIRED_FLUIDS = {"water"}


# ── déterminisme ─────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_determinisme(seed: int) -> None:
    """Même seed PRNG → même résultat (identique byte-for-byte)."""
    rng1 = random.Random(seed)
    rng2 = random.Random(seed)
    cfg = NonfiniteConfig(enabled=True)
    out1 = randomise_patches(rng1, BASE_PATCHES, cfg)
    out2 = randomise_patches(rng2, BASE_PATCHES, cfg)
    assert len(out1) == len(out2)
    for a, b in zip(out1, out2):
        assert a.resource == b.resource
        assert a.richness == b.richness
        assert a.count == b.count
        assert a.cluster_radius == b.cluster_radius


# ── identités préservées ─────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_identites_inchangees(seed: int) -> None:
    """L'identité (kind + resource) n'est jamais modifiée."""
    rng = random.Random(seed)
    cfg = NonfiniteConfig(enabled=True)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    for orig, modif in zip(BASE_PATCHES, out):
        assert modif.kind == orig.kind
        assert modif.resource == orig.resource


# ── bornes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_borne_richesse_positive(seed: int) -> None:
    """Richesse ≥ 1 après randomisation."""
    rng = random.Random(seed)
    cfg = NonfiniteConfig(enabled=True)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    for p in out:
        assert p.richness >= 1, f"{p.resource}: richness={p.richness}"


@pytest.mark.parametrize("seed", SEEDS)
def test_borne_count_non_zero(seed: int) -> None:
    """Count ≥ 1 quand le patch est non-nul (count original > 0)."""
    rng = random.Random(seed)
    cfg = NonfiniteConfig(enabled=True)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    for orig, modif in zip(BASE_PATCHES, out):
        if orig.count > 0:
            assert modif.count >= 1, f"{modif.resource}: count={modif.count}"


@pytest.mark.parametrize("seed", SEEDS)
def test_borne_radius(seed: int) -> None:
    """Cluster radius ≥ 3 (minimum de sécurité)."""
    rng = random.Random(seed)
    cfg = NonfiniteConfig(enabled=True)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    for p in out:
        if p.cluster_radius > 0 or p.kind == "item":
            assert p.cluster_radius >= 3, f"{p.resource}: radius={p.cluster_radius}"


# ── aucun doublon ────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_aucun_doublon(seed: int) -> None:
    """Invariant C6 : chaque ressource au plus une fois."""
    rng = random.Random(seed)
    cfg = NonfiniteConfig(enabled=True)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    assert no_duplicates(out)


# ── solvabilité ──────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_solvabilite(seed: int) -> None:
    """Les ressources obligatoires du bootstrap sont toujours présentes."""
    rng = random.Random(seed)
    cfg = NonfiniteConfig(enabled=True)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    missing = verify_solvability(out, REQUIRED_ITEMS, REQUIRED_FLUIDS)
    assert not missing, f"ressources manquantes : {missing}"


# ── mode désactivé ──────────────────────────────────────────────────

def test_desactive_sans_modification() -> None:
    """enabled=False → aucune modification, même enrichissements."""
    rng = random.Random(999)
    cfg = NonfiniteConfig(enabled=False)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    assert len(out) == len(BASE_PATCHES)
    for orig, modif in zip(BASE_PATCHES, out):
        assert modif.richness == orig.richness
        assert modif.count == orig.count
        assert modif.cluster_radius == orig.cluster_radius


# ── mode activé : les quantités changent réellement ─────────────────

def test_active_modifie_valeurs() -> None:
    """enabled=True produit des valeurs différentes (en général) de l'original."""
    rng = random.Random(7)
    cfg = NonfiniteConfig(enabled=True)
    out = randomise_patches(rng, BASE_PATCHES, cfg)
    # Au moins un patch doit avoir une richesse modifiée
    any_changed = any(
        o.richness != p.richness or o.count != p.count
        for o, p in zip(out, BASE_PATCHES)
        if p.kind == "item"  # les items ont richness > 0
    )
    assert any_changed, "enabled=True mais aucune valeur n'a changé"


# ── invariants d'orthogonalité ──────────────────────────────────────

def test_config_defaut_coherente() -> None:
    """La config par défaut est désactivée et a des bornes valides."""
    cfg = NonfiniteConfig()
    assert not cfg.enabled
    assert cfg.richness_factor_min < cfg.richness_factor_max
    assert cfg.count_factor_min < cfg.count_factor_max
    assert cfg.radius_factor_min < cfg.radius_factor_max
