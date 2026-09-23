"""Tests de la chaîne de départ (docs/starter.md §7) : kit, extraction, transformation,
transports, et partage d'état avec les phases suivantes."""

from __future__ import annotations

import random

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_FLUID, SLOT_ITEM, VanillaDB
from tool.common.demo import build_demo_db
from tool.generator.map_patches import Patch, generate_patches, make_rng
from tool.generator.starter_chain import build_starter_chain
from tests.test_recipes import replay


def make_patches(*specs):
    return [Patch(kind, resource, 1000) for kind, resource in specs]


def test_kit_contient_arme_et_munitions():
    rng = random.Random(9)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore")))
    names = {entry["name"] for entry in chain.kit}
    assert "pistol" in names
    assert "firearm-magazine" in names


def test_chest_craftable_materiaux_finis():
    """§7 : la seed GARANTIT une recette de chest (stockage d'items), tirée
    aléatoirement, craftable avec des matériaux FINIS — aucun ingrédient
    environnemental (wood/stone/raw-fish) ni fluide (infini)."""
    rng = random.Random(9)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore")))
    chest_recipes = []
    for r in chain.recipes:
        res = (r.get("results") or [{}])[0]
        if res.get("type") != SLOT_ITEM or not res.get("name"):
            continue
        item = db.items.get(res["name"])
        if not item or not item.place_result:
            continue
        building = db.buildings.get(item.place_result)
        if building is not None and building.is_chest:
            chest_recipes.append(r)
    assert len(chest_recipes) == 1
    for ing in chest_recipes[0]["ingredients"]:
        assert ing["type"] == SLOT_ITEM
        assert not db.items.get(ing["name"], None) or not db.items[ing["name"]].is_environmental


def test_chaine_item_complete_et_valide():
    rng = random.Random(21)
    db = build_demo_db()
    patches = make_patches(
        ("item", "iron-ore"),
        ("item", "copper-ore"),
        ("fluid", "water"),
        ("fluid", "crude-oil"),
    )
    chain = build_starter_chain(rng, db, patches)
    replay(db, chain.state)

    targets = {r["results"][0]["name"] for r in chain.recipes}
    # extracteurs : un pour le sol + un pompage eau + un fluide profond
    assert any(
        "mining-drill" in t or t in ("offshore-pump", "pumpjack") for t in targets
    )
    # transformation
    assert any("furnace" in t or "assembling" in t or "boiler" in t for t in targets)
    # transports item ET fluide
    assert any("belt" in t for t in targets)
    assert any("splitter" in t for t in targets)
    assert any("underground" in t for t in targets)
    assert any("pipe" in t for t in targets)


def test_extracteur_pumpjack_pour_patch_fluide():
    """§7.5 : un PATCH fluide est une ENTITÉ resource basic-fluid posée sur la
    terre — elle n'est minée que par un pumpjack (mining-drill électrique), pas
    par une pompe offshore (réservée aux tuiles d'eau / lacs)."""
    rng = random.Random(4)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("fluid", "water")))
    extract_steps = [s for s in chain.steps if s["type"] == "extract"]
    assert extract_steps[0]["extractor"] == "pumpjack"


def test_extracteur_pompe_offshore_pour_lac():
    """§7.5 : un LAC est une TUILE fluide (copie de la tuile eau) : la pompe
    offshore (énergie void) extrait son fluide sans électricité."""
    rng = random.Random(4)
    db = build_demo_db()
    chain = build_starter_chain(
        rng, db, make_patches(("item", "iron-ore")),
        lake_resources=frozenset({"crude-oil"}),
    )
    extract_steps = [s for s in chain.steps if s["type"] == "extract"]
    lake_step = next(
        s for s in extract_steps if s["resource"]["name"] == "crude-oil"
    )
    assert lake_step["extractor"] == "offshore-pump"


