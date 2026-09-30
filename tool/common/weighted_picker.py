"""Sélection pondérée à pourcentages.

Utilitaire central pour toutes les mécaniques de pioche aléatoire pondérée.

Exemple :
    picker = WeightedPicker()
    picker.add("transformer", weight=30)
    choix = picker.pick(rng)  # probabilités configurables
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class WeightedItem:
    """Un élément avec son poids pour la sélection pondérée."""
    name: str
    weight: float
    tags: set[str] = field(default_factory=set)


class WeightedPicker:
    """Sélecteur pondéré configurable.

    Un poids élevé = plus de chances d'être sélectionné. pick() retire
    l'élément choisi du pool (sans remise) ou le garde (avec remise).

    - items : éléments pondérés
    - replacement : True si les éléments restent après sélection
    """

    def __init__(self, replacement: bool = False) -> None:
        self.items: list[WeightedItem] = []
        self.replacement = replacement

    def add(self, name: str, weight: float = 1.0, tags: set[str] | None = None) -> None:
        """Ajoute un élément au pool."""
        self.items.append(WeightedItem(name=name, weight=weight, tags=tags or set()))

    def add_many(self, items: list[tuple[str, float]]) -> None:
        """Ajoute plusieurs éléments (nom, poids)."""
        for name, weight in items:
            self.add(name, weight)

    def remove(self, name: str) -> None:
        """Retire un élément du pool par son nom."""
        self.items = [item for item in self.items if item.name != name]

    def filter_by_tags(self, required_tags: set[str]) -> list[WeightedItem]:
        """Retourne les éléments ayant TOUS les tags requis."""
        return [item for item in self.items if required_tags.issubset(item.tags)]

    def filter_by_predicate(self, predicate) -> list[WeightedItem]:
        """Filtre les éléments par un prédicat arbitraire."""
        return [item for item in self.items if predicate(item)]

    def pick(self, rng: random.Random) -> str | None:
        """Sélectionne un élément au hasard pondéré.

        Retourne le nom de l'élément choisi, ou None si le pool est vide.
        Si replacement=False, l'élément est retiré du pool.
        """
        if not self.items:
            return None

        names = [item.name for item in self.items]
        weights = [item.weight for item in self.items]

        # rng.choices retourne toujours au moins un élément
        chosen = rng.choices(names, weights=weights, k=1)[0]

        if not self.replacement:
            self.items = [item for item in self.items if item.name != chosen]

        return chosen

    def pick_many(self, rng: random.Random, count: int) -> list[str]:
        """Sélectionne plusieurs éléments (sans remise si replacement=False)."""
        results = []
        for _ in range(min(count, len(self.items))):
            choice = self.pick(rng)
            if choice is None:
                break
            results.append(choice)
        return results

    def pick_with_predicate(self, rng: random.Random, predicate) -> str | None:
        """Sélectionne un élément satisfaisant le prédicat, ou None."""
        candidates = [item for item in self.items if predicate(item)]
        if not candidates:
            return None

        names = [item.name for item in candidates]
        weights = [item.weight for item in candidates]
        chosen = rng.choices(names, weights=weights, k=1)[0]

        if not self.replacement:
            self.items = [item for item in self.items if item.name != chosen]

        return chosen

    @property
    def total_weight(self) -> float:
        """Somme des poids des candidats restants."""
        return sum(item.weight for item in self.items)

    @property
    def is_empty(self) -> bool:
        """Vrai si plus aucun candidat (sélection sans remise épuisée)."""
        return len(self.items) == 0

    def __len__(self) -> int:
        return len(self.items)


def weighted_choice(rng: random.Random, weighted: list[tuple[int, int]]) -> int:
    """Sélection pondérée parmi des valeurs entières.

    Chaque tuple est (valeur, poids). Retourne la valeur choisie.
    Utilisé pour les choix de coûts, montants, etc.
    """
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]
