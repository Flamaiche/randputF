"""Phase 1 : ressources au sol (§6).

IMPLEMENTE. Nombre de patchs tiré entre 3 et 8 ; chaque patch reçoit un type
parmi tous les items beltables ou tous les fluides pipables, sans contrainte
d'homogénéité ; richesse variable. Tirage SANS remise : chaque ressource
apparaît au plus une fois.
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
    # Gisement posé au runtime (§6.5) : le mod pose chaque bloc/puits ; la seed
    # fournit le centre, un nombre aléatoire de blocs, un rayon de dispersion
    # et une graine locale pour dériver chaque position de façon déterministe.
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
    """Tire les patchs au sol (§6). Chaque ressource de la carte (patches +
    lacs) ne doit apparaître qu'une fois (C6) : à chaque tirage on repioche si
    la ressource est déjà posée via ``used``. ``lake_resources`` : fluides déjà
    en lac, à éviter."""
    map_cfg = config.get("map", {})
    low = int(map_cfg.get("patches_min", 3))
    high = int(map_cfg.get("patches_max", 8))
    count = rng.randint(max(1, low), max(1, high))

    item_candidates = [i.name for i in _excludable_items(db)]
    fluid_candidates = [f.name for f in db.pipable_fluids()]

    # Identités de ressources déjà posées sur la carte : les lacs d'abord (C6),
    # puis chaque patch ajouté. Un même fluide n'est jamais patch ET lac.
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
        # Tirage sans remise, en sautant les identités déjà dans ``used``.
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


# ── Gisements posés au runtime (§6.5) ──
# Nombre de blocs/puits par gisement et dispersion autour du centre (item ET
# fluide).
WELLS_MIN = 3
WELLS_MAX = 8
# Rayon (tuiles) de dispersion des blocs/puits d'un gisement.
CLUSTER_MIN = 9
CLUSTER_MAX = 16
# Gisements ITEM = champ plein « comme le mapgen vanilla » (disque dense posé
# au runtime, count = nombre RÉEL de tuiles posées — l'aire du disque narquait
# la richesse par tuile : seules ~55..65 % des tuiles théoriques étaient posées,
# le champ produisait donc bien moins que ``richness``). Les puits FLUIDES, eux,
# restent éparpillés (un pumpjack se branche sur une tuile quelconque, la
# densité n'apporte rien).
ITEM_RADIUS_MIN = 9
ITEM_RADIUS_MAX = 17

# ── Forme du champ ITEM (§6.5) — miroir EXACT de ``block_positions_in_area``
# dans mod/control.lua ──
# Le champ est un disque bruité posé tuile par tuile au runtime. Cœur plein
# (« façon vanilla » : quasi toutes les tuiles internes, ~1 % de trous), anneau
# externe dilué en densité décroissante jusqu'au bord. Le bord ondule via un
# bruit (``NOISE_WOBBLE``). Chaque tuile est décidée par un HASH DÉTERMINISTE
# modulo 2^31-1 (jamais de sin : un sin de grands arguments n'est pas garanti
# bit-à-bit identique entre Python et LuaJIT, le comptage divergerait).
NOISE_WOBBLE = 0.20  # amplitude du bruit sur le bord (contours sinueux)
NOISE_CORE = 0.72    # fraction du rayon = cœur plein
NOISE_CORE_KEEP = 0.99  # proba de poser une tuile au cœur (quasi plein)
NOISE_DILUTE = 0.85  # densité maximale de l'anneau externe (bord dilué)
NOISE_M = 2147483647  # modulo (nombre premier, multiplications < 2^53 → exact)


def _tile_hash(seed: int, x: int, y: int) -> float:
    """Hash déterministe ∈ [0,1) par tuile (coordonnées RELATIVES au centre).
    Miroir exact de ``tile_hash`` dans mod/control.lua. Uniquement des
    multiplications par 48271 mod 2^31-1 (LCG de Schrage) : entiers < 2^53,
    reproductibles à l'identique en double dans LuaJIT."""
    h = (seed % NOISE_M) + 1 + (x + 31) * 48271 + (y + 31) * 33919
    h = ((h % NOISE_M) * 48271) % NOISE_M
    h = (h * 48271) % NOISE_M
    return h / NOISE_M


def item_field_tiles(radius: int, well_seed: int) -> set[tuple[int, int]]:
    """Positions RÉELLES que le champ ITEM posera au runtime (relatif au centre).

    Le mod itère le même carré ``[-margin, margin]`` et applique la même règle
    (bord : ``d <= radius + wobble`` ; densité : cœur ``NOISE_CORE`` plein,
    anneau externe dilué). ``count`` stocké dans la seed = ``len(...)`` : la
    richesse totale ``richness/count`` par tuile tombe ainsi EXACTEMENT sur le
    nombre de tuiles posées (plus d'aire théorique sur-estimée)."""
    margin = math.ceil(radius * (1 + NOISE_WOBBLE))
    seed_a = well_seed
    # Constante Φ (~1.6e9) pour décorréler le 2e champ de bruit.
    seed_b = well_seed + 1618033989
    out: set[tuple[int, int]] = set()
    for dy in range(-margin, margin + 1):
        for dx in range(-margin, margin + 1):
            d = math.sqrt(dx * dx + dy * dy)
            wobble = (_tile_hash(seed_a, dx, dy) - 0.5) * 2 * radius * NOISE_WOBBLE
            if d <= radius + wobble:
                edge = d / radius
                t = _tile_hash(seed_b, dx, dy)
                if edge <= NOISE_CORE:
                    if t < NOISE_CORE_KEEP:
                        out.add((dx, dy))
                else:
                    weak = (edge - NOISE_CORE) / (1 - NOISE_CORE)
                    if t < (1 - weak) * NOISE_DILUTE:
                        out.add((dx, dy))
    return out
