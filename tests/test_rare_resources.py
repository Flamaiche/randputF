"""Tests du prototype « ressources rares au début » (mode exploration).

Vérifie :
- déterminisme (même seed → même résultat) ;
- mode désactivé → aucune modification ;
- mode activé → les patchs lointains sont plus riches que les proches ;
- les ressources obligatoires restent proches du spawn (solvabilité) ;
- aucun patch nul (richesse ≥ 1, count ≥ 1) ;
- factorisation terrain monotone (loi de distance).
"""

from __future__ import annotations

import random

import pytest

from tool.prototypes.rare_resources import (
    RarePatch,
    RareResourcesConfig,
    apply_rare_mode,
    terrain_factor,
    verify_no_zero,
    verify_required_near_spawn,
)

SEEDS = (0, 5, 13, 42, 99)

# Patchs avec distances variées : proche (10), moyen (60), lointain (150)
BASE_PATCHES = [
    RarePatch("iron-ore",    10000, 5, 10),
    RarePatch("copper-ore",   8000, 4, 12),
    RarePatch("coal",         5000, 3, 15),
    RarePatch("water",           0, 3, 20),
    RarePatch("stone",        3000, 2, 60),
    RarePatch("crude-oil",   20000, 6, 150),
    RarePatch("uranium-ore", 15000, 4, 180),
]

REQUIRED = ("iron-ore", "copper-ore", "coal", "water")


# ── déterminisme ─────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_determinisme(seed: int) -> None:
    rng1 = random.Random(seed)
    rng2 = random.Random(seed)
    cfg = RareResourcesConfig(enabled=True)
    out1 = apply_rare_mode(rng1, BASE_PATCHES, cfg)
    out2 = apply_rare_mode(rng2, BASE_PATCHES, cfg)
    assert out1 == out2


# ── mode désactivé ──────────────────────────────────────────────────

def test_desactive_aucune_modification() -> None:
    rng = random.Random(999)
    cfg = RareResourcesConfig(enabled=False)
    out = apply_rare_mode(rng, BASE_PATCHES, cfg)
    assert out == BASE_PATCHES


# ── rareté progressive ──────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_lointain_plus_riche_que_proche(seed: int) -> None:
    """En mode activé, un patch lointain devient plus riche (per capita) que
    le même patch proche — à distance égale, le facteur est identique."""
    rng = random.Random(seed)
    cfg = RareResourcesConfig(enabled=True)
    # Patchs de référence : le même gisement à 10 vs 150 tuiles.
    near = apply_rare_mode(rng, [RarePatch("x", 1000, 4, 10)], cfg)
    far = apply_rare_mode(rng, [RarePatch("x", 1000, 4, 150)], cfg)
    assert far[0].richness > near[0].richness
    if far[0].count > 0 and near[0].count > 0:
        assert far[0].count >= near[0].count


# ── solvabilité : obligations proches ───────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_ressources_obligatoires_proches_du_spawn(seed: int) -> None:
    """Les 4 ressources obligatoires du bootstrap ont toujours un gisement
    proche (≤ near_radius) — le mode rareté ne bloque pas le démarrage."""
    rng = random.Random(seed)
    cfg = RareResourcesConfig(enabled=True)
    out = apply_rare_mode(rng, BASE_PATCHES, cfg)
    assert verify_required_near_spawn(out, REQUIRED, cfg.near_radius)


# ── aucun patch nul ─────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_aucun_patch_nul(seed: int) -> None:
    """Richesse ≥ 1 et count ≥ 1 pour tous les patchs (bornes de sécurité)."""
    rng = random.Random(seed)
    cfg = RareResourcesConfig(enabled=True)
    out = apply_rare_mode(rng, BASE_PATCHES, cfg)
    assert verify_no_zero(out)


# ── loi de terrain monotone ─────────────────────────────────────────

def test_factorisation_terrain_monotone() -> None:
    """Plus on s'éloigne, plus les facteurs croissent (jamais décroissants)."""
    cfg = RareResourcesConfig(enabled=True)
    prev_r = 0.0
    prev_c = 0.0
    for dist in (0, 20, 40, 60, 80, 100, 120, 200):
        r, c = terrain_factor(dist, cfg)
        assert r >= prev_r, f"richesse décroissante à {dist}"
        assert c >= prev_c, f"count décroissant à {dist}"
        prev_r, prev_c = r, c


# ── interpolation continue ──────────────────────────────────────────

def test_interpolation_continue() -> None:
    """terrain_factor est borné entre les facteurs extrêmes."""
    cfg = RareResourcesConfig(enabled=True)
    for dist in (0, 5, 10, 25, 40, 80, 120, 250):
        r, c = terrain_factor(dist, cfg)
        assert cfg.near_richness_factor <= r <= cfg.far_richness_factor
        assert cfg.near_count_factor <= c <= cfg.far_count_factor