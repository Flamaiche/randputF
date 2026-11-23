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
    """Élément candidat d'un ``WeightedPicker``.

    ``name`` est la valeur retournée par le tirage, ``weight`` son poids relatif (positif) et ``tags`` un ensemble libre conservé avec le candidat.
    """
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
        """Crée un pool vide.

        ``replacement=True`` conserve les éléments après ``pick`` (tirage avec
        remise) ; ``False`` (défaut) les retire (sans remise). Le pool et le
        mode sont exposés via ``items`` / ``replacement`` et mutés en place.
        """
        self.items: list[WeightedItem] = []
        self.replacement = replacement

    def add(self, name: str, weight: float = 1.0, tags: set[str] | None = None) -> None:
        """Ajoute un élément nommé au pool.

        ``name`` identifie l'élément (les doublons sont autorisés mais ``pick``
        les retire tous par nom), ``weight`` est son poids relatif (positif ;
        un poids nul le rend jamais tiré) et ``tags`` est conservé sur
        l'élément. Retourne ``None``.
        """
        self.items.append(WeightedItem(name=name, weight=weight, tags=tags or set()))

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
        """Sélectionne jusqu'à ``count`` éléments.

        ``rng`` est la source aléatoire et ``count`` le nombre demandé. Avec ``replacement=False``, chaque tirage retire l'élément ; le résultat peut donc être plus court si le pool s'épuise. Retourne la liste des noms choisis.
        """
        results = []
        for _ in range(min(count, len(self.items))):
            choice = self.pick(rng)
            if choice is None:
                break
            results.append(choice)
        return results

    def pick_with_predicate(self, rng: random.Random, predicate) -> str | None:
        """Sélectionne un élément satisfaisant ``predicate``.

        ``rng`` est la source aléatoire et ``predicate`` filtre les candidats. Le tirage est pondéré parmi les seuls candidats ; avec ``replacement=False``, l'élément choisi est retiré du pool. Retourne le nom choisi ou ``None`` si aucun candidat.
        """
        candidates = [item for item in self.items if predicate(item)]
        if not candidates:
            return None

        names = [item.name for item in candidates]
        weights = [item.weight for item in candidates]
        chosen = rng.choices(names, weights=weights, k=1)[0]

        if not self.replacement:
            self.items = [item for item in self.items if item.name != chosen]

        return chosen

    def __len__(self) -> int:
        """Retourne le nombre d'éléments actuellement dans le pool.

        Permet ``len(picker)`` ; la valeur diminue après chaque ``pick`` sans remise et sert à borner ``pick_many``.
        """
        return len(self.items)


def weighted_choice(rng: random.Random, weighted: list[tuple[int, int]]) -> int:
    """Sélection pondérée parmi des valeurs entières.

    Chaque tuple est (valeur, poids). Retourne la valeur choisie.
    Utilisé pour les choix de coûts, montants, etc.
    """
    values, weights = zip(*weighted)
    return rng.choices(values, weights=weights, k=1)[0]
