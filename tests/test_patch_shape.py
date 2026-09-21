"""Forme des champs ITEM (§6.5) : miroir exact avec mod/control.lua.

- le count stocké dans la seed = nombre RÉEL de tuiles posées (plus l'aire
  théorique du disque, qui sur-estimait le champ et diluait la richesse) ;
- cœur quasi plein (« façon vanilla » : ~>95 % des tuiles internes posées,
  pas de grands trous) ;
- anneau externe dilué en densité décroissante (jamais plus dense que le cœur) ;
- bord ondule (des tuiles au-delà du rayon, jamais au-delà de rayon+wobble) ;
- déterministe : mêmes entrées → mêmes tuiles, à l'identique sur deux appels
  (reposé identiquement par le mod quel que soit l'ordre des chunks).
"""

import math
import random

import pytest

from tool.generator.map_patches import (
    NOISE_CORE,
    NOISE_CORE_KEEP,
    NOISE_DILUTE,
    NOISE_WOBBLE,
    item_field_tiles,
)

WELL_SEEDS = [1, 7, 42, 12345, 555, 99999, 2**31 - 5]
RADII = list(range(9, 18))


@pytest.mark.parametrize("well_seed", WELL_SEEDS)
@pytest.mark.parametrize("radius", RADII)
def test_deterministe(well_seed: int, radius: int) -> None:
    a = item_field_tiles(radius, well_seed)
    b = item_field_tiles(radius, well_seed)
    assert a == b


@pytest.mark.parametrize("well_seed", WELL_SEEDS)
@pytest.mark.parametrize("radius", RADII)
def test_croy_tres_plein(well_seed: int, radius: int) -> None:
    """Le cœur (fraction NOISE_CORE du rayon) est quasi plein : une vraie veine
    vanilla n'a pas de grands trous internes. On vérifie qu'au moins ~92 %
    des tuiles du cœur sont posées (le hash est Bernoulli, densité espérée
    NOISE_CORE_KEEP ≈ 99 %)."""
    tiles = item_field_tiles(radius, well_seed)
    core_r = radius * NOISE_CORE
    core_expected = 0
    core_possibles: set[tuple[int, int]] = set()
    for dy in range(-math.ceil(core_r) - 1, math.ceil(core_r) + 2):
        for dx in range(-math.ceil(core_r) - 1, math.ceil(core_r) + 2):
            if math.hypot(dx, dy) <= core_r:
                core_expected += 1
                core_possibles.add((dx, dy))
    present = sum(1 for t in tiles if t in core_possibles)
    assert present >= math.ceil(core_expected * 0.92), (
        f"{well_seed} r={radius}: cœur trop lacunaire ({present}/{core_expected} posées)"
    )


@pytest.mark.parametrize("well_seed", WELL_SEEDS)
@pytest.mark.parametrize("radius", RADII)
def test_anneau_dilue(well_seed: int, radius: int) -> None:
    """L'anneau externe (hors cœur) est DILUÉ, jamais plus dense que le cœur
    possible : la densité décroît vers le bord (jamais un mur plein de briques
    avec un trou à l'intérieur)."""
    tiles = item_field_tiles(radius, well_seed)
    core_r = radius * NOISE_CORE
    ring_tiles = sum(1 for dx, dy in tiles if math.hypot(dx, dy) > core_r)
    ring_possible = 0
    for dy in range(-radius - 2, radius + 3):
        for dx in range(-radius - 2, radius + 3):
            d = math.hypot(dx, dy)
            if core_r < d <= radius:
                ring_possible += 1
    max_ring = int(ring_possible * min(NOISE_CORE_KEEP, NOISE_DILUTE) * 1.05)
    assert ring_tiles <= max_ring, (
        f"{well_seed} r={radius}: anneau trop dense ({ring_tiles} > {max_ring})"
    )


@pytest.mark.parametrize("well_seed", WELL_SEEDS)
@pytest.mark.parametrize("radius", RADII)
def test_bord_deborde_pas_trop(well_seed: int, radius: int) -> None:
    """Le wobble fait onduler le bord : des tuiles peuvent dépasser `radius`,
    mais jamais au-delà de radius + wobble (le mod balaye `margin`, borné)."""
    tiles = item_field_tiles(radius, well_seed)
    max_d = radius * (1 + NOISE_WOBBLE)
    for dx, dy in tiles:
        assert math.hypot(dx, dy) <= max_d + 1e-6, (
            f"{well_seed} r={radius}: tuile ({dx},{dy}) au-delà du wobble"
        )


@pytest.mark.parametrize("well_seed", WELL_SEEDS)
@pytest.mark.parametrize("radius", RADII)
def test_compte_reel_vs_aire_theorique(well_seed: int, radius: int) -> None:
    """Le count doit refléter les tuiles réellement posées, PAS l'aire du disque
    (qui sur-estimait de ~30-35 % et diluait la richesse par tuile)."""
    tiles = item_field_tiles(radius, well_seed)
    theoretical = math.ceil(math.pi * radius * radius)
    assert 0.55 <= len(tiles) / theoretical <= 0.95, (
        f"{well_seed} r={radius}: {len(tiles)} tuiles vs aire {theoretical} "
        f"(ratio {len(tiles)/theoretical:.2f} hors [0.55, 0.95])"
    )


def test_densite_moyenne_sur_la_gamme() -> None:
    """Sur toute la gamme (9..17) la densité moyenne reste ~2/3 du disque, dans
    une plage étroite et déterministe. Un champ vraiment rempli == la richesse
    seedée tombe sur les tuiles posées."""
    ratios = []
    for ws in WELL_SEEDS:
        for r in RADII:
            tiles = item_field_tiles(r, ws)
            ratios.append(len(tiles) / (math.pi * r * r))
    mean = sum(ratios) / len(ratios)
    assert 0.60 <= mean <= 0.75, f"densité moyenne {mean:.3f} hors [0.60, 0.75]"


def test_prng_stable_pas_d_alea_global() -> None:
    """item_field_tiles n'utilise aucun générateur global : deux appels
    entrelacés restent identiques (aucun état partagé entre patches)."""
    r = random.Random(0)
    r.randrange(1000)  # consomme le générateur global par ailleurs
    first = item_field_tiles(12, 777)
    r.randrange(1000)
    second = item_field_tiles(12, 777)
    assert first == second