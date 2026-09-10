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
- Amorçage sans boucle : un générateur à vapeur (fluid_inputs > 0) demande
  un FLUIDE en entrée — n'importe quel fluide pipable, pas spécifiquement
  l'eau. Mais cet amorçage n'est possible que via un fluide EXTRACTIBLE SANS
  ÉLECTRICITÉ, c'est-à-dire un LAC (pompe offshore, énergie void) : une
  ressource « oil » posée en PATCH exige un pumpjack électrique (boucle
  fuel→électricité→fuel). La turbine est donc amorçable si et seulement si
  la seed tire au moins UN LAC fluide.
- Exclusions : le réacteur nucléaire (combustible à la chaîne profonde jamais
  garantie) est écarté du tirage initial.

Résolution robuste (§IDEES C1) : on ne décide PAS a priori quel générateur
« doit » marcher. On shuffle la liste des générateurs et on teste un par un
jusqu'à en trouver un FONCTIONNEL. Si AUCUN n'est fonctionnel, on force un
patch (item OU lac fluide, ressource ≠ du type précédent) pour changer le
pool obtenable, puis on re-shuffle et on revérifie. Après 20 essais sans
résultat, on lève une erreur explicite — jamais une seed silencieusement
cassée.
"""

from __future__ import annotations

import random

from tool.common.db import VanillaDB
from tool.generator.recipes import ProgressionState

# Générateur préféré pour amorcer le réseau : la turbine (§10). Avec les
# « lacs » extractibles sans électricité, sa chaîne (un fluide en entrée) est
# amorçable au bootstrap. On l'utilise quand elle est disponible, sinon on
# tire parmi les autres.
_PREFERRED_GENERATOR = "steam-turbine"

# Borne du cycle de réparation (IDEES C1) : au-delà on lève une erreur.
MAX_REPAIR_ATTEMPTS = 20


def _is_steam_generator(building) -> bool:
    """Un générateur à vapeur prend un FLUIDE en entrée (fluid_inputs > 0) :
    steam-engine / steam-turbine. Son amorçage dépend d'un fluide extractible
    sans électricité (un lac)."""
    return getattr(building, "fluid_inputs", 0) > 0


def _has_lake(db: VanillaDB, state: ProgressionState, lake_resources: set[str]) -> bool:
    """Y a-t-il un fluide extractible SANS électricité (un lac) ?

    Les lacs (resources déjà tirées) sont les seuls fluides amorçables :
    extractibles via la pompe offshore (énergie void), sans boucle. Une
    ressource posée en PATCH (oil, gaz...) exige un extracteur électrique →
    boucle (§10)."""
    return bool(lake_resources)


def _generator_functional(
    db: VanillaDB, state: ProgressionState, building, lake_resources: set[str]
) -> bool:
    """Un générateur est-il FONCTIONNEL (amorçable) dans la seed courante ?

    - générateur à vapeur (fluid_inputs > 0) : fonctionnel s'il existe au
      moins un LAC (fluide extractible sans électricité) ;
    - burner-generator / solar-panel : toujours fonctionnel (combustible item
      garanti par `_ensure_burner_fuel`, ou autonome) ;
    - nuclear-reactor : jamais candidat (produces_electricity=False —
      produit de la chaleur, pas du courant)."""
    if not _is_steam_generator(building):
        return True
    return _has_lake(db, state, lake_resources)


def _candidate_generators(rng: random.Random, db: VanillaDB, state: ProgressionState):
    """Liste (shufflée) des producteurs de COURANT non débloqués.

    Filtre sur le TAG ``produces_electricity`` (PAR CAPACITÉS, aucune liste de
    noms) : steam-engine, turbine, burner-generator, solar-panel. Le réacteur
    nucléaire (produces_heat seulement, pas de courant) en est donc écarté
    naturellement — il ne démarre jamais le réseau."""
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
    """Teste les générateurs un par un (dans la liste shufflée) et renvoie le
    premier FUNCTIONNEL. Préfère la turbine quand elle est disponible ET
    amorçable. Renvoie (generator, ok): ``ok`` False si AUCUN générateur n'est
    fonctionnel (le réparateur doit alors forcer un patch)."""
    gens = _candidate_generators(rng, db, state)
    # La turbine est préférée quand elle est amorçable (elle arrive en premier).
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
    """Réparation C1 : force un patch aléatoire qui change le pool obtenable.

    En pratique deux types de patch débloquent de nouvelles possibilités sans
    introduire de boucle :
    - un lac FLUIDE (fluide extractible sans électricité) → peut amorcer une
      turbine ;
    - un item supplémentaire → enrichit le pool de craft.

    On tire une ressource aléatoire d'un type ≠ de celui déjà essayé
    précédemment (item ↔ lac fluide), sans doublon (une ressource déjà posée
    sur la carte — patch ou lac — est évitée, IDEES C6), pour maximiser la
    chance de rendre au moins un générateur fonctionnel. Renvoie None si la
    carte est déjà couverte de tous les candidats."""
    from tool.generator.lakes import Lake, pipable_lake_resources
    from tool.generator.map_patches import Patch, item_patch_resources

    used = set(used_resources)

    # Essaye d'abord un lac fluide si ce type n'a pas déjà été tenté.
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

    ``lake_resources`` : les fluides EXTRACTIBLES SANS ÉLECTRICITÉ (les lacs
    déjà tirés par la seed). Un générateur à vapeur n'est fonctionnel que s'il
    y a au moins un tel fluide (IDEES C1).

    ``used_resources`` : les identités déjà posées sur la carte (patches +
    lacs) ; un patch réparateur n'en re-pioche jamais un déjà présent (IDEES C6).

    Si AUCUN générateur n'est fonctionnel, on force un patch (lac fluide ou
    item) pour réparer, puis on re-shuffle et on revérifie ; après 20 essais
    on lève une erreur. Renvoie la liste des patches/lacs ajoutés par la
    réparation (à fusionner dans la sortie seed)."""
    state = starter.state
    buildings_unlocked = state.unlocked_buildings
    repairs: list[tuple] = []

    # Vérifier si un bâtiment électrique est déjà débloqué
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
        # Débloquer un pylône (poteau électrique) : la distribution du courant
        # entre le générateur et les bâtiments est indispensable. Sans lui,
        # l'électricité produite ne transporte rien de jouable.
        _unlock_pole(rng, db, state)

    return repairs