def test_kit_un_seul_extracteur_par_type():
    """§7 : le kit n'apporte qu'UNE amorce par type d'extracteur — 1 pumpjack
    pour les patchs fluides (entités basic-fluid) et 1 pompe offshore pour les
    lacs (tuiles). La SUITE se craft : la recette de l'extracteur est unlockée
    par starter-extraction (tech 0), avant tout besoin. 2 patchs fluides + 2
    lacs → 1 pumpjack + 1 offshore-pump."""
    rng = random.Random(44)
    db = build_demo_db()
    patches = make_patches(("fluid", "water"), ("fluid", "lubricant"))
    chain = build_starter_chain(
        rng, db, patches, lake_resources=frozenset({"crude-oil", "steam-demo"})
    )
    pump = next(e for e in chain.kit if e["name"] == "offshore-pump")
    assert pump["count"] == 1
    pumpjack = next(e for e in chain.kit if e["name"] == "pumpjack")
    assert pumpjack["count"] == 1
    # idem sans lac : seul le pumpjack des patchs reste, toujours unique
    chain2 = build_starter_chain(rng, db, patches)
    pumpjack2 = next(e for e in chain2.kit if e["name"] == "pumpjack")
    assert pumpjack2["count"] == 1
    assert not any(e["name"] == "offshore-pump" for e in chain2.kit)


def test_recette_extracteur_debloquee_meme_si_item_en_patch():
    """§7 « la tech d'avant » : la recette de craft d'un extracteur existe dans
    le starter (tech starter-extraction) MÊME quand son item est déjà obtenu
    comme patch au sol (§6) — sinon l'extracteur-patch n'aurait aucune recette
    et ne serait craftable qu'en profondeur de seed. Cas : patch dont la
    ressource EST un extracteur (electric-mining-drill posé au sol)."""
    rng = random.Random(31)
    db = build_demo_db()
    patches = make_patches(("item", "electric-mining-drill"), ("fluid", "water"))
    chain = build_starter_chain(rng, db, patches)
    extraction = next(
        s for s in chain.tech_steps if s["id"] == "randputf-starter-extraction"
    )
    ateliers_unlocked = {
        (b.name) for b in db.buildings.values()
        if b.name in chain.state.unlocked_buildings
    }
    for step in chain.steps:
        if step["type"] != "extract":
            continue
        extractor = step["extractor"]
        item = next(
            (i for i in db.items.values() if i.place_result == extractor), None
        )
        assert item is not None
        recipe = next(
            (r for r in chain.recipes
             if r["results"] and r["results"][0]["name"] == item.name),
            None,
        )
        assert recipe is not None, (
            f"{item.name}: aucune recette starter malgré l'item en patch"
        )
        assert recipe["name"] in extraction["unlocks_recipes"], (
            f"{item.name}: la recette {recipe['name']} n'est pas unlockée par "
            "starter-extraction"
        )


def test_state_partage_avec_phases_suivantes():
    rng = random.Random(77)
    db = build_demo_db()
    patches = make_patches(("item", "stone"), ("fluid", "lubricant"))
    chain = build_starter_chain(rng, db, patches)
    assert chain.state.obtained_items >= {"stone"}
    assert chain.state.obtained_fluids >= {"lubricant"}
    assert len(chain.state.unlocked_buildings) >= 2
    assert chain.buildings == sorted(chain.state.unlocked_buildings)


def test_pool_environnemental_disponible_des_le_depart():
    """Arbres/rochers/poissons (docs/model.md §3, docs/ressources.md §6) : items obtenus dès le départ,
    avant tout patch — ils alimentent le pool d'ingrédients initial."""
    db = build_demo_db()
    chain = build_starter_chain(random.Random(1), db, make_patches(("fluid", "water")))
    assert set(chain.state.obtained_items) >= set(ENVIRONMENTAL_ITEMS)


def test_batiment_recherche_debloque():
    """§8 : le starter doit toujours garantir un bâtiment de type "recherche"
    (un lab) dès les techs gratuites."""
    db = build_demo_db()
    chain = build_starter_chain(random.Random(3), db, make_patches(("item", "iron-ore")))
    unlocked_research = {
        b.name for b in db.buildings.values()
        if b.is_research and b.name in chain.state.unlocked_buildings
    }
    assert unlocked_research


def test_recherche_obligatoire_dans_2eme_research_gratuite():
    """§8 : la recette du bâtiment de recherche tombe dans la 2e recherche
    gratuite (starter-transformation), jamais dans la tech d'extraction."""
    db = build_demo_db()
    chain = build_starter_chain(
        random.Random(5),
        db,
        make_patches(("item", "iron-ore"), ("fluid", "water")),
    )
    assert len(chain.tech_steps) >= 2
    extraction, transformation = chain.tech_steps[:2]
    assert extraction["id"] == "randputf-starter-extraction"
    assert transformation["id"] == "randputf-starter-transformation"

    research_items = {
        i.name for i in db.items.values()
        if i.place_result
        and db.buildings.get(i.place_result)
        and db.buildings[i.place_result].is_research
    }
    lab_recipes = {f"randputf-{item}" for item in research_items}
    assert not (set(extraction["unlocks_recipes"]) & lab_recipes)
    assert set(transformation["unlocks_recipes"]) & lab_recipes


