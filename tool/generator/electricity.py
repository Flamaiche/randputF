"""Phase 4 : résolution de l'électricité (README §10).

L'électricité est un type à part : elle n'est pas « randputisée » en tant que
ressource. Ce qui se randomise, c'est tout ce qui l'entoure :
- Déclenchement à la demande : si un bâtiment tiré a besoin d'électricité
  dès le début, alors le réseau électrique est débloqué au début.
- Générateurs : tout ce qui peut produire de l'électricité est dans le
  même cas.
- Combustible : les bâtiments qui en CONSOMMENT (four, foreuse thermique,
  chaudière, burner-generator — `energy_type == "burner"`) reçoivent un
  combustible ITEM (les fluides sont gérés à part) via
  `recipes._ensure_burner_fuel`, appelé à chaque déblocage de bâtiment. On
  pioche un item combustible au hasard parmi tous et on crée sa recette sur
  le tas s'il n'est pas encore implémenté (§9.3). Un générateur à vapeur
  (steam-engine, turbine) n'en consomme pas.
- Amorçage sans boucle : les « lacs » (patchs fluides, dont pétrole/gaz/
  acide) sont extractibles SANS électricité via la pompe côtière
  (offshore-pump, énergie void) — `starter_chain._extractors_for_resource` +
  patch runtime data-updates.lua. L'eau comme les autres fluides alimentent
  donc le parc électrique sans dépendre d'un pumpjack électrique (§10).
- Exclusions : le réacteur nucléaire (combustible à la chaîne profonde jamais
  garantie) est écarté du tirage initial.
"""

from __future__ import annotations

import random

from tool.common.db import POWER_POLES, VanillaDB
from tool.generator.recipes import ProgressionState


def resolve_electricity(
    rng: random.Random,
    db: VanillaDB,
    starter,
) -> None:
    """Résout l'électricité : déclenchement à la demande, générateur + pylône.
    Le combustible des bâtiments burner est géré par `_unlock_building`."""
    state = starter.state
    buildings_unlocked = state.unlocked_buildings

    # Vérifier si un bâtiment électrique est déjà débloqué
    needs_electricity = _needs_electricity(db, buildings_unlocked)

    if needs_electricity:
        # Débloquer un générateur
        generator = _pick_generator(rng, db, state)
        if generator:
            _unlock_generator(rng, db, state, generator)
        # Débloquer un pylône (poteau électrique) : la distribution du courant
        # entre le générateur et les bâtiments est indispensable. Sans lui,
        # l'électricité produite ne transporte rien de jouable.
        _unlock_pole(rng, db, state)
    else:
        # Pas de besoin électrique immédiat, on passe
        pass


def _pick_pole(rng: random.Random, db: VanillaDB, state: ProgressionState):
    """Choisit un pylône réel (poteau électrique) non débloqué.

    Exclut le beacon (bâtiment de distribution mais pas un pylône : il ne
    transporte pas le courant) — le joueur doit avoir un VRAI poteau dès le
    bootstrap électrique (§10)."""
    poles = [
        b
        for b in db.buildings_of_type("distribution")
        if b.name in POWER_POLES and b.name not in state.unlocked_buildings
    ]
    if not poles:
        return None
    return rng.choice(poles)


def _unlock_pole(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> None:
    """Débloque un pylône électrique (distribution) et sa recette.

    Sans poteau, l'électricité issue du générateur ne peut pas être
    transportée jusqu'aux bâtiments qui en ont besoin (§10)."""
    pole = _pick_pole(rng, db, state)
    if pole is None:
        return
    from tool.generator.recipes import _unlock_building

    _unlock_building(rng, db, state, pole, "electricity")


def _needs_electricity(db: VanillaDB, unlocked_buildings: set[str]) -> bool:
    """Vérifie si un bâtiment débloqué a besoin d'électricité."""
    for building_name in unlocked_buildings:
        building = db.buildings.get(building_name)
        if building and building.energy_type == "electric":
            return True
    return False


# Générateurs écartés du tirage initial. Le réacteur nucléaire consomme un
# combustible dont la recette peut reposer sur une chaîne profonde (uranium,
# cells) jamais garantie amorçable au temps 0 : on préfère ne jamais lui
# confier le démarrage du réseau (§10).
_EXCLUDED_GENERATORS = frozenset({"nuclear-reactor"})

# Générateur préféré pour amorcer le réseau : la turbine (§10). Avec les
# « lacs » extractibles sans électricité, sa chaîne vapeur (chaudière +
# combustible + eau) est amorçable au bootstrap. On l'utilise quand elle est
# disponible, sinon on tire parmi les autres.
_PREFERRED_GENERATOR = "steam-turbine"


def _pick_generator(rng: random.Random, db: VanillaDB, state: ProgressionState):
    """Choisit un générateur non débloqué, hors exclusions (§10).

    L'amorçabilité ne dépend plus du type du générateur : les « lacs » (patchs
    fluides) sont extractibles sans électricité via la pompe côtière
    (offshore-pump, énergie void) — starter_chain._extractors_for_resource —
    donc l'eau comme le pétrole/gaz alimentent la chaîne vapeur de la turbine
    OU le combustible d'un burner sans boucle. On préfère la turbine
    (`_PREFERRED_GENERATOR`), sinon on tire parmi les générateurs réels
    restants (la classe `generator` exclut déjà les accumulateurs, §5)."""
    generators = [
        b
        for b in db.buildings_of_type("generator")
        if b.name not in state.unlocked_buildings
        and b.name not in _EXCLUDED_GENERATORS
    ]
    if not generators:
        return None
    preferred = [b for b in generators if b.name == _PREFERRED_GENERATOR]
    if preferred:
        return preferred[0]
    return rng.choice(generators)


def _unlock_generator(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    generator,
) -> None:
    """Débloque un générateur.

    La recette du générateur est **forcée à la main** (`handcraft=True`,
    §10) : ingrédients 100% solides, aucun atelier. En particulier jamais
    d'assembling-machine-2 ni d'usine chimique — ils exigent l'électricité
    que ce générateur est censé amorcer (antiboocle).

    Le combustible d'un éventuel générateur burner (burner-generator) est
    garanti par `_unlock_building`/`_ensure_burner_fuel` (§10) : un générateur
    qui en a besoin en reçoit un, un générateur à vapeur (steam-engine,
    turbine) n'en consomme pas et n'en reçoit donc pas."""
    from tool.generator.recipes import _unlock_building

    _unlock_building(rng, db, state, generator, "electricity", handcraft=True)