def _pick_pole(rng: random.Random, db: VanillaDB, state: ProgressionState):
    """Choisit un pylône réel (poteau électrique) non débloqué.

    Exclut le beacon (bâtiment de distribution mais pas un pylône : il ne
    transporte pas le courant) — le joueur doit avoir un VRAI poteau dès le
    bootstrap électrique (§10)."""
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
    """Débloque un pylône électrique (distribution) et sa recette.

    Sans poteau, l'électricité issue du générateur ne peut pas être
    transportée jusqu'aux bâtiments qui en ont besoin (§10). Le pôle est
    CRAFTABLE À LA MAIN comme le générateur (`handcraft=True`) : son atelier
    exigerait l'électricité que le pôle est censé transporter — boucle
    bootstrap sinon."""
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

    La recette du générateur est **forcée à la main** (`handcraft=True`,
    §10) : ingrédients 100% solides, aucun atelier. En particulier jamais
    d'assembling-machine-2 ni d'usine chimique — ils exigent l'électricité
    que ce générateur est censé amorcer (antiboocle).

    Le combustible d'un éventuel générateur burner (burner-generator) est
    garanti par `_unlock_building`/`_ensure_burner_fuel` (§10) : un générateur
    qui en a besoin en reçoit un, un générateur à vapeur (steam-engine,
    turbine) n'en consomme pas et n'en reçoit donc pas.

    Si le générateur est un générateur à vapeur (fluid_inputs > 0) et que
    ``lake_resources`` est fourni, on lui assigne immédiatement un fluide
    obtainable (un lac) — c'est le fluide qu'il consomme pour produire de
    l'énergie. Le fluide est stocké dans ``state.building_fluid_assignments``
    pour export dans la seed (§6/§10)."""
    from tool.generator.recipes import _unlock_building

    _unlock_building(rng, db, state, generator, "electricity", handcraft=True)

    # Assigner un fluide du lac au générateur à vapeur (§10). La turbine /
    # steam-engine consomme un fluide pipable (pas forcément "steam") — un
    # fluide du lac est extractible sans électricité (pompe offshore, void).
    if (
        lake_resources
        and getattr(generator, "fluid_inputs", 0) > 0
    ):
        # Ordre déterministe : ``lake_resources`` est un set (itération non
        # stable entre processus / PYTHONHASHSEED) et alimente un rng.choice.
        available = [f for f in sorted(lake_resources) if f not in state.building_fluid_assignments]
        if available:
            fluid = rng.choice(available)
            state.building_fluid_assignments[generator.name] = {"input": fluid}
