"""Phase 1 : ressources au sol (README §6).

IMPLEMENTE. Nombre de patchs tire entre 3 et 8 ; chaque patch recoit un type
parmi tous les items beltables ou tous les fluides pipables, sans contrainte
d'homogeneite ; richesse variable. Tirage SANS remise : chaque ressource
apparait au plus une fois (deux patchs de petroleum-gas sur la meme seed :
impossible).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from tool.common.db import ROCKET_CHAIN, VanillaDB


@dataclass
class Patch:
    kind: str
    resource: str
    richness: int
    # Gisement posé au runtime (§6.5) : valable pour TOUS les patchs (item et
    # fluide). Le mod pose au runtime chaque bloc/puits (entité-resource,
    # minable ou pompeable) ; la seed fournit le centre du gisement, un nombre
    # aléatoire de blocs, un rayon de dispersion et une graine locale pour
    # dériver chaque position de façon déterministe.
    center: tuple[int, int] | None = None
    count: int = 0
    well_seed: int = 0
    cluster_radius: int = 10

    def to_seed(self) -> dict:
        seed = {
            "kind": self.kind,
            "resource": self.resource,
            "richness": self.richness,
        }
        if self.center is not None:
            seed["center"] = {"x": self.center[0], "y": self.center[1]}
            seed["count"] = self.count
            seed["well_seed"] = self.well_seed
            seed["cluster_radius"] = self.cluster_radius
        return seed


def make_rng(seed_value: int) -> random.Random:
    return random.Random(f"randputF:{seed_value}")


def generate_patches(
    rng: random.Random,
    db: VanillaDB,
    config: dict,
    *,
    lake_resources: set[str] | None = None,
) -> list[Patch]:
    """Tire les patchs au sol (§6).

    Chaque ressource de la carte (patches item + patches fluides + lacs) ne doit
    apparaître qu'UNE fois (IDEES C6) : à chaque item/fluide pioché, on vérifie
    s'il n'est pas déjà posé (patch tiré ou lac) et on repioche sinon
    (`used`). ``lake_resources`` : les fluides déjà posés en LAC, à éviter.
    """
    map_cfg = config.get("map", {})
    low = int(map_cfg.get("patches_min", 3))
    high = int(map_cfg.get("patches_max", 8))
    count = rng.randint(max(1, low), max(1, high))

    item_candidates = [i.name for i in _excludable_items(db)]
    fluid_candidates = [f.name for f in db.pipable_fluids()]

    # Identités de ressources déjà posées sur la carte : les lacs d'abord (C6),
    # puis chaque patch ajouté ci-dessous. Un même fluide n'est donc jamais à la
    # fois patch et lac, ni deux fois en patch.
    used: set[str] = set(lake_resources or ())

    def available(pool: list[str]) -> list[str]:
        return [r for r in pool if r not in used]

    available_items = len(available(item_candidates))
    available_fluids = len(available(fluid_candidates))
    if available_items == 0 and available_fluids == 0:
        return []

    if available(item_candidates) and available(fluid_candidates):
        type_roll = rng.random()
        if type_roll < 0.15:
            use_items, use_fluids = True, False
        elif type_roll < 0.30:
            use_items, use_fluids = False, True
        else:
            use_items, use_fluids = True, True
    elif available(item_candidates):
        use_items, use_fluids = True, False
    else:
        use_items, use_fluids = False, True

    if use_items and use_fluids:
        min_items = max(1, count // 2)
        min_fluids = max(1, count - min_items)
        n_items = rng.randint(min_items, max(min_items, count - 1))
        n_fluids = count - n_items
        n_items = min(n_items, available_items)
        n_fluids = min(n_fluids, available_fluids)
    elif use_items:
        n_items = min(count, available_items)
        n_fluids = 0
    else:
        n_items = 0
        n_fluids = min(count, available_fluids)

    item_rich = tuple(int(x) for x in map_cfg.get("richness_item", [50000, 300000]))
    fluid_rich = tuple(int(x) for x in map_cfg.get("richness_fluid", [100000, 600000]))

    patches: list[Patch] = []

    def _draw(pool: list[str], n: int, kind: str, richness: tuple) -> None:
        # Tirage sans remise + vérifie qu'une ressource déjà posée est évitée
        # (on repioche en sautant les identités déjà dans ``used``).
        rng.shuffle(pool)
        for resource in pool:
            if n <= 0:
                break
            if resource in used:
                continue
            used.add(resource)
            ri = rng.randint(richness[0], richness[1])
            patches.append(Patch(kind, resource, ri))
            n -= 1

    _draw(item_candidates, n_items, "item", item_rich)
    _draw(fluid_candidates, n_fluids, "fluid", fluid_rich)

    rng.shuffle(patches)
    return patches


# ── Gisements posés au runtime (§6.5) ───────────────────────────────────────
# DEFAULTS santé : nombre de blocs/puits par gisement et dispersion autour du
# centre. Valable pour les patchs ITEM ET FLUIDE : chaque ressource posée au sol
# devient un gisement de plusieurs entités-resource (blocs pour un item, puits
# pour un fluide) placées au runtime par le mod, dispersées autour d'un centre.
WELLS_MIN = 3
WELLS_MAX = 8
# Rayon (tuiles) dans lequel les blocs/puits d'un gisement sont dispersés.
CLUSTER_MIN = 9
CLUSTER_MAX = 16
# Gisements ITEM = champ plein « comme le mapgen vanilla » : un disque bruité
# dense, calqué sur les vraies veines d'ore de Factorio (fer/cuivre/charbon).
# Le runtime pose TOUTES les tuiles du disque (rayon ci-dessous ≈ champ de
# taille classique), et ``count`` (= aire du disque) sert au runtime à répartir
# la richesse TOTALE du champ par tuile. Les puits FLUIDES, eux, restent
# éparpillés : un pumpjack se branche sur une tuile quelconque, la densité n'y
# apporte rien.
ITEM_RADIUS_MIN = 9
ITEM_RADIUS_MAX = 17
# Distance (tuiles) du premier gisement au spawn ; chaque gisement suivant est
# posé un peu plus loin. Choisi pour un « cluster serré au spawn » : les 3..8
# gisements (items + fluides) restent dans un rayon accessible à pied très tôt
# (~25 à ~193 tuiles pour le cas extrême de 8 patchs ; ~25..145 pour les 3..6
# usuels) — léger gradient d'exploration sans jamais exiger un long voyage au
# départ. Le PREMIER patch (tiré, quel qu'il soit : item ou fluide) est donc
# toujours dans le périmètre immédiat.
FIRST_CENTER_DIST = 25
RING_STEP = 24


def assign_patch_gisements(patches: list[Patch], seed_value: int, config: dict) -> None:
    """Attribue à CHAQUE patch (item ET fluide) un gisement posé au runtime.

    Modifie ``patches`` en place. Utilise un flux RNG DÉDIÉ
    (``randputF:wells:...``) pour ne pas perturber le tirage des autres phases
    (starter, récursif, ...) : tous les seeds existants restent stables, seuls
    les champs ``center/count/well_seed/cluster_radius`` s'ajoutent.

    Pour chaque patch, dans l'ordre de la liste (le patch n°0 est donc le plus
    proche du spawn, puis anneaux croissants) :
      * centre déterministe à des angles éparpillés (pas alignés) ;
      * fluide : nombre aléatoire de puits éparpillés (config
        ``wells_per_patch``, défaut 3..8) ; item : champ plein — rayon
        aléatoire (config ``item_patch_radius``), count = aire du disque ;
      * ``well_seed`` : graine locale pour dériver les positions au runtime de
        façon reproductible, indépendamment de l'ordre de génération des chunks
        (1 PRNG par bloc = seed + index).
    """
    if not patches:
        return

    map_cfg = config.get("map", {})
    wells_lo, wells_hi = map_cfg.get("wells_per_patch", [WELLS_MIN, WELLS_MAX])
    wells_lo, wells_hi = int(wells_lo), int(wells_hi)
    cl_min = int(CLUSTER_MIN)
    cl_max = int(CLUSTER_MAX)
    ir_min, ir_max = map_cfg.get("item_patch_radius", [ITEM_RADIUS_MIN, ITEM_RADIUS_MAX])
    ir_min, ir_max = int(ir_min), int(ir_max)

    wrng = random.Random(f"randputF:wells:{seed_value}")
    for k, p in enumerate(patches):
        if p.kind == "fluid":
            # Puits éparpillés : quelques entités à dispersion large (§6.5), un
            # pumpjack se branche sur n'importe quelle tuile du champ.
            count = wrng.randint(wells_lo, max(wells_lo, wells_hi))
            radius = wrng.randint(cl_min, cl_max)
        else:
            # Champ ITEM plein type vanilla : rayon = taille du champ (disque
            # plein au runtime), count = aire du disque. La richesse TOTALE du
            # champ (richness_item) est répartie par tuile (richness/count) au
            # runtime, comme une vraie couche d'ore.
            radius = wrng.randint(ir_min, ir_max)
            count = math.ceil(math.pi * radius * radius)
        well_seed = wrng.randint(1, 2**31 - 1)
        # Centre : anneau croissant + angle éparpillé (déterministe).
        dist = FIRST_CENTER_DIST + k * RING_STEP
        angle = wrng.random() * 2 * math.pi
        cx = round(dist * math.cos(angle))
        cy = round(dist * math.sin(angle))
        p.center = (cx, cy)
        p.count = count
        p.well_seed = well_seed
        p.cluster_radius = radius


def _excludable_items(db: VanillaDB):
    excluded_types = {"combat"}
    # Les bâtiments de recherche (§8) ne sont jamais des patchs : leur recette
    # est une brique garantie du starter (2e recherche gratuite). Si un lab
    # tombait en ressource minière, il n'existerait pas de recette à débloquer.
    research = {
        i.name
        for i in db.items.values()
        if i.place_result is not None
        and db.buildings.get(i.place_result) is not None
        and db.buildings[i.place_result].is_research
    }
    # Idem pour la chaîne fusée (§14) et le rocket-silo lui-même : la victoire
    # exige leurs recettes générées (unlockées par randputf-endgame-rocket).
    # Jamais un patch, sinon la phase endgame n'aurait aucune recette à créer.
    hero = set(ROCKET_CHAIN) | {"rocket-silo"}
    # Les science packs ne sont JAMAIS des patchs (§13) : leur économie repose
    # sur le craft (chaque pack se fabrique, jamais extrait du sol). Posé au
    # sol, un pack briserait la filière de coût des techs (le premier pack,
    # seedé par le starter, n'aurait pas de recette et l'amorçage des coûts
    # échouerait).
    return [
        i for i in db.beltable_items()
        if i.subgroup not in excluded_types
        and not i.is_gun
        and not i.is_science_pack
        and not i.is_environmental
        and i.name not in research
        and i.name not in hero
        and not i.is_virtual_item
    ]


def item_patch_resources(db: VanillaDB) -> list[str]:
    """Pool des ressources ITEM pouvant être posées en patch (réparation C1)."""
    return [i.name for i in _excludable_items(db)]
