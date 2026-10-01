"""Prototype : recettes alternatives « ease-up ».

Certains produits de la seed ont un craft trop lourd (graphe profond ou
boucle : ingrédient exigeant un science pack tardif). Cette phase génère une
recette ALTERNATIVE tirée du pool GELÉ de début de run, débloquée par des
techs prologue (hand-craft).

Configuration (section `easeup` dans config/defaults.yaml) :
- prefix : préfixe des noms de recettes ease-up
- max_recipes : nombre max de recettes alternatives par seed
- depth_threshold : profondeur (nombre de sauts de recettes) au-delà de
  laquelle un craft est jugé trop lourd
- unlocks_per_tech : nombre max de recettes ease-up par tech de déblocage
"""

from __future__ import annotations

from dataclasses import dataclass

from tool.common import config as _cfg
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
        """Construit la config easeup depuis ``config`` — défauts du
yaml, jamais codés en dur par le moteur."""
        cfg = config.get("easeup", {})
        return cls(
            prefix=str(cfg.get("prefix", _cfg.default_value("easeup", "prefix"))),
            max_recipes=int(cfg.get("max_recipes", _cfg.default_value("easeup", "max_recipes"))),
            depth_threshold=int(cfg.get("depth_threshold", _cfg.default_value("easeup", "depth_threshold"))),
            unlocks_per_tech=int(cfg.get("unlocks_per_tech", _cfg.default_value("easeup", "unlocks_per_tech"))),
        )