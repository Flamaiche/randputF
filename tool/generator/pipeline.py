"""Pipeline de génération d'une seed randputF.

Orchestre les phases décrites au README §6 à §13 et produit le dictionnaire
seed consommé par le mod (structure documentée dans exporters/mod_seed.py).
"""

from __future__ import annotations

import copy
import logging

from tool.common.db import VanillaDB
from tool.generator import (
    building_fluids,
    electricity,
    endgame_phase,
    lakes,
    map_patches,
    recursive_phase,
    relay_phase,
    starter_chain,
    tech_tree,
    wreck_loot,
)
from tool.generator import recipes

log = logging.getLogger(__name__)


def generate_seed(db: VanillaDB, config: dict | None = None, *, validate: bool = True) -> dict:
    """Génère une seed complète à partir de la base vanilla."""
    cfg = config or {}

    # Distribuer la config aux modules via set_config()
    recipes.set_config(cfg)
    starter_chain.set_config(cfg)
    recursive_phase.set_config(cfg)
    relay_phase.set_config(cfg)
    tech_tree.set_config(cfg)

    rng = map_patches.make_rng(db.seed_value)

    # Phase 1bis : Lacs de fluide (§7.5). Flux RNG INDÉPENDANT (make_rng dédié)
    # pour ne pas perturber le tirage des phases suivantes. 3e type de raw,
    # même système que les patchs : `count ∈ [min, max]` (défaut 1), chaque lac
    # un fluide du pool pipable ; 0 lac tiré = aucun lac sur la carte (le mod
    # supprime aussi l'eau vanilla). Les lacs sont tirés AVANT les patchs pour
    # que ceux-ci évitent de reposer en patch un fluide déjà en lac (IDEES C6).
    lake_list = lakes.generate_lakes(lakes.make_rng(db.seed_value), db, cfg)
    log.debug("lacs tirés: %s", [la.to_seed() for la in lake_list])

    # Phase 1 : Ressources au sol. Un fluide déjà posé en lac n'est jamais
    # re-tiré en patch (une même ressource brute n'apparaît qu'une fois, C6).
    patches = map_patches.generate_patches(
        rng, db, cfg, lake_resources={la.resource for la in lake_list}
    )

    # Phase 2 : Chaîne initiale (starter). ``has_lakes`` : si la seed tire au
    # moins un lac, le landfill est rendu craftable dès le bootstrap (C4).
    starter = starter_chain.build_starter_chain(
        rng, db, patches, has_lakes=bool(lake_list)
    )

    # Phase 3 : Électricité (déclenchement à la demande, combustible assigné).
    # ``lake_resources`` : les fluides EXTRACTIBLES SANS ÉLECTRICITÉ (les lacs
    # tirés par la seed). Un générateur à vapeur (turbine/steam-engine) est
    # amorçable si et seulement si un tel fluide existe (IDEES C1) — il prend
    # n'importe QUEL fluide pipable, pas spécifiquement l'eau. Si aucun
    # générateur n'est fonctionnel, la phase FORCE un patch réparateur (lac
    # fluide ou item) et le MÈLE au pool de la seed (§10, C1).
    lake_resources = {la.resource for la in lake_list}
    used_resources = {p.resource for p in patches} | lake_resources
    repairs = electricity.resolve_electricity(
        rng, db, starter, lake_resources, used_resources
    )
    for kind, value in repairs:
        if kind == "lac":
            lake_list.append(value)
        elif kind == "item":
            patches.append(value)

    # Rejoue les macro-techs du starter : les recettes créées par l'électricité
    # (générateur, combustible) doivent être unlockées par une tech, jamais
    # rester orphelines (sinon un relais pourrait en dépendre sans pouvoir la
    # fabriquer).
    starter.tech_steps = starter_chain.build_tech_steps(starter.state, db)

    # Phase 2bis : Assignation de fluides aux bâtiments à comportement fixe
    # (§6/§10). Détecte automatiquement les steam-generators (turbine, steam-
    # engine) et les transformateurs à recette fixe (boiler, heat-exchanger) qui
    # n'ont pas encore reçu de fluide, et leur assigne un fluide obtainable
    # (un lac). La turbine du premier générateur a déjà reçu son fluide dans
    # resolve_electricity ; cette phase couvre le reste.
    lake_res = {la.resource for la in lake_list}
    building_fluid_assignments = building_fluids.assign_building_fluids(
        rng, db, starter.state, lake_res
    )
    # Fusionne avec les assignations déjà faites par resolve_electricity
    # (turbine du premier générateur).
    for bld, assignment in starter.state.building_fluid_assignments.items():
        if bld not in building_fluid_assignments:
            building_fluid_assignments[bld] = assignment

    # Phase 1ter : Gisements posés au runtime (§6.5). Après l'électricité (la
    # liste de patchs est finale : les réparations n'ajoutent que des lacs ou
    # des patchs item — ces derniers reçoivent alors leur gisement ici). TOUS
    # les patchs (items ET fluides) reçoivent leur gisement de blocs/puits posés
    # au runtime autour d'un centre proche du spawn.
    map_patches.assign_patch_gisements(patches, db.seed_value, cfg)

    # INSTANTANÉ GELÉ du pool de début de run : pris APRÈS le starter +
    # électricité, AVANT le récursif. C'est la ressource exclusive des recettes
    # relais (§9.3) : un relais ne dépend jamais d'un bâtiment ou d'un item
    # débloqué seulement en profondeur de seed.
    base = copy.deepcopy(starter.state)

    # Phase 4 : Récursion pondérée
    recursive_phase.expand_recursive(rng, db, patches, starter, lake_res)

    # Phase 4ter : chaîne fusée intable (victoire possible, §14). Consomme le
    # pool profond ; passe AVANT les relais pour qu'aucun ingrédient
    # environnemental n'y entre (les recettes de fusée ne sont pas relayées).
    endgame_steps = endgame_phase.ensure_rocket_chain(rng, db, starter.state)

    # Phase 4bis : relais des ressources non-infinies (README §9.3). Les items
    # environnementaux (bois/pierre/poisson) ont servi au bootstrap du début ;
    # on crée des recettes « propres » pour chaque produit qui en consommait.
    # Le pool d'ingrédients et les bâtiments de craft proviennent de ``base``,
    # jamais du pool final.
    relays = relay_phase.build_relay_recipes(rng, db, starter.state, base)

    # Phase 4ter : techs de prologue. Les recettes propres du bootstrap (relais)
    # sont consolidées en techs FRONTALES à l'arbre (≤ 5 unlocks chacune,
    # §13) : le palier « bootstrap → sciences », façon début Factorio vanilla.
    # Nombre de techs déduit du plafond (§13), une seule si peu de recettes.
    #
    # Chaque tech de prologue se débloque par HAND-CRAFT d'un item du bootstrap
    # (façon vanilla automation/logistics) : pas de packs à fournir en labo, la
    # `unit` reste vide et le `research_trigger` (craft-item) fait le travail
    # (§9.3). Déclencheurs = items craftables à la main (produits des recettes
    # du starter), pour que chaque prologue reçoive un
    # déclencheur DISTINCT. Le premier science pack (craftable dès le bootstrap)
    # en fait naturellement partie via les recettes du starter.
    #
    # ⚠️ IL NE FAUT PAS lire `starter.recipes` ici : c'est la MÊME liste que
    # `state.recipes`, que la phase récursive continue d'étendre — on y
    # trouverait TOUTES les recettes de la seed (nuclear-reactor, rocket-silo,
    # spidertron…), y compris des items unlockés bien plus tard que le prologue
    # (§9.3). Un tel déclencheur n'est jamais craftable le moment venu → la
    # tech prologue resterait bloquée pour toujours. On ne prend donc QUE les
    # recettes des techs gratuites du starter (jamais gonflées après coup).
    trigger_candidates: list[str] = []
    for step in starter.tech_steps:
        for recipe in step.get("unlocks_recipes", []):
            if recipe.startswith("randputf-"):
                trigger_candidates.append(recipe.removeprefix("randputf-"))
    trigger_candidates = list(dict.fromkeys(trigger_candidates))
    welcome_steps = relay_phase.consolidate_intro_steps(
        relay_phase.dispatch_relay_steps(relays, rng),
        trigger_candidates
        or ([starter.first_science_pack] if starter.first_science_pack else None),
        rng,
    )

    # Phase 5 : Arbre technologique (macro-steps uniquement)
    # Ordre demandé : d'abord les techs gratuites du starter (les premières
    # recettes, craftables avec tout le pool de début), PUIS les techs de
    # prologue (recettes alternatives + premier pack science).
    all_tech_steps = starter.tech_steps + welcome_steps + recursive_phase.steps() + endgame_steps
    technologies = tech_tree.build_linear_tech_tree(all_tech_steps, rng)

    # Seules les techs du starter sont gratuites (auto-complétées au runtime) :
    # elles débloquent les recettes du bootstrap. Les techs de prologue
    # suivent immédiatement (cost=[] = se recherchent sans packs, trigger
    # hand-craft) mais restent
    # des recherches à lancer par le joueur, PAS des free_researches.
    starter.free_researches = [s["id"] for s in starter.tech_steps]

    # Phase 6 : Validation
    if validate:
        from tool.validator.pipeline_validator import validate_pipeline

        patch_resources = {p.resource for p in patches}
        lake_resources = {la.resource for la in lake_list}
        all_recipes = starter.recipes + recursive_phase.recipes_to_seed()
        state = starter.state
        vr = validate_pipeline(
            state, technologies, db, patch_resources, lake_resources
        )
        if not vr.is_valid:
            log.warning("[randputF] validation FAILED: %s", "; ".join(vr.issues))
        else:
            log.info("[randputF] validation OK: %s", vr.stats)
        for w in vr.warnings:
            log.warning("[randputF] warning: %s", w)

    # Assemblage de la seed
    return {
        "meta": {
            "seed": db.seed_value,
            "generator_version": "0.1.0",
            "factorio_version": "2.0",
        },
        "pools": {
            "item_resources": sorted(i.name for i in db.beltable_items()),
            "fluid_resources": sorted(f.name for f in db.pipable_fluids()),
            # Pool des armes montées (§7/§12.1) : items gun tirés pour les
            # véhicules — aucune valeur en dur dans le mod. Origine : config.
            "vehicle_weapons": recursive_phase.vehicle_weapons_pool(),
            # Scale de portée montée (§12.1) : portée du clone =
            # base × (1 + max(taille_véhicule - base_size, 0) × scale).
            "vehicle_range_scaling": recursive_phase.vehicle_range_scaling(),
            # Ressources brutes (§3/§13) : patches + environnement +
            # fluides d'extraction (eau/pétrole brut/vapeur, infinis ou non) —
            # un science pack n'en consomme JAMAIS. Exposées ici pour une
            # vérification data-driven de la seed assemblée. Les LACS (§7.5)
            # sont une raw resource comme les autres : leurs fluides entrent
            # dans le pool.
            "raw_resources": sorted(
                db.raw_resources(
                    {p.resource for p in patches} | {la.resource for la in lake_list}
                )
            ),
        },
        "map": {"patches": [p.to_seed() for p in patches],
                "lakes": [la.to_seed() for la in lake_list]},
        "starter_kit": starter.kit,
        "free_researches": starter.free_researches,
        # Loot du site de crash (§7) : pool de matériaux + loi pondérée 0..3 par
        # slot (seed.wreck.counts = [c0, c1, c2, c3], somme des valeurs = 100).
        "wreck": wreck_loot.build_wreck_config(cfg, db),
        "recipes": starter.recipes + recursive_phase.recipes_to_seed(),
        "technologies": technologies,
        "progression_order": [t["id"] for t in technologies],
        "vehicle_armament": recursive_phase.vehicle_armament(),
        # Assignation de fluides aux bâtiments à comportement fixe (§6/§10) :
        # {building_name: {"input": fluid, "output"?: fluid}}. Le mod lit cette
        # section en data-stage pour assigner les filters et tooltips des fluid
        # boxes — plus aucun bâtiment n'est figé sur steam/water. La clé fait
        # autorité : les assignations du récursif (fabricateurs à recette fixe,
        # recette réelle = source de vérité) écrasent celles de `building_fluids`.
        "building_fluid_assignments": {
            **building_fluid_assignments,
            **starter.state.building_fluid_assignments,
        },
    }
