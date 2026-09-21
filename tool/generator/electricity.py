"""Phase 4 : résolution de l'électricité (§10).

L'électricité n'est pas « randputisée » en tant que ressource ; se randomise
tout ce qui l'entoure :
- Déclenchement à la demande : si un bâtiment tiré est électrique, le réseau
  est débloqué au début.
- Générateurs : tous les producteurs de courant sont candidats, à l'exception
  du réacteur nucléaire (combustible à chaîne profonde jamais garantie).
- Combustible : les brûleurs (energy_type == "burner") reçoivent un
  combustible ITEM (les fluides à part) via `recipes._ensure_burner_fuel`,
  appelé à chaque déblocage de bâtiment.
- Amorçage sans boucle : un générateur à vapeur (fluid_inputs > 0) exige un
  fluide extractible SANS ÉLECTRICITÉ — donc un LAC (pompe offshore, énergie
  void) ; une ressource en PATCH exigerait un pumpjack électrique (boucle
  fuel→électricité→fuel). La turbine est amorçable ssi la seed tire au moins
  un lac.

Résolution robuste : on ne décide pas a priori quel générateur « doit »
marcher. On shuffle la liste des générateurs et on teste un par un jusqu'à en
trouver un fonctionnel. Si AUCUN, on force un patch (item OU lac fluide,
ressource ≠ du type précédent), puis on re-shuffle et on revérifie. Après 20
essais, erreur explicite — jamais une seed silencieusement cassée.
"""

from __future__ import annotations

import random

from tool.common.db import VanillaDB
from tool.generator.recipes import ProgressionState

# Générateur préféré : la turbine (§10). Avec les lacs extractibles sans
# électricité, sa chaîne (un fluide en entrée) est amorçable au bootstrap.
_PREFERRED_GENERATOR = "steam-turbine"

# Borne du cycle de réparation : au-delà, erreur.
MAX_REPAIR_ATTEMPTS = 20


def _is_steam_generator(building) -> bool:
    """Générateur à vapeur (fluid_inputs > 0) : steam-engine / steam-turbine.
    Son amorçage dépend d'un fluide extractible sans électricité (un lac)."""
    return getattr(building, "fluid_inputs", 0) > 0


def _has_lake(db: VanillaDB, state: ProgressionState, lake_resources: set[str]) -> bool:
    """Y a-t-il un fluide extractible sans électricité (un lac) ?

    Les lacs sont extractibles via la pompe offshore (énergie void), sans
    boucle ; une ressource en PATCH exige un extracteur électrique → boucle."""
    return bool(lake_resources)


def _generator_functional(
    db: VanillaDB, state: ProgressionState, building, lake_resources: set[str]
) -> bool:
    """Un générateur est-il fonctionnel (amorçable) dans la seed courante ?

    - générateur à vapeur : s'il existe au moins un lac ;
    - burner-generator / solar-panel : toujours fonctionnel (combustible item
      garanti, ou autonome) ;
    - nuclear-reactor : jamais candidat (produces_electricity=False — il
      produit de la chaleur, pas du courant)."""
    if not _is_steam_generator(building):
        return True
    return _has_lake(db, state, lake_resources)


def _candidate_generators(rng: random.Random, db: VanillaDB, state: ProgressionState):
    """Producteurs de COURANT non débloqués, shufflés.

    Filtre sur le tag ``produces_electricity`` (par capacités, aucune liste de
    noms). Le réacteur nucléaire (chaleur seulement) en est écarté
    naturellement."""
    gens = [
        b
        for b in db.buildings.values()
        if getattr(b, "produces_electricity", False)
        and b.name not in state.unlocked_buildings
    ]
    rng.shuffle(gens)
    return gens


def _pick_functional_generator(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    lake_resources: set[str],
):
    """Teste les générateurs un par un et renvoie (generator, ok) ; ``ok`` False
    si AUCUN n'est fonctionnel (le réparateur force alors un patch). Préfère
    la turbine quand elle est amorçable."""
    gens = _candidate_generators(rng, db, state)
    # Turbine préférée (arrivée en premier) quand elle est amorçable.
    preferred = [b for b in gens if b.name == _PREFERRED_GENERATOR]
    rest = [b for b in gens if b.name != _PREFERRED_GENERATOR]
    ordered = preferred + rest
    for b in ordered:
        if _generator_functional(db, state, b, lake_resources):
            return b, True
    return None, False


def _force_repair_patch(
    rng: random.Random,
    db: VanillaDB,
    used_types: set[str],
    used_resources: set[str],
):
    """Réparation : force un patch aléatoire qui change le pool obtenable.

    Deux types débloquent de nouvelles possibilités sans boucle : un lac
    FLUIDE (extractible sans électricité → amorce une turbine) ou un item
    supplémentaire (enrichit le pool de craft). On tire une ressource d'un type
    ≠ de celui déjà tenté, sans doublon de ressource déjà posée (patch ou lac).
    Renvoie None si la carte couvre déjà tous les candidats."""
    from tool.generator.lakes import Lake, pipable_lake_resources
    from tool.generator.map_patches import Patch, item_patch_resources

    used = set(used_resources)

    # D'abord un lac fluide si ce type n'a pas déjà été tenté.
    if "lac" not in used_types:
        fluid_pool = [r for r in pipable_lake_resources(db) if r not in used]
        rng.shuffle(fluid_pool)
        for res in fluid_pool:
            used.add(res)
            return ("lac", Lake(resource=res, richness=rng.randint(100000, 600000)))

    # Sinon un item (jamais du même type qu'un lac).
    if "item" not in used_types:
        item_pool = [r for r in item_patch_resources(db) if r not in used]
        rng.shuffle(item_pool)
        for res in item_pool:
            used.add(res)
            return ("item", Patch(kind="item", resource=res,
                                  richness=rng.randint(50000, 300000),
                                  density=rng.randint(4, 24)))
    return None


