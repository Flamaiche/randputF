"""Gestionnaire de pools par catégorie (§9.1).

Gère les ensembles d'éléments disponibles pour chaque mécanique du jeu.
Chaque pool est filtré par l'état de progression et les contraintes
de la mécanique associée.

Le PoolManager est le pont entre la base de données vanilla et les
prototypes qui ont besoin de savoir "qu'est-ce qui est disponible ?".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tool.common.db import SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.common.weighted_picker import WeightedPicker

if TYPE_CHECKING:
    from tool.generator.recipes import ProgressionState


class PoolManager:
    """Gestionnaire central des pools d'éléments.

    Fournit des pools pré-filtrés pour chaque type de mécanique :
    - buildings: bâtiments non débloqués par type fonctionnel
    - items: items obtenables
    - fluids: fluides obtenables
    - weapons: armes non obtenues
    - science: packs de recherche non obtenus
    - generators: générateurs d'énergie
    - fuels: combustibles

    Chaque méthode retourne un WeightedPicker prêt à l'emploi.
    """

    # Bâtiments toujours exclus du jeu
    EXCLUDED_BUILDINGS: set[str] = {"character"}

    def __init__(self, db: VanillaDB, state: ProgressionState) -> None:
        self.db = db
        self.state = state

    def undeployed_buildings(
        self, functional_type: str, base_weights: dict[str, float] | None = None
    ) -> WeightedPicker:
        """Pool des bâtiments non débloqués d'un type fonctionnel.

        Args:
            functional_type: Le type ("transformer", "extractor", etc.)
            base_weights: Poids de base par catégorie (de CATEGORY_WEIGHTS)
        """
        picker = WeightedPicker()
        base = (base_weights or {}).get(functional_type, 10.0)

        for b in self.db.buildings_of_type(functional_type):
            if b.name in self.EXCLUDED_BUILDINGS:
                continue
            if b.name in self.state.unlocked_buildings:
                continue
            picker.add(b.name, weight=base)

        return picker

    def undeployed_weapons(self) -> WeightedPicker:
        """Pool des armes non obtenues."""
        picker = WeightedPicker()
        for item in self.db.items.values():
            if item.is_handheld_gun and item.name not in self.state.obtained_items:
                picker.add(item.name, weight=1.0)
        return picker

    def undeployed_science(self) -> WeightedPicker:
        """Pool des science packs non obtenus."""
        picker = WeightedPicker()
        for item in self.db.items.values():
            if item.is_science_pack and item.name not in self.state.obtained_items:
                picker.add(item.name, weight=1.0)
        return picker

    def available_items(self, exclude_prefix: str = "randputf-") -> WeightedPicker:
        """Pool des items obtenus (hors items générés)."""
        picker = WeightedPicker()
        for name in sorted(self.state.obtained_items):
            if not name.startswith(exclude_prefix):
                picker.add(name, weight=1.0)
        return picker

    def available_fluids(self) -> WeightedPicker:
        """Pool des fluides obtenus."""
        picker = WeightedPicker()
        for name in sorted(self.state.obtained_fluids):
            picker.add(name, weight=1.0)
        return picker

    def available_tools(self, exclude_prefix: str = "randputf-") -> WeightedPicker:
        """Pool des outils obtenus (pour coûts de recherche)."""
        picker = WeightedPicker()
        for name in sorted(self.state.obtained_items):
            if not name.startswith(exclude_prefix) and self.db.items[name].is_tool:
                picker.add(name, weight=1.0)
        return picker

    def generators(self) -> WeightedPicker:
        """Pool des générateurs d'énergie non débloqués."""
        picker = WeightedPicker()
        for b in self.db.buildings_of_type("generator"):
            if b.name not in self.state.unlocked_buildings:
                picker.add(b.name, weight=1.0)
        return picker

    def fuels(self, exclude_prefix: str = "randputf-") -> WeightedPicker:
        """Pool des combustibles disponibles."""
        picker = WeightedPicker()
        for item in self.db.fuel_items():
            if item.name not in self.state.obtained_items:
                picker.add(item.name, weight=1.0)
        return picker

    def all_undeployed(self, base_weights: dict[str, float] | None = None) -> WeightedPicker:
        """Pool combiné de toutes les catégories non déployées.

        Inclut : buildings (transformer, extractor, generator, distribution),
        combat, science. Chaque élément est tagué avec sa catégorie.
        """
        picker = WeightedPicker()
        base = base_weights or {}

        # Bâtiments par type fonctionnel
        for func_type in ("transformer", "extractor", "generator", "distribution"):
            weight = base.get(func_type, 10.0)
            for b in self.db.buildings_of_type(func_type):
                if b.name in self.EXCLUDED_BUILDINGS:
                    continue
                if b.name in self.state.unlocked_buildings:
                    continue
                picker.add(b.name, weight=weight, tags={func_type})

        # Armes
        weapon_weight = base.get("combat", 15.0)
        for item in self.db.items.values():
            if item.is_handheld_gun and item.name not in self.state.obtained_items:
                picker.add(item.name, weight=weapon_weight, tags={"combat"})

        # Science packs
        science_weight = base.get("science", 20.0)
        for item in self.db.items.values():
            if item.is_science_pack and item.name not in self.state.obtained_items:
                picker.add(item.name, weight=science_weight, tags={"science"})

        return picker
