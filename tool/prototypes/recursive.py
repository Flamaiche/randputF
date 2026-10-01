"""Configuration : récursion pondérée.

- poids de base par catégorie
- facteur d'accélération progressive
- nombre max d'itérations
- seuil de stall (itérations sans nouveauté)
- bornes de recipes par bâtiment
- bornes de count pour les tech steps
- randomisation des armes montées
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.common import config as _cfg
from tool.prototypes.base import PrototypeConfig


@dataclass
class RecursiveConfig(PrototypeConfig):
    """Configuration pour la récursion pondérée."""
    # Poids de base par catégorie
    category_weights: dict[str, float] = field(default_factory=lambda: {
        "transformer": 30.0,
        "extractor": 15.0,
        "generator": 10.0,
        "distribution": 10.0,
        "combat": 15.0,
        "science": 20.0,
    })
    # Facteur d'accélération progressive
    # Poids effectif = base × (1 + nombre_bâtiments × progressive_factor)
    progressive_factor: float = 0.15
    # Bâtiments toujours exclus
    excluded_buildings: set[str] = field(default_factory=lambda: {"character", "lab"})
    # Itérations
    max_iterations: int = 120
    stall_threshold: int = 10
    # Cadence garantie des pylônes : 3 pôles à positions espacées de la récursion
    # (chacun tire un type DIFFÉRENT, jamais déjà déployé). Ex. (8, 28, 48).
    dist_marks: tuple[int, int, int] = (8, 28, 48)
    dist_guaranteed: int = 3
    # Recipes par bâtiment
    recipes_per_building_min: int = 1
    recipes_per_building_max: int = 3
    # Tech steps
    tech_count_min: int = 10
    tech_count_max: int = 30
    science_cost_min: int = 5
    science_cost_max: int = 15
    # Randomisation des armes MONTÉES : chaque véhicule armé reçoit
    # ``vehicle_slots`` armes tirées dans ``vehicle_weapons``.
    # Portée montée : chaque arme est clonée pour le véhicule, portée
    # augmentée selon la taille : facteur = 1 + max(taille - base_size, 0) × scale.
    armed_vehicles: list[str] = field(default_factory=lambda: ["tank", "spidertron", "artillery-wagon"])
    vehicle_weapons: list[str] = field(default_factory=lambda: [
        "tank-cannon",
        "vehicle-machine-gun",
        "tank-flamethrower",
        "artillery-wagon-cannon",
        "spidertron-rocket-launcher-1",
        "pistol",
        "submachine-gun",
        "shotgun",
        "combat-shotgun",
        "rocket-launcher",
        "flamethrower",
    ])
    vehicle_slots_min: int = 1
    vehicle_slots_max: int = 4
    vehicle_slots_with_replacement: bool = True
    vehicle_range_base_size: float = 2.0
    vehicle_range_scale: float = 0.4
    # Paires/graphes d'items dépendants qui ne doivent jamais être diffusés
    # loin l'un de l'autre (un robot sans roboport = contenu mort).
    companions: list[list[str]] = field(default_factory=lambda: [
        ["roboport", "logistic-robot", "construction-robot"],
        ["solar-panel", "accumulator"],
    ])

    @classmethod
    def from_config(cls, config: dict) -> RecursiveConfig:
        """Construit la config recursive depuis ``config`` — défauts du