def resolve_electricity(
    rng: random.Random,
    db: VanillaDB,
    starter,
    lake_resources: set[str],
    used_resources: set[str] | None = None,
) -> list:
    """Résout l'électricité : déclenchement à la demande, générateur + pylône.

    ``lake_resources`` : fluides extractibles sans électricité (lacs déjà
    tirés) ; un générateur à vapeur n'est fonctionnel que s'il en existe.
    ``used_resources`` : identités déjà posées sur la carte (patches + lacs) —
    un patch réparateur n'en re-pioche jamais une déjà présente.

    Aucun générateur fonctionnel → on force un patch (lac fluide ou item),
    puis on revérifie ; après 20 essais, erreur. Renvoie les patches/lacs
    ajoutés par la réparation (à fusionner dans la sortie seed)."""
    state = starter.state
    buildings_unlocked = state.unlocked_buildings
    repairs: list[tuple] = []

    # Un bâtiment électrique est-il déjà débloqué ?
    needs_electricity = _needs_electricity(db, buildings_unlocked)

    if needs_electricity:
        generator, ok = _pick_functional_generator(rng, db, state, lake_resources)
        used_types: set[str] = set()
        used: set[str] = set(lake_resources) | set(used_resources or ())
        attempts = 0
        while not ok:
            attempts += 1
            if attempts > MAX_REPAIR_ATTEMPTS:
                raise ValueError(
                    "[randputF] C1: électricité irréparable — aucun générateur "
                    "fonctionnel après %d essais (aucun lac fluide ni générateur "
                    "non-vapeur disponible)" % MAX_REPAIR_ATTEMPTS
                )
            repair = _force_repair_patch(rng, db, used_types, used)
            if repair is None:
                raise ValueError(
                    "[randputF] C1: aucun patch réparateur disponible "
                    "(tous les types déjà tentés)"
                )
            kind, value = repair
            used_types.add(kind)
            repairs.append(repair)
            used.add(value.resource)
            # Un lac ajouté étend les fluides extractibles sans électricité.
            if kind == "lac":
                lake_resources = lake_resources | {value.resource}
            generator, ok = _pick_functional_generator(rng, db, state, lake_resources)

        if generator:
            _unlock_generator(rng, db, state, generator, lake_resources)
        # Pylône : indispensable pour distribuer le courant aux bâtiments.
        _unlock_pole(rng, db, state)

    return repairs


def _pick_pole(rng: random.Random, db: VanillaDB, state: ProgressionState):
    """Choisit un pylône réel (poteau électrique) non débloqué.

    Exclut le beacon (distribution mais pas un pylône : il ne transporte pas
    le courant) — il faut un vrai poteau dès le bootstrap électrique."""
    poles = [
        b
        for b in db.buildings_with_tag("is_distribution")
        if b.is_power_pole and b.name not in state.unlocked_buildings
    ]
    if not poles:
        return None
    return rng.choice(poles)


def _unlock_pole(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
) -> None:
    """Débloque un pylône électrique et sa recette.

    Le pôle est craftable à la main (`handcraft=True`) : son atelier exigerait
    l'électricité qu'il est censé transporter — boucle bootstrap sinon."""
    pole = _pick_pole(rng, db, state)
    if pole is None:
        return
    from tool.generator.recipes import _unlock_building

    _unlock_building(rng, db, state, pole, "electricity", handcraft=True)


def _needs_electricity(db: VanillaDB, unlocked_buildings: set[str]) -> bool:
    """Vérifie si un bâtiment débloqué a besoin d'électricité."""
    for building_name in unlocked_buildings:
        building = db.buildings.get(building_name)
        if building and building.energy_type == "electric":
            return True
    return False


def _unlock_generator(
    rng: random.Random,
    db: VanillaDB,
    state: ProgressionState,
    generator,
    lake_resources: set[str] | None = None,
) -> None:
    """Débloque un générateur.

    La recette est forcée à la main (`handcraft=True`) : ingrédients 100%
    solides, aucun atelier — jamais d'assembling-machine-2 ni d'usine chimique
    (ils exigent l'électricité à amorcer).

    Le combustible d'un brûleur est garanti par `_ensure_burner_fuel` ; un
    générateur à vapeur n'en consomme pas. Pour un générateur à vapeur avec
    ``lake_resources`` fourni, on assigne un fluide de lac (extractible sans
    électricité) immédiatement obtainable, stocké dans
    ``state.building_fluid_assignments`` pour export dans la seed."""
    from tool.generator.recipes import _unlock_building

    _unlock_building(rng, db, state, generator, "electricity", handcraft=True)

    # La turbine/steam-engine consomme un fluide pipable — un fluide du lac est
    # extractible sans électricité (pompe offshore, void).
    if (
        lake_resources
        and getattr(generator, "fluid_inputs", 0) > 0
    ):
        # Ordre déterministe : ``lake_resources`` est un set (itération non
        # stable entre processus) et alimente un rng.choice.
        available = [f for f in sorted(lake_resources) if f not in state.building_fluid_assignments]
        if available:
            fluid = rng.choice(available)
            state.building_fluid_assignments[generator.name] = {"input": fluid}
