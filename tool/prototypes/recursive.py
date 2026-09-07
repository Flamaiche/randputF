"""Configuration : récursion pondérée (§9.1).

Configuration lue par le générateur recursive_phase :
- poids de base par catégorie
- facteur d'accélération progressive
- nombre max d'itérations
- seuil de stall (itérations sans nouveauté)
- bornes de recipes par bâtiment
- bornes de count pour les tech steps
- randomisation des armes montées (§12.1)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from tool.prototypes.base import PrototypeConfig


@dataclass
class RecursiveConfig(PrototypeConfig):
    """Configuration pour la récursion pondérée."""
    # Poids de base par catégorie (§9.1)
    category_weights: dict[str, float] = field(default_factory=lambda: {
        "transformer": 30.0,
        "extractor": 15.0,
        "generator": 10.0,
        "distribution": 10.0,
        "combat": 15.0,
        "science": 20.0,
    })
    # Facteur d'accélération progressive (§9.1)
    # Poids effectif = base × (1 + nombre_bâtiments × progressive_factor)
    progressive_factor: float = 0.15
    # Bâtiments toujours exclus
    excluded_buildings: set[str] = field(default_factory=lambda: {"character", "lab"})
    # Itérations
    max_iterations: int = 120
    stall_threshold: int = 10
    # Cadence garantie des pylônes/distribution (§9.1) : 3 pôles verrouillés
    # à des positions espacées de la récursion (chacun tire un type DIFFÉRENT,
    # jamais déjà déployé). Index = nombre de steps récursifs produits.
    # ex. (8, 28, 48) : un pôle avant ~8 steps, un autre ~20 après, un 3e ~20
    # plus loin. Le reste des distributions reste randomisé normalement.
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
    # Randomisation des armes MONTÉES (§7/§12.1) : chaque véhicule armé reçoit
    # ``vehicle_slots`` armes tirées dans ``vehicle_weapons`` — de VRAIS ITEMS
    # gun (tank-cannon, combat-shotgun, ...). La pool peut mêler les armes de
    # véhicule (jamais craftables : elles restent des données de montage) et
    # des armes de poing adoptables (ex. fusil à pompe : craftable à la main,
    # ET clonable sur un véhicule). ``vehicle_slots_with_replacement`` : tirage
    # avec remise (une même arme peut être tirée plusieurs fois puis est
    # dédupliquée) ou sans remise.
    # Portée montée (§12.1) : chaque arme assignée est CLONÉE pour le véhicule
    # (« arme dans arme »), et la portée du clone est augmentée selon la taille
    # de l'entité : facteur = 1 + max(taille - base_size, 0) × scale.
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
    # C3 : « companion guarantee » — paires/graphes d'items dépendants qui ne
    # doivent JAMAIS être diffusés loin l'un de l'autre (un robot sans roboport
    # = contenu mort). Chaque sous-liste est un groupe de compagnons mutuels :
    # dès qu'un membre est déployé (balayage §9.6 / générateur), les autres
    # membres sans recette sont créés juste après (dispatch ≤ 3 techs).
    companions: list[list[str]] = field(default_factory=lambda: [
        ["roboport", "logistic-robot", "construction-robot"],
        ["solar-panel", "accumulator"],
    ])

    @classmethod
    def from_config(cls, config: dict) -> RecursiveConfig:
        rec_cfg = config.get("recursive", {})
        return cls(
            category_weights={
                "transformer": float(rec_cfg.get("weight_transformer", 30)),
                "extractor": float(rec_cfg.get("weight_extractor", 15)),
                "generator": float(rec_cfg.get("weight_generator", 10)),
                "distribution": float(rec_cfg.get("weight_distribution", 10)),
                "combat": float(rec_cfg.get("weight_combat", 15)),
                "science": float(rec_cfg.get("weight_science", 20)),
            },
            progressive_factor=float(rec_cfg.get("progressive_factor", 0.15)),
            max_iterations=int(rec_cfg.get("max_iterations", 120)),
            stall_threshold=int(rec_cfg.get("stall_threshold", 10)),
            dist_marks=tuple(int(m) for m in rec_cfg.get("dist_marks", (8, 28, 48))),
            dist_guaranteed=int(rec_cfg.get("dist_guaranteed", 3)),
            recipes_per_building_min=int(rec_cfg.get("recipes_per_building_min", 1)),
            recipes_per_building_max=int(rec_cfg.get("recipes_per_building_max", 3)),
            tech_count_min=int(rec_cfg.get("tech_count_min", 10)),
            tech_count_max=int(rec_cfg.get("tech_count_max", 30)),
            science_cost_min=int(rec_cfg.get("science_cost_min", 5)),
            science_cost_max=int(rec_cfg.get("science_cost_max", 15)),
            armed_vehicles=[str(v) for v in rec_cfg.get("armed_vehicles", ["tank", "spidertron", "artillery-wagon"])],
            vehicle_weapons=[str(v) for v in rec_cfg.get("vehicle_weapons", [
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
            ])],
            vehicle_slots_min=int(rec_cfg.get("vehicle_slots_min", 1)),
            vehicle_slots_max=int(rec_cfg.get("vehicle_slots_max", 4)),
            vehicle_slots_with_replacement=bool(rec_cfg.get("vehicle_slots_with_replacement", True)),
            vehicle_range_base_size=float(rec_cfg.get("vehicle_range_base_size", 2.0)),
            vehicle_range_scale=float(rec_cfg.get("vehicle_range_scale", 0.4)),
            companions=[
                [str(m) for m in group]
                for group in rec_cfg.get(
                    "companions",
                    [
                        ["roboport", "logistic-robot", "construction-robot"],
                        ["solar-panel", "accumulator"],
                    ],
                )
            ],
        )

    def roll_tech_count(self, rng: random.Random) -> int:
        return rng.randint(self.tech_count_min, self.tech_count_max)

    def roll_recipes_count(self, rng: random.Random) -> int:
        return rng.randint(self.recipes_per_building_min, self.recipes_per_building_max)

    def roll_science_cost(self, rng: random.Random) -> int:
        return rng.randint(self.science_cost_min, self.science_cost_max)

    @property
    def vehicle_weapon_names(self) -> list[str]:
        """Items d'armes de la pool (ordre de config) : ``pools.vehicle_weapons``
        de la seed, et source du tirage (§7). Peut couvrir n'importe quelle
        arme gun licence (même non montée de base : ex. fusil à pompe)."""
        return list(self.vehicle_weapons)

    def roll_vehicle_slot_count(self, rng: random.Random) -> int:
        """Nombre d'emplacements d'armes d'un véhicule (§7) :
        bornes min/max de config."""
        return rng.randint(self.vehicle_slots_min, self.vehicle_slots_max)

    def companion_group_for(self, item_name: str) -> list[str] | None:
        """Groupe compagnon (C3) contenant ``item_name``, ou None."""
        for group in self.companions:
            if item_name in group:
                return list(group)
        return None