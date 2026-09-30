"""Configuration : kit de départ, extraction et transformation.

- nombre de munitions du kit
- probabilité d'inclure un inserter
- patterns de transport par rôle
"""

from __future__ import annotations

from dataclasses import dataclass

from tool.prototypes.base import PrototypeConfig


@dataclass
class StarterConfig(PrototypeConfig):
    """Configuration pour le kit de départ et la chaîne initiale."""
    # Kit
    ammo_count: int = 50
    # Transports
    inserter_chance: float = 0.5
    # §6.2/§6.3 « late raws » : raws ``(kind, nom)`` reportées à leur jalon.
    # Posées dans la config AVANT la passe B (pipeline.generate_seed) : elles
    # ne sont pas obtenables au départ et n'entrent pas dans le watershed early
    # — « tout est déjà setté » avant le run, sans paramètre spécial à faire
    # transiter d'appel en appel.
    deferred: frozenset[tuple[str, str]] = frozenset()

    @classmethod
    def from_config(cls, config: dict) -> StarterConfig:
        """Construit la config starter depuis ``config`` — défauts du
yaml, jamais codés en dur par le moteur."""
        starter_cfg = config.get("starter", {})
        return cls(
            ammo_count=int(starter_cfg.get("ammo_count", 50)),
            inserter_chance=float(starter_cfg.get("inserter_chance", 0.5)),
            deferred=frozenset(map(tuple, starter_cfg.get("deferred", ()))),
        )