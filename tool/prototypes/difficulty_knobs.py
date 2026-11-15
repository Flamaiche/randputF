"""Prototype C3 : knobs de difficulté par seed.

La seed dérive (déterministe via son PRNG) des valeurs de map settings :
``starting_area``, densité de nids / évolution, pollution, falaises, biome
de départ. Sortie compatible ``map_gen_settings``.

Solvabilité : le profil est imposé AVANT le bootstrap ; il ne doit pas rendre
le démarrage injuste (forêt trop pauvre en bois, starting_area trop petite).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.prototypes.base import PrototypeConfig


@dataclass
class DifficultyConfig(PrototypeConfig):
    """Configuration des knobs de difficulté par seed.

    ``enabled`` active la dérivation ; chaque knob est une paire de bornes (aire de départ, nids, évolution, pollution, falaises) et ``biomes`` liste les biomes de départ autorisés.
    """
    enabled: bool = False
    # bornes (min, max) de chaque knob
    starting_area: tuple[int, int] = (2, 5)        # taille (vanilla ≈ 2)
    nest_density: tuple[float, float] = (1.0, 3.0) # × densité nids
    evolution_factor: tuple[float, float] = (0.25, 1.5)
    pollution_factor: tuple[float, float] = (0.5, 2.0)
    cliff_density: tuple[float, float] = (0.5, 2.0)
    # biomes de départ possibles
    biomes: tuple[str, ...] = ("plains", "forest", "desert")

    @classmethod
    def from_config(cls, config: dict) -> DifficultyConfig:
        """Construit la configuration ``difficulty`` depuis le dict complet.

        ``config`` peut être partiel ; les clés absentes prennent les défauts du YAML. Retourne une ``DifficultyConfig`` avec des bornes converties en tuples.
        """
        cfg = config.get("difficulty", {})
        return cls(
            enabled=bool(cfg.get("enabled", False)),
            starting_area=tuple(int(x) for x in cfg.get("starting_area", (2, 5))),
            nest_density=tuple(float(x) for x in cfg.get("nest_density", (1.0, 3.0))),
            evolution_factor=tuple(float(x) for x in cfg.get("evolution_factor", (0.25, 1.5))),
            pollution_factor=tuple(float(x) for x in cfg.get("pollution_factor", (0.5, 2.0))),
            cliff_density=tuple(float(x) for x in cfg.get("cliff_density", (0.5, 2.0))),
            biomes=tuple(cfg.get("biomes", ("plains", "forest", "desert"))),
        )


@dataclass
class DifficultyProfile:
    """Profil de difficulté concret d'une seed.

    Porte les valeurs tirées pour ``starting_area``, ``nest_density``, ``evolution_factor``, ``pollution_factor``, ``cliff_density`` et ``biome``. ``to_map_settings`` le sérialise.
    """
    starting_area: int
    nest_density: float
    evolution_factor: float
    pollution_factor: float
    cliff_density: float
    biome: str

    def to_map_settings(self) -> dict:
        """Sérialise le profil en ``map_gen_settings`` simplifié.

        Retourne un dict contenant l'aire de départ, l'expansion ennemie, l'évolution, la pollution, les falaises et le biome. Les valeurs sont directement dérivées des champs du profil.
        """
        return {
            "starting_area": self.starting_area,
            "enemy_expansion": {"expansion_cooldown": int(3600 / self.nest_density)},
            "evolution": {"time_factor": self.evolution_factor},
            "pollution": {"diffusion_ratio": self.pollution_factor},
            "cliffs": {"density": self.cliff_density},
            "autoplace_controls": {
                "enemy-base": {"frequency": self.nest_density},
                "cliff": {"frequency": self.cliff_density},
            },
            "biome_tag": self.biome,
        }


def derive_difficulty_profile(
    rng: random.Random,
    config: DifficultyConfig,
) -> DifficultyProfile:
    """Dérive le profil de difficulté d'une seed, déterministe.

    - ``enabled=False`` → profil vanilla (valeurs neutres).
    - ``enabled=True`` → chaque valeur tirée dans sa plage.
    """
    if not config.enabled:
        return DifficultyProfile(
            starting_area=2,
            nest_density=1.0,
            evolution_factor=1.0,
            pollution_factor=1.0,
            cliff_density=1.0,
            biome="plains",
        )

    return DifficultyProfile(
        starting_area=config.starting_area[0]
        + rng.randint(0, max(0, config.starting_area[1] - config.starting_area[0])),
        nest_density=rng.uniform(*config.nest_density),
        evolution_factor=rng.uniform(*config.evolution_factor),
        pollution_factor=rng.uniform(*config.pollution_factor),
        cliff_density=rng.uniform(*config.cliff_density),
        biome=rng.choice(config.biomes),
    )