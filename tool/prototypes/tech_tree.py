"""Prototype : arbre technologique (§13).

Gère les paramètres de génération de l'arbre tech :
- coûts progressifs (ingrédients, montants)
- nombre de cycles de recherche
- groupage par catégorie
- noms des tech nodes

Configuration :
- seuils de profondeur pour les paliers de coûts
- plages de montants par palier
- plages de cycles de recherche par palier
- format des noms de tech nodes
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
class CostTier:
    """Un palier de coûts pour l'arbre tech."""
    depth_threshold: float  # ratio < threshold → ce palier
    n_ingredients: int
    amount_min: int
    amount_max: int


@dataclass
class CountTier:
    """Un palier de cycles de recherche."""
    depth_threshold: float
    count_min: int
    count_max: int


@dataclass
class TechTreeConfig(PrototypeConfig):
    """Configuration pour l'arbre technologique."""
    # Paliers de coûts (triés par profondeur croissante)
    cost_tiers: list[CostTier] = field(default_factory=lambda: [
        CostTier(depth_threshold=0.15, n_ingredients=1, amount_min=3, amount_max=5),
        CostTier(depth_threshold=0.40, n_ingredients=2, amount_min=5, amount_max=10),
        CostTier(depth_threshold=0.70, n_ingredients=3, amount_min=8, amount_max=15),
        CostTier(depth_threshold=1.01, n_ingredients=4, amount_min=12, amount_max=25),
    ])
    # Paliers de cycles de recherche
    count_tiers: list[CountTier] = field(default_factory=lambda: [
        CountTier(depth_threshold=0.30, count_min=5, count_max=10),
        CountTier(depth_threshold=0.70, count_min=10, count_max=20),
        CountTier(depth_threshold=1.01, count_min=15, count_max=30),
    ])
    # Format des noms de tech nodes groupées
    node_id_format: str = "randputf-{cat}-tier-{index}"
    # Nombre de techs gratuites en début d'arbre
    free_techs_count: int = 2

    @classmethod
    def from_config(cls, config: dict) -> TechTreeConfig:
        tech_cfg = config.get("tech_tree", {})
        return cls(
            free_techs_count=int(tech_cfg.get("free_techs", 2)),
        )


class TechTreePrototype(MechanicPrototype):
    """Prototype pour l'arbre technologique.

    Fournit les paramètres de calcul des coûts et cycles.
    Utilisé par tech_graph.build_tech_graph().
    """

    def __init__(self, config: TechTreeConfig, pool: PoolManager) -> None:
        super().__init__(config, pool)
        self._config = config

    def build_picker(self) -> WeightedPicker:
        """Pool de candidats pour les coûts de recherche."""
        return self.pool.available_tools()

    def cost_for_depth(self, depth: int, total: int, candidates: list[str]) -> list[dict]:
        """Calcule le coût d'un nœud à une profondeur donnée.

        Utilise les paliers de coûts configurés.
        Retourne une liste de {type: "item", name: ..., amount: ...}.
        """
        ratio = depth / max(total - 1, 1)

        # Trouver le bon palier
        tier = self._config.cost_tiers[-1]  # palier par défaut = le dernier
        for t in self._config.cost_tiers:
            if ratio < t.depth_threshold:
                tier = t
                break

        n_ingredients = min(tier.n_ingredients, len(candidates))
        if n_ingredients == 0:
            return []

        # Sélection déterministe basée sur la profondeur
        import hashlib
        seed_bytes = f"cost:{depth}".encode()
        h = hashlib.md5(seed_bytes).hexdigest()

        selected = []
        used_indices = set()
        for i in range(n_ingredients):
            idx = int(h[i * 2: i * 2 + 2], 16) % len(candidates)
            attempts = 0
            while idx in used_indices and attempts < len(candidates):
                idx = (idx + 1) % len(candidates)
                attempts += 1
            if idx not in used_indices:
                used_indices.add(idx)
                selected.append(candidates[idx])

        ingredients = []
        for i, name in enumerate(selected):
            amount_hash = int(h[i * 2 + 8: i * 2 + 10], 16) if i * 2 + 10 <= len(h) else i + 1
            amount = tier.amount_min + (amount_hash % (tier.amount_max - tier.amount_min + 1))
            ingredients.append({"type": "item", "name": name, "amount": amount})

        return ingredients

    def count_for_depth(self, depth: int, total: int) -> int:
        """Calcule le nombre de cycles de recherche pour un nœud."""
        ratio = depth / max(total - 1, 1)

        import hashlib
        seed_bytes = f"count:{depth}".encode()
        h = hashlib.md5(seed_bytes).hexdigest()
        seed_val = int(h[:4], 16)

        # Trouver le bon palier
        tier = self._config.count_tiers[-1]
        for t in self._config.count_tiers:
            if ratio < t.depth_threshold:
                tier = t
                break

        return tier.count_min + (seed_val % (tier.count_max - tier.count_min + 1))

    def node_id(self, category: str, index: int) -> str:
        """Génère l'ID d'un nœud tech groupé."""
        return self._config.node_id_format.format(cat=category, index=index)

    @property
    def free_techs_count(self) -> int:
        return self._config.free_techs_count
