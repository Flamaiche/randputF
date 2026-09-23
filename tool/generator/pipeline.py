"""Pipeline de génération d'une seed randputF.

Orchestre les phases décrites dans les docs (§7 à §14) et produit le dictionnaire
seed consommé par le mod (structure documentée dans exporters/mod_seed.py).
"""

from __future__ import annotations

import copy
import logging

from tool.common.db import SLOT_ITEM, VanillaDB
from tool.generator import (
    building_fluids,
    easeup_phase,
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
    easeup_phase.set_config(cfg)

    rng = map_patches.make_rng(db.seed_value)

    # Phase 1bis : Lacs de fluide (§7.5). Flux RNG indépendant (make_rng dédié).
    # 3e type de raw : count ∈ [min, max], chaque lac un fluide du pool pipable ;
    # 0 lac = aucun lac (le mod supprime l'eau vanilla). Tirés AVANT les patchs
    # pour que ceux-ci évitent de reposer en patch un fluide déjà en lac (C6).
    lake_list = lakes.generate_lakes(lakes.make_rng(db.seed_value), db, cfg)
    log.debug("lacs tirés: %s", [la.to_seed() for la in lake_list])

    # Phase 1 : Ressources au sol. Un fluide déjà en lac n'est jamais re-tiré
    # en patch (C6).
    patches = map_patches.generate_patches(
        rng, db, cfg, lake_resources={la.resource for la in lake_list}
    )

    # Phase 2 : Chaîne initiale (starter). ``has_lakes`` : si au moins un lac
    # est tiré, le landfill est craftable dès le bootstrap (C4). ``lake_resources``
    # : fluides des lacs extraits par la pompe du starter — le kit contient une
    # pompe par fluide distinct en plus des patchs (§7/§7.5).
    initial_lake_resources = frozenset(la.resource for la in lake_list)
    starter = starter_chain.build_starter_chain(
        rng, db, patches, has_lakes=bool(lake_list),
        lake_resources=initial_lake_resources,
    )

    # Phase 3 : Électricité (déclenchement à la demande, combustible assigné).
    # ``lake_resources`` : fluides extractibles sans électricité (lacs tirés).
    # Un générateur à vapeur n'est fonctionnel que si un tel fluide existe — il
    # prend n'importe quel fluide pipable, pas spécifiquement l'eau. Si aucun
    # générateur n'est fonctionnel, la phase force un patch réparateur (lac
    # fluide ou item) et l'ajoute au pool (§10).
    lake_resources = {la.resource for la in lake_list}
    used_resources = {p.resource for p in patches} | lake_resources
    patch_items_before = {p.resource for p in patches if p.kind == SLOT_ITEM}
    repairs = electricity.resolve_electricity(
        rng, db, starter, lake_resources, used_resources
    )
    for kind, value in repairs:
        if kind == "lac":
            lake_list.append(value)
        elif kind == "item":
            patches.append(value)

    # Bootstrap inline (§10ter) : patches/lacs réparateurs ajoutés par
    # l'électricité sont obtenables sans électricité (foreuse non-élec / pompe
    # offshore) → ils rejoignent le watershed de l'oracle, actif jusqu'au gel.
    starter.state.early.add_sources(
        items={p.resource for p in patches if p.kind == SLOT_ITEM} - patch_items_before,
        fluids={la.resource for la in lake_list} - lake_resources,
    )

    # Rejoue les macro-techs du starter : les recettes créées par l'électricité
    # doivent être unlockées par une tech, jamais rester orphelines.
    starter.tech_steps = starter_chain.build_tech_steps(starter.state, db)

    # GEL DES PROMESSES + EXTINCTION DE L'ORACLE (§10ter). `starter.promises`
    # = snapshot des produits des recettes des techs gratuites au moment du gel.
    # Dès maintenant la phase récursive re-tire sans contrainte early ;
    # ``ensure_obtainable``/``make_recipe`` garantissent qu'aucun produit promis
    # n'est re-baké ensuite.
    starter.promises = {
        recipe["results"][0]["name"]
        for recipe in starter.state.recipes
        if recipe.get("results") and recipe["results"][0]["type"] == SLOT_ITEM
    }
    starter.state.early.deactivate()

    # Phase 2bis : Assignation de fluides aux bâtiments à comportement fixe
    # (§6/§10). Détecte steam-generators et transformateurs à recette fixe
    # (boiler, heat-exchanger) non encore assignés, leur attribue un fluide
    # obtainable (un lac). Le premier générateur a déjà reçu son fluide dans
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

    # Phase 1ter : Gisements posés au runtime (§6.5). Après l'électricité, la
    # liste des patchs est finale (les réparations n'ajoutent que des lacs ou des
    # patchs item) — tous reçoivent ici leur gisement autour d'un centre proche
    # du spawn.
    map_patches.assign_patch_gisements(patches, db.seed_value, cfg)

    # Phase 1ter-bis : randomisation des ressources non-finies (A1, §˙). Après
    # les gisements, les patchs sont définitifs : richesse totale et rayon sont
    # multipliés par des facteurs aléatoires dédiés (inouï ; `count` des ITEM
    # réévalué pour garder le miroir runtime, section nonfinite: de la config).
    map_patches.apply_nonfinite_randomisation(patches, db.seed_value, cfg)

    # INSTANTANÉ GELÉ du pool de début de run : après starter + électricité,
    # avant le récursif. Source exclusive des recettes relais (§9.3).
    base = copy.deepcopy(starter.state)

    # Phase 4 : Récursion pondérée
    recursive_phase.expand_recursive(rng, db, patches, starter, lake_res)

    # Phase 4ter : chaîne fusée intable (victoire possible, §14). Consomme le
    # pool profond ; passe AVANT les relais pour qu'aucun ingrédient
    # environnemental n'y entre (les recettes de fusée ne sont pas relayées).
    endgame_steps = endgame_phase.ensure_rocket_chain(rng, db, starter.state)

    # Phase 4ter-bis : garantie d'usage dure (§D2, usage_pass). Passée AVANT les
    # relais — une recette « propre » du bootstrap hébergée dans un bâtiment mort
    # masquerait le contenu sans usage (U1). Corrige par construction U1 (usage
    # non-nul) et U2 (bâtiment débloqué avant son premier usage) ; déterministe,
    # ne touche que crafted_in/category (§D2).
    from tool.generator.usage_pass import enforce_usage

    usage_report = enforce_usage(
        db,
        starter.state,
        starter,
        starter.tech_steps + recursive_phase.steps() + endgame_steps,
        cfg,
    )

    # Phase 4bis : relais des ressources non-infinies (§9.3). Les items
    # environnementaux ont servi au bootstrap ; on crée des recettes « propres »
    # pour chaque produit qui en consommait. Le pool d'ingrédients et bâtiments
    # proviennent de ``base``, jamais du pool final.
    relays = relay_phase.build_relay_recipes(rng, db, starter.state, base)

    # Phase 4ter : techs de prologue. Les recettes propres du bootstrap sont
    # consolidées en techs frontales à l'arbre (≤ 5 unlocks chacune, §13) :
    # le palier « bootstrap → sciences », façon début Factorio vanilla.
    # Chaque tech se débloque par HAND-CRAFT d'un item du bootstrap (façon
    # vanilla automation/logistics) : pas de packs en labo, la `unit` reste vide
    # et le `research_trigger` (craft-item) fait le travail (§9.3).
    # ⚠️  Déclencheurs = items des recettes des techs gratuites du starter
    # (jamais gonflées après coup) — sinon la tech prologue resterait bloquée.
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

    # Phase 4ter-bis : recettes alternatives « ease-up » pour les crafts trop
    # lourds (graphe trop profond ou boucle). Détection sur le graphe FINAL ;
    # recette alternative du pool gelé ``base`` (comme les relais §9.3) ;
    # déblocage par des techs prologue (hand-craft) insérées après le
    # bootstrap/relais. Flux RNG indépendant (make_rng) : additif pur,
    # une seed régénérée = la précédente plus les ease-up.
    #
    # Déclencheurs hand-craft : les techs ease-up réutilisent le même pool que
    # les prologue relais, mais les triggers déjà pris leur sont interdits
    # (deux techs avec le même craft-item se déclencheraient ensemble).
    easeup_rng = easeup_phase.make_rng(db.seed_value)
    used_triggers = [
        s.get("craft_trigger") for s in welcome_steps if s.get("craft_trigger")
    ]
    _eased, ease_steps = easeup_phase.build_ease_up_recipes(
        easeup_rng,
        db,
        starter.state,
        base,
        trigger_candidates
        or ([starter.first_science_pack] if starter.first_science_pack else None),
        used_triggers,
        steps_rng=easeup_rng,
    )

    # Phase 5 : Arbre technologique (macro-steps uniquement). Ordre : d'abord les
    # techs gratuites du starter (premières recettes), puis les techs de prologue
    # (recettes alternatives + premier pack science + ease-up).
    all_tech_steps = (
        starter.tech_steps + welcome_steps + ease_steps + recursive_phase.steps() + endgame_steps
    )

    # Ré-applique la garantie d'usage dure sur l'ORDRE FINAL (recettes relais et
    # ease-up créées après la passe primaire ; leurs techs prologue sont tôt alors
    # que leur bâtiment d'hébergement peut être profond). La passe est idempotente
    # et déterministe ; elle ne touche que crafted_in/category/claims d'unlock.
    enforce_usage(
        db,
        starter.state,
        starter,
        all_tech_steps,
        cfg,
    )

    technologies = tech_tree.build_linear_tech_tree(all_tech_steps, rng, db)

    # Seules les techs du starter sont gratuites (auto-complétées au runtime) ;
    # les techs de prologue suivent immédiatement (cost=[], trigger hand-craft)
    # mais restent des recherches à lancer par le joueur, pas des free_researches.
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
    seed = {
        "meta": {
            "seed": db.seed_value,
            "generator_version": "0.1.0",
            "factorio_version": "2.0",
        },
        "pools": {
            "item_resources": sorted(i.name for i in db.beltable_items()),
            "fluid_resources": sorted(f.name for f in db.pipable_fluids()),
            # Pool des armes montées (§7/§12.1) : items gun tirés pour les
            # véhicules — aucune valeur en dur dans le mod.
            "vehicle_weapons": recursive_phase.vehicle_weapons_pool(),
            # Scale de portée montée (§12.1) : portée du clone =
            # base × (1 + max(taille_véhicule − base_size, 0) × scale).
            "vehicle_range_scaling": recursive_phase.vehicle_range_scaling(),
            # Ressources brutes (§3/§13) : patches + environnement +
            # fluides d'extraction (infinis ou non) — les lacs (§7.5) y sont
            # inclus. Un science pack n'en consomme jamais.
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
        # Loot du site de crash (§7) : pool de matériaux + loi pondérée 0..3 par slot
        # (seed.wreck.counts = [c0, c1, c2, c3], somme des valeurs = 100).
        "wreck": wreck_loot.build_wreck_config(cfg, db),
        "recipes": starter.recipes + recursive_phase.recipes_to_seed(),
        "technologies": technologies,
        "progression_order": [t["id"] for t in technologies],
        "vehicle_armament": recursive_phase.vehicle_armament(),
        # Assignation de fluides aux bâtiments à comportement fixe (§6/§10) :
        # {building_name: {"input": fluid, "output"?: fluid}}. La clé fait
        # autorité : les assignations du récursif écrasent celles de
        # `building_fluids` (source unique de vérité).
        "building_fluid_assignments": {
            **building_fluid_assignments,
            **starter.state.building_fluid_assignments,
        },
    }

    # Phase 6bis : C1 — quantités de craft (post-assemblage, §IDEES C1). Passe
    # RNG dédié sur les montants (la solvabilité ne lit que la structure) ;
    # inerte si `craft_quantity.enabled` est faux.
    from tool.generator.craft_quantity import apply_craft_quantity

    apply_craft_quantity(seed, cfg)
    return seed
