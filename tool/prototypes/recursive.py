"""Prototype : récursion pondérée (§9.1).

Gère la génération récursive de bâtiments, armes et science packs.
Chaque catégorie a un poids configurable qui évolue avec la progression.

Configuration :
- poids de base par catégorie
- facteur d'accélération progressive
- nombre max d'itérations
- seuil de stall (itérations sans nouveauté)
- bornes de recipes par bâtiment
- bornes de count pour les tech steps
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tool.common.db import VanillaDB
from tool.common.pool_manager import PoolManager
from tool.common.weighted_picker import WeightedPicker
from tool.prototypes.base import MechanicPrototype, PrototypeConfig

if TYPE_CHECKING:
    from tool.generator.recipes import ProgressionState


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


class RecursivePrototype(MechanicPrototype):
    """Prototype pour la récursion pondérée.

    Fournit les pools pondérés pour les catégories et éléments.
    Les poids progressifs sont calculés dynamiquement selon le nombre
    de bâtiments débloqués dans chaque catégorie.
    """

    def __init__(self, config: RecursiveConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool combiné de toutes les catégories non déployées."""
        return self.pool.all_undeployed(
            base_weights=self._config.category_weights
        )

    def available_categories(self, state: ProgressionState) -> list[str]:
        """Liste des catégories ayant des éléments non déployés."""
        available = []
        for cat in ("transformer", "extractor", "generator", "distribution"):
            if self._has_undeployed_buildings(cat, state):
                available.append(cat)
        if self._has_undeployed_weapons(state):
            available.append("combat")
        if self._has_undeployed_science(state):
            available.append("science")
        return available

    def pick_category(
        self, rng: random.Random, categories: list[str], state: ProgressionState
    ) -> str | None:
        """Pioche une catégorie avec poids progressifs."""
        if not categories:
            return None

        weights = []
        for cat in categories:
            base = self._config.category_weights.get(cat, 10.0)
            # Compter les bâtiments de cette catégorie déjà débloqués
            cat_count = sum(
                1 for b in state.unlocked_buildings
                if b in self._buildings_of_category(cat)
            )
            progressive = base * (1 + cat_count * self._config.progressive_factor)
            weights.append(progressive)

        return rng.choices(categories, weights=weights, k=1)[0]

    def pick_element(
        self, rng: random.Random, category: str, state: ProgressionState
    ):
        """Pioche un élément dans la catégorie donnée."""
        if category in ("transformer", "extractor", "generator", "distribution"):
            candidates = [
                b for b in self.pool.db.buildings_of_type(category)
                if b.name not in self._config.excluded_buildings
                and b.name not in state.unlocked_buildings
            ]
            return rng.choice(candidates) if candidates else None
        elif category == "combat":
            candidates = [
                i for i in self.pool.db.items.values()
                if i.is_handheld_gun and i.name not in state.obtained_items
            ]
            return rng.choice(candidates) if candidates else None
        elif category == "science":
            candidates = [
                i for i in self.pool.db.items.values()
                if i.is_science_pack and i.name not in state.obtained_items
            ]
            return rng.choice(candidates) if candidates else None
        return None

    def roll_recipes_count(self, rng: random.Random) -> int:
        """Nombre de recettes à générer pour un bâtiment."""
        return rng.randint(
            self._config.recipes_per_building_min,
            self._config.recipes_per_building_max,
        )

    def roll_tech_count(self, rng: random.Random) -> int:
        """Nombre de cycles de recherche pour un tech step."""
        return rng.randint(
            self._config.tech_count_min,
            self._config.tech_count_max,
        )

    def roll_science_cost(self, rng: random.Random) -> int:
        """Montant du coût pour un science pack."""
        return rng.randint(
            self._config.science_cost_min,
            self._config.science_cost_max,
        )

    def _has_undeployed_buildings(self, functional_type: str, state: ProgressionState) -> bool:
        for b in self.pool.db.buildings_of_type(functional_type):
            if (b.name not in self._config.excluded_buildings
                    and b.name not in state.unlocked_buildings):
                return True
        return False

    def _has_undeployed_weapons(self, state: ProgressionState) -> bool:
        return any(
            i.is_handheld_gun and i.name not in state.obtained_items
            for i in self.pool.db.items.values()
        )

    def _has_undeployed_science(self, state: ProgressionState) -> bool:
        return any(
            i.is_science_pack and i.name not in state.obtained_items
            for i in self.pool.db.items.values()
        )

    def _buildings_of_category(self, cat: str) -> set[str]:
        """Retourne les noms de bâtiments connus pour une catégorie."""
        return set()
