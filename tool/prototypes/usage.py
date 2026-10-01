"""Prototype D2 : garantie d'usage « dure » (bâtiment avant usage, niveau seed).

Garantit, sur la seed assemblée, deux invariants qui complètent la garantie de
fabricabilité montante (C2, pilotée par la recette) : l'usage DESCENDANT.

- U1 — usage non-nul : tout bâtiment unlocké (recette ``randputf-<b>`` présente)
  héberge ≥ 1 recette de la seed (par ``crafted_in`` ou une ``category`` dans ses
  ``crafting_categories``), sauf bâtiments terminaux (lab, rocket-silo,
  générateurs — l'usage est leur rôle moteur, vérifié via le graphe) et sauf le
  kit du starter.
- U2 — ordre strict : pour chaque recette R hébergée dans un bâtiment B, la tech
  qui unlock R vient à un index ≥ la tech qui unlock B (« la tech d'avant », §7).
  Exception : les bâtiments du kit de départ (réputés débloqués en tech 0) et les
  auto-consommations œuf/poule du bootstrap.

Configuration (section ``usage:`` dans config/defaults.yaml) :
- enabled : activation de la passe (défaut true — invariant, pas optionnel)
- strict_order : applique U2 (réordonnancement) ou seulement U1
- kit_exempt : bâtiments réputés débloqués dès la tech 0 (déduits du kit sinon)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common import config as _cfg
from tool.prototypes.base import PrototypeConfig


@dataclass
class UsageConfig(PrototypeConfig):
    """Configuration pour la garantie d'usage dure (D2)."""
    enabled: bool = True
    strict_order: bool = True
    # Bâtiments terminaux : leur usage est leur rôle moteur, pas une recette
    # hébergée (lab = consommation de packs, rocket-silo = lancement, etc.).
    terminal_buildings: frozenset[str] = field(
        default_factory=lambda: frozenset({"lab", "rocket-silo"})
    )
    # Bâtiments livrés par le kit de départ → réputés débloqués en tech 0.
    kit_exempt: frozenset[str] = frozenset()

    @classmethod
    def from_config(cls, config: dict) -> UsageConfig:
        """Construit la config usage depuis ``config`` — défauts du
yaml, jamais codés en dur par le moteur."""
        cfg = config.get("usage", {})
        return cls(
            enabled=bool(cfg.get("enabled", _cfg.default_value("usage", "enabled"))),
            strict_order=bool(cfg.get("strict_order", _cfg.default_value("usage", "strict_order"))),
            terminal_buildings=frozenset(
                cfg.get("terminal_buildings", _cfg.default_value("usage", "terminal_buildings"))
            ),
            kit_exempt=frozenset(cfg.get("kit_exempt", _cfg.default_value("usage", "kit_exempt"))),
        )