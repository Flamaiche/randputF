"""Registre central des prototypes de mécaniques.

Fournit un point d'entrée unique pour accéder à tous les prototypes.
Chaque prototype est instancié avec sa config et le pool manager.

Usage :
    from tool.prototypes import PrototypeRegistry

    registry = PrototypeRegistry.create(db, state, config)

Le registre est créé une fois par seed et réutilisé par toutes les phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from tool.common.db import VanillaDB
from tool.common.pool_manager import PoolManager
from tool.prototypes.combat import CombatConfig, CombatPrototype
from tool.prototypes.electricity import ElectricityConfig, ElectricityPrototype
from tool.prototypes.map_patches import MapPatchesConfig, MapPatchesPrototype
from tool.prototypes.recursive import RecursiveConfig, RecursivePrototype
from tool.prototypes.recipes import RecipeConfig, RecipePrototype
from tool.prototypes.science import ScienceConfig, SciencePrototype
from tool.prototypes.starter import StarterConfig, StarterKitPrototype, TransportPrototype
from tool.prototypes.tech_tree import TechTreeConfig, TechTreePrototype
from tool.prototypes.transport import CategoryTransportPrototype, TransportConfig

if TYPE_CHECKING:
    from tool.generator.recipes import ProgressionState


@dataclass
class PrototypeRegistry:
    """Registre central de tous les prototypes."""
    map_patches: MapPatchesPrototype
    starter_kit: StarterKitPrototype
    starter_transport: TransportPrototype
    recursive: RecursivePrototype
    combat: CombatPrototype
    science: SciencePrototype
    transport: CategoryTransportPrototype
    electricity: ElectricityPrototype
    recipes: RecipePrototype
    tech_tree: TechTreePrototype

    @classmethod
    def create(
        cls,
        db: VanillaDB,
        state: ProgressionState,
        config: dict,
    ) -> PrototypeRegistry:
        """Crée le registre avec tous les prototypes initialisés."""
        pool = PoolManager(db, state)

        return cls(
            map_patches=MapPatchesPrototype(
                config=MapPatchesConfig.from_config(config),
                pool=pool,
            ),
            starter_kit=StarterKitPrototype(
                config=StarterConfig.from_config(config),
                pool=pool,
            ),
            starter_transport=TransportPrototype(
                config=StarterConfig.from_config(config),
                pool=pool,
            ),
            recursive=RecursivePrototype(
                config=RecursiveConfig.from_config(config),
                pool=pool,
            ),
            combat=CombatPrototype(
                config=CombatConfig.from_config(config),
                pool=pool,
            ),
            science=SciencePrototype(
                config=ScienceConfig.from_config(config),
                pool=pool,
            ),
            transport=CategoryTransportPrototype(
                config=TransportConfig.from_config(config),
                pool=pool,
            ),
            electricity=ElectricityPrototype(
                config=ElectricityConfig.from_config(config),
                pool=pool,
            ),
            recipes=RecipePrototype(
                config=RecipeConfig.from_config(config),
                pool=pool,
            ),
            tech_tree=TechTreePrototype(
                config=TechTreeConfig.from_config(config),
                pool=pool,
            ),
        )