# Distance (tuiles) du premier gisement au spawn, puis anneaux croissants :
# « cluster serré au spawn » (~25..193 tuiles selon le nombre de patchs),
# léger gradient d'exploration sans long voyage au départ.
FIRST_CENTER_DIST = 25
RING_STEP = 24


def assign_patch_gisements(patches: list[Patch], seed_value: int, config: dict) -> None:
    """Attribue à CHAQUE patch (item ET fluide) un gisement posé au runtime.

    Modifie ``patches`` en place, avec un flux RNG DÉDIÉ (``randputF:wells:``)
    pour ne pas perturber le tirage des autres phases (seeds stables).

    Pour chaque patch (n°0 le plus proche du spawn, puis anneaux croissants) :
      * centre déterministe à des angles éparpillés ;
      * fluide : puits éparpillés (``wells_per_patch``, défaut 3..8) ;
        item : champ plein — rayon ``item_patch_radius``, count = tuiles RÉELLES
        posées par l'algo de forme (§6.5, ``item_field_tiles``) ;
      * ``well_seed`` : graine locale reproductible indépendamment de l'ordre
        de génération des chunks.
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
        well_seed = wrng.randint(1, 2**31 - 1)
        if p.kind == "fluid":
            # Puits éparpillés : quelques entités à dispersion large (§6.5) ;
            # un pumpjack se branche sur n'importe quelle tuile du champ.
            count = wrng.randint(wells_lo, max(wells_lo, wells_hi))
            radius = wrng.randint(cl_min, cl_max)
        else:
            # Champ ITEM plein type vanilla : rayon = taille du champ (disque
            # au runtime). count = nombre RÉEL de tuiles que l'algo de forme
            # posera (§6.5) — pas l'aire théorique (qui sur-estimait ~35..45 %
            # et diluait la richesse par tuile). richesse/count tombe alors
            # exactement sur les tuiles posées, comme une vraie couche d'ore.
            radius = wrng.randint(ir_min, ir_max)
            count = len(item_field_tiles(radius, well_seed))
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
    # est une brique garantie du starter (2e recherche gratuite).
    research = {
        i.name
        for i in db.items.values()
        if i.place_result is not None
        and db.buildings.get(i.place_result) is not None
        and db.buildings[i.place_result].is_research
    }
    # Idem chaîne fusée (§14) et rocket-silo : la victoire exige leurs recettes
    # générées (unlockées par randputf-endgame-rocket) — jamais un patch.
    hero = set(ROCKET_CHAIN) | {"rocket-silo"}
    # Les science packs ne sont JAMAIS des patchs (§13) : leur économie repose
    # sur le craft (jamais extraits du sol) ; un pack posé briserait la filière
    # de coût des techs.
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


# ── Randomisation des ressources non-finies (A1) ──
# Chantier A1 : les gisements finis (patches items/fluides) gardent leur richesse
# et leur taille telles que tirées par `generate_patches`/`assign_patch_gisements`.
# Cette phase (optionnelle, `nonfinite.enabled`) applique en plus des facteurs
# multiplicatifs ALÉATOIRES par gisement sur la richesse totale et le rayon —
# sans jamais casser le miroir runtime : pour un ITEM, `count` est RÉÉVALUÉ via
# `item_field_tiles(radius, well_seed)` (le mod pose exactement ces tuiles).
# L'identité (kind + resource) reste tirée par `generate_patches` (C6).
#
# Flux RNG DÉDIÉ (`randputF:nonfinite:`) : la randomisation n'ajoute rien aux
# autres phases (une seed régénérée = la précédente + les facteurs A1).


def apply_nonfinite_randomisation(
    patches: list[Patch], seed_value: int, config: dict
) -> None:
    """Applique les facteurs A1 (richesse + rayon) aux gisements, en place.

    Inerte si la section ``nonfinite`` de la config est absente ou
    ``enabled: false``. Bornes de sécurité : richesse ≥ 1, rayon ≥ 3 ;
    ``count`` des ITEM réévalué (le mod pose ``item_field_tiles``), celui des
    fluides (puits) inchangé (déjà éparpillés).
    """
    nonfinite = config.get("nonfinite") or {}
    if not nonfinite.get("enabled", False):
        return
    from tool.prototypes.nonfinite_randomisation import NonfiniteConfig

    ncfg = NonfiniteConfig.from_config(config)
    nrng = random.Random(f"randputF:nonfinite:{seed_value}")

    for p in patches:
        rf = nrng.uniform(ncfg.richness_factor_min, ncfg.richness_factor_max)
        rrf = nrng.uniform(ncfg.radius_factor_min, ncfg.radius_factor_max)
        p.richness = max(1, int(p.richness * rf))
        p.cluster_radius = max(3, int(p.cluster_radius * rrf))
        if p.kind == "item" and p.well_seed:
            # Miroir runtime : le champ posé = item_field_tiles(radius, well_seed)
            # → count réévalué, richesse/count tombe sur les tuiles réellement posées.
            p.count = len(item_field_tiles(p.cluster_radius, p.well_seed))
        elif p.kind == "fluid":
            # Puits éparpillés : la taille du champ (center/count/well_seed) est
            # fixée par le runtime ; le facteur count module le nb de puits.
            cf = nrng.uniform(ncfg.count_factor_min, ncfg.count_factor_max)
            p.count = max(1, int(p.count * cf))