def test_items_environnementaux_jamais_en_patch():
    """§6 : les ressources non automatisables (wood/stone/raw-fish) ne
    constituent jamais un patch, même sur de nombreuses générations."""
    db = build_demo_db()
    for seed in range(50):
        rng = make_rng(seed)
        patches = generate_patches(rng, db, {})
        resources = {p.resource for p in patches}
        assert not resources & set(ENVIRONMENTAL_ITEMS)


def test_patches_sans_ressource_dupliquee():
    """Chaque ressource apparait au plus une fois sur une seed (tirage sans
    remise) : deux patchs de petroleum-gas sont impossibles."""
    db = build_demo_db()
    for seed in range(50):
        rng = make_rng(seed)
        patches = generate_patches(rng, db, {})
        resources = [p.resource for p in patches]
        assert len(resources) == len(set(resources)), f"seed {seed}: {resources}"


def test_landfill_garanti_des_lacs():
    """Quand la seed tire au moins un lac (plus d'eau vanilla), le landfill
    est craftable dès le bootstrap (recette randputf-landfill + unlock par la
    tech gratuite starter-transformation), jamais laissé au hasard du balayage."""
    rng = random.Random(11)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore")), has_lakes=True)
    # landfill obtenable : sa recette randputf-landfill existe et est unlockée
    landfill_recipe = next(
        (r for r in chain.recipes
         if r["results"] and r["results"][0]["name"] == "landfill"),
        None,
    )
    assert landfill_recipe is not None
    assert landfill_recipe["name"] == "randputf-landfill"
    # unlockée par une tech gratuite du starter
    unlocked = {
        r for step in chain.tech_steps for r in step.get("unlocks_recipes", [])
    }
    assert "randputf-landfill" in unlocked


def test_pas_de_landfill_sans_lac():
    """Sans lac, on ne force PAS le landfill dans le starter (il reste au
    balayage §9.6). La seed préserve son aléa."""
    rng = random.Random(11)
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore")), has_lakes=False)
    uncovered = {
        r for step in chain.tech_steps for r in step.get("unlocks_recipes", [])
    }
    assert "randputf-landfill" not in uncovered


def test_mineur_non_electrique_amorce_au_kit_quand_extracteur_electrique():
    """D4ter : quand le starter tire electric-mining-drill pour ses patchs item,
    le kit ne pourrait rien miner avant le réseau — l'oracle early traite pourtant
    les patchs item comme obtenables pré-élec. Un mineur NON-électrique
    (burner-mining-drill) est donc AMORCÉ au kit ET refabriquable (recette dans
    une tech gratuite), façon vanilla."""
    rng = random.Random(1)  # seed 1 : item-patch extractor = electric-mining-drill
    db = build_demo_db()
    chain = build_starter_chain(rng, db, make_patches(("item", "iron-ore")))
    extractor = next(
        s["extractor"] for s in chain.steps
        if s["type"] == "extract" and s["resource"]["name"] == "iron-ore"
    )
    assert extractor == "electric-mining-drill"
    kit = {e["name"] for e in chain.kit}
    assert "burner-mining-drill" in kit
    assert any(
        r["results"] and r["results"][0]["name"] == "burner-mining-drill"
        for r in chain.recipes
    )


def test_aucune_recette_auto_hebergee():
    """D4ter : aucune recette n'est hébergée dans un bâtiment dont l'item EST
    son produit (randputf-stone-furnace dans stone-furnace) — cercle
    atelier=produit qui rend la recette inconstructible. Vérifié sur une
    poignée de seeds aux patchs item + fluide."""
    db = build_demo_db()
    for seed in range(12):
        for patch in (("item", "iron-ore"), ("fluid", "water"), ("item", "copper-ore")):
            chain = build_starter_chain(
                random.Random(seed), db, make_patches(patch)
            )
            for r in chain.recipes:
                crafted_in = r.get("crafted_in")
                if not crafted_in or not r.get("results"):
                    continue
                item = next(
                    (i for i in db.items.values() if i.place_result == crafted_in), None
                )
                assert item is None or item.name != r["results"][0]["name"], (
                    f"seed {seed}: recette {r['name']} auto-hébergée dans "
                    f"{crafted_in}"
                )
