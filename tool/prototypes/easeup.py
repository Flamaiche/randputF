"""Prototype : recettes alternatives « ease-up ».

Certains produits de la seed ont un craft trop lourd (graphe profond ou
boucle : ingrédient exigeant un science pack tardif). Cette phase génère une
recette ALTERNATIVE tirée du pool GELÉ de début de run, débloquée par des
techs prologue (hand-craft).

Configuration (section `easeup` dans config/settings.yaml) :
- prefix : préfixe des noms de recettes ease-up
- max_recipes : nombre max de recettes alternatives par seed
- depth_threshold : profondeur (nombre de sauts de recettes) au-delà de
  laquelle un craft est jugé trop lourd
- unlocks_per_tech : nombre max de recettes ease-up par tech de déblocage
"""

from __future__ import annotations

from dataclasses import dataclass

from tool.prototypes.base import PrototypeConfig


@dataclass
class EaseupConfig(PrototypeConfig):
    """Configuration pour la phase ease-up."""
    prefix: str = "randputf-ease-"
    max_recipes: int = 8
    depth_threshold: int = 5
    unlocks_per_tech: int = 5

    @classmethod
    def from_config(cls, config: dict) -> EaseupConfig:
        cfg = config.get("easeup", {})
        return cls(
            prefix=str(cfg.get("prefix", "randputf-ease-")),
            max_recipes=int(cfg.get("max_recipes", 8)),
            depth_threshold=int(cfg.get("depth_threshold", 5)),
            unlocks_per_tech=int(cfg.get("unlocks_per_tech", 5)),
        )