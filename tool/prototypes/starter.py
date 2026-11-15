"""Configuration : kit de départ, extraction et transformation.

- nombre de munitions du kit
- probabilité d'inclure un inserter
- patterns de transport par rôle
"""

from __future__ import annotations

from dataclasses import dataclass

from tool.common import config as _cfg
from tool.prototypes.base import PrototypeConfig


@dataclass
class StarterConfig(PrototypeConfig):
    """Configuration du kit de départ et de la chaîne initiale.

    Porte le nombre de munitions, la probabilité d'inserter, la quantité de combustible au spawn et ``deferred`` (raws reportées à leur jalon). Les valeurs sont lues par ``from_config``.
    """
    # Kit
    ammo_count: int = 50
    # Transports
    inserter_chance: float = 0.5
    # Quantité de combustible du kit quand le fabricateur/extracteur est burner.
    spawn_fuel_count: int = 50
    # §6.2/§6.3 « late raws » : raws ``(kind, nom)`` reportées à leur jalon.
    # Posées dans la config AVANT la passe B (pipeline.generate_seed) : elles
    # ne sont pas obtenables au départ et n'entrent pas dans le watershed early
    # — « tout est déjà setté » avant le run, sans paramètre spécial à faire
    # transiter d'appel en appel.
    deferred: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def from_config(cls, config: dict) -> StarterConfig:
        """Construit la configuration ``starter`` depuis le dict complet.

        ``config`` peut être partiel ; les clés absentes prennent les défauts du YAML. Retourne une ``StarterConfig`` avec ``deferred`` converti en ``frozenset`` de tuples.
        """
        starter_cfg = config.get("starter", {})
        return cls(
            ammo_count=int(starter_cfg.get("ammo_count", _cfg.default_value("starter", "ammo_count"))),
            inserter_chance=float(starter_cfg.get("inserter_chance", _cfg.default_value("starter", "inserter_chance"))),
            spawn_fuel_count=int(starter_cfg.get("spawn_fuel_count", _cfg.default_value("starter", "spawn_fuel_count"))),
            deferred=frozenset(map(tuple, starter_cfg.get("deferred", ()))),
        )