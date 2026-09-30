"""Tests du prototype : knobs de difficulté par seed.

Vérifie :
- déterminisme (même seed → même profil) ;
- bornes de chaque knob respectées ;
- mode désactivé → profil vanilla neutre ;
- sérialisation map_settings valide (types, cohérence) ;
- invariants de solvabilité (le profil n'outre-passe pas les bornes qui
  rendraient le bootstrap jouable — starting_area jamais < 1).
"""

from __future__ import annotations

import random

import pytest

from tool.prototypes.difficulty_knobs import (
    DifficultyConfig,
    derive_difficulty_profile,
)

SEEDS = (0, 5, 13, 42, 99)


# ── déterminisme ─────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_determinisme(seed: int) -> None:
    rng1 = random.Random(seed)
    rng2 = random.Random(seed)
    cfg = DifficultyConfig(enabled=True)
    p1 = derive_difficulty_profile(rng1, cfg)
    p2 = derive_difficulty_profile(rng2, cfg)
    assert p1 == p2


# ── bornes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_kobs_dans_les_bornes(seed: int) -> None:
    rng = random.Random(seed)
    cfg = DifficultyConfig(enabled=True)
    p = derive_difficulty_profile(rng, cfg)
    assert 2 <= p.starting_area <= 5, f"starting_area={p.starting_area}"
    assert 1.0 <= p.nest_density <= 3.0, f"nest_density={p.nest_density}"
    assert 0.25 <= p.evolution_factor <= 1.5, f"evolution_factor={p.evolution_factor}"
    assert 0.5 <= p.pollution_factor <= 2.0, f"pollution_factor={p.pollution_factor}"
    assert 0.5 <= p.cliff_density <= 2.0, f"cliff_density={p.cliff_density}"
    assert p.biome in cfg.biomes, f"biome={p.biome}"


# ── mode désactivé ──────────────────────────────────────────────────

def test_desactive_profil_vanilla() -> None:
    rng = random.Random(999)
    cfg = DifficultyConfig(enabled=False)
    p = derive_difficulty_profile(rng, cfg)
    assert p.starting_area == 2
    assert p.nest_density == 1.0
    assert p.evolution_factor == 1.0
    assert p.pollution_factor == 1.0
    assert p.cliff_density == 1.0
    assert p.biome == "plains"


# ── sérialisation ───────────────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_serialisation_map_settings(seed: int) -> None:
    rng = random.Random(seed)
    cfg = DifficultyConfig(enabled=True)
    p = derive_difficulty_profile(rng, cfg)
    ms = p.to_map_settings()
    assert isinstance(ms["starting_area"], int)
    assert isinstance(ms["evolution"]["time_factor"], float)
    assert isinstance(ms["pollution"]["diffusion_ratio"], float)
    assert "enemy-base" in ms["autoplace_controls"]
    assert "cliff" in ms["autoplace_controls"]
    assert ms["biome_tag"] in cfg.biomes
    # cohérence : density nid > 0, jamais négatif
    assert ms["autoplace_controls"]["enemy-base"]["frequency"] > 0


# ── solvabilité bootstrap ───────────────────────────────────────────

@pytest.mark.parametrize("seed", SEEDS)
def test_starting_area_jamais_trop_petite(seed: int) -> None:
    """Invariant de solvabilité : la zone de départ protégée (starting_area)
    n'est jamais < 1 (elle garantit au joueur un périmètre sans nids)."""
    rng = random.Random(seed)
    cfg = DifficultyConfig(enabled=True, starting_area=(1, 3))
    p = derive_difficulty_profile(rng, cfg)
    assert p.starting_area >= 1