yaml, jamais codés en dur par le moteur."""
        rec_cfg = config.get("recursive", {})
        return cls(
            category_weights={
                "transformer": float(rec_cfg.get("weight_transformer", _cfg.default_value("recursive", "weight_transformer"))),
                "extractor": float(rec_cfg.get("weight_extractor", _cfg.default_value("recursive", "weight_extractor"))),
                "generator": float(rec_cfg.get("weight_generator", _cfg.default_value("recursive", "weight_generator"))),
                "distribution": float(rec_cfg.get("weight_distribution", _cfg.default_value("recursive", "weight_distribution"))),
                "combat": float(rec_cfg.get("weight_combat", _cfg.default_value("recursive", "weight_combat"))),
                "science": float(rec_cfg.get("weight_science", _cfg.default_value("recursive", "weight_science"))),
            },
            progressive_factor=float(rec_cfg.get("progressive_factor", _cfg.default_value("recursive", "progressive_factor"))),
            excluded_buildings=set(
                rec_cfg.get("excluded_buildings", _cfg.default_value("recursive", "excluded_buildings"))
            ),
            max_iterations=int(rec_cfg.get("max_iterations", _cfg.default_value("recursive", "max_iterations"))),
            stall_threshold=int(rec_cfg.get("stall_threshold", _cfg.default_value("recursive", "stall_threshold"))),
            dist_marks=tuple(int(m) for m in rec_cfg.get("dist_marks", _cfg.default_value("recursive", "dist_marks"))),
            dist_guaranteed=int(rec_cfg.get("dist_guaranteed", _cfg.default_value("recursive", "dist_guaranteed"))),
            recipes_per_building_min=int(rec_cfg.get("recipes_per_building_min", _cfg.default_value("recursive", "recipes_per_building_min"))),
            recipes_per_building_max=int(rec_cfg.get("recipes_per_building_max", _cfg.default_value("recursive", "recipes_per_building_max"))),
            tech_count_min=int(rec_cfg.get("tech_count_min", _cfg.default_value("recursive", "tech_count_min"))),
            tech_count_max=int(rec_cfg.get("tech_count_max", _cfg.default_value("recursive", "tech_count_max"))),
            science_cost_min=int(rec_cfg.get("science_cost_min", _cfg.default_value("recursive", "science_cost_min"))),
            science_cost_max=int(rec_cfg.get("science_cost_max", _cfg.default_value("recursive", "science_cost_max"))),
            armed_vehicles=[str(v) for v in rec_cfg.get("armed_vehicles", _cfg.default_value("recursive", "armed_vehicles"))],
            vehicle_weapons=[str(v) for v in rec_cfg.get("vehicle_weapons", _cfg.default_value("recursive", "vehicle_weapons"))],
            vehicle_slots_min=int(rec_cfg.get("vehicle_slots_min", _cfg.default_value("recursive", "vehicle_slots_min"))),
            vehicle_slots_max=int(rec_cfg.get("vehicle_slots_max", _cfg.default_value("recursive", "vehicle_slots_max"))),
            vehicle_slots_with_replacement=bool(rec_cfg.get("vehicle_slots_with_replacement", _cfg.default_value("recursive", "vehicle_slots_with_replacement"))),
            vehicle_range_base_size=float(rec_cfg.get("vehicle_range_base_size", _cfg.default_value("recursive", "vehicle_range_base_size"))),
            vehicle_range_scale=float(rec_cfg.get("vehicle_range_scale", _cfg.default_value("recursive", "vehicle_range_scale"))),
            companions=[
                [str(m) for m in group]
                for group in rec_cfg.get("companions", _cfg.default_value("recursive", "companions"))
            ],
        )

    def roll_tech_count(self, rng: random.Random) -> int:
        """Nombre de technologies enfant tiré au sort (bornes config)."""
        return rng.randint(self.tech_count_min, self.tech_count_max)

    def roll_recipes_count(self, rng: random.Random) -> int:
        """Nombre de recettes par bâtiment tiré au sort (bornes config)."""
        return rng.randint(self.recipes_per_building_min, self.recipes_per_building_max)

    def roll_science_cost(self, rng: random.Random) -> int:
        """Coût en packs de science d'une tech tiré au sort (bornes config)."""
        return rng.randint(self.science_cost_min, self.science_cost_max)

    @property
    def vehicle_weapon_names(self) -> list[str]:
        """Items d'armes de la pool (ordre de config)."""
        return list(self.vehicle_weapons)

    def roll_vehicle_slot_count(self, rng: random.Random) -> int:
        """Nombre d'emplacements d'armes d'un véhicule."""
        return rng.randint(self.vehicle_slots_min, self.vehicle_slots_max)

    def companion_group_for(self, item_name: str) -> list[str] | None:
        """Groupe compagnon (C3) contenant ``item_name``, ou None."""
        for group in self.companions:
            if item_name in group:
                return list(group)
        return None