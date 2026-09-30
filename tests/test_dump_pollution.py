"""Régression dumps pollués (exporter + mod principal actifs ensemble).

Trois canaux de pollution, trois protections :
1. clés AJOUTÉES (recettes/items `randputf-*`, préfixe empilé) → filtrées par
   ``load_db_from_dump`` : clean et pollué donnent la même DB et la même seed ;
2. valeurs MUTÉES en place (fuel_value 0 → 200 000, filtres, fuel_categories)
   → indétectables par le filtre de noms, "ressemblent" à du contenu légitime :
   l'exporter refuse un export pollué (garde-fou runtime) ET le tool rejette un
   dump déjà muté via un invariant vanilla 2.0 ;
3. un dump qui cumule les deux canaux reste rejeté (le canal mutation à lui
   seul suffit).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump

DUMP_PATH = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"
CLEAN = json.loads(DUMP_PATH.read_text(encoding="utf-8"))

POLLUTED_SECTIONS = ("items", "fluids", "entities", "recipes")


def _pollute(dump: dict) -> dict:
    """Re-préfixe le contenu comme le ferait un mod actif pendant l'export :
    chaque clé est réinsérée sous ``randputf-<name>`` (une couche), plus
    quelques clés à double préfixe (deux couches successives)."""
    polluted = copy.deepcopy(dump)
    for section in POLLUTED_SECTIONS:
        entries = polluted.get(section)
        if not isinstance(entries, dict):
            continue
        layers = {}
        for name, entry in entries.items():
            layers[f"randputf-{name}"] = entry
        for name in list(layers)[:5]:
            layers[f"randputf-{name}"] = layers[name]
        entries.update(layers)
    return polluted


def test_dump_pollue_et_clean_donnent_la_meme_db():
    clean_db = load_db_from_dump(CLEAN)
    polluted_db = load_db_from_dump(_pollute(CLEAN))

    assert polluted_db.recipes == clean_db.recipes
    assert polluted_db.items == clean_db.items
    assert polluted_db.fluids == clean_db.fluids
    assert polluted_db.buildings == clean_db.buildings
    assert polluted_db.excluded_items == clean_db.excluded_items
    assert polluted_db.excluded_fluids == clean_db.excluded_fluids


@pytest.mark.parametrize("seed_value", [5, 77])
def test_dump_pollue_et_clean_donnent_la_meme_seed(seed_value):
    clean_db = load_db_from_dump(CLEAN)
    clean_db.seed_value = seed_value
    polluted_db = load_db_from_dump(_pollute(CLEAN))
    polluted_db.seed_value = seed_value

    assert generate_seed(polluted_db) == generate_seed(clean_db)


@pytest.mark.parametrize("fluid,fuel_value", [("crude-oil", 200000), ("steam", 200000)])
def test_dump_mute_en_place_rejete(fluid, fuel_value):
    """Canal mutation : même clé, valeur changée — le filtre de noms ne peut pas
    le voir, l'invariant vanilla 2.0 (fluide non-carburant) doit le rejeter."""
    mutated = copy.deepcopy(CLEAN)
    mutated["fluids"][fluid]["fuel_value"] = fuel_value
    with pytest.raises(ValueError, match="Dump pollue"):
        load_db_from_dump(mutated)


def test_dump_avec_les_deux_canaux_rejete():
    """Clés ajoutées ``randputf-*`` ET mutation : la mutation seule suffit à
    rejeter — pas de fausse garantie par le filtre de noms."""
    mutated = _pollute(CLEAN)
    mutated["fluids"]["light-oil"]["fuel_value"] = 200000
    with pytest.raises(ValueError, match="Dump pollue"):
        load_db_from_dump(mutated)


def test_mutation_entities_seule_acceptee_frontiere_documentee():
    """Canal entities seul (fuel_categories += "nuclear", filtres boiler) : PAS
    d'invariant dédié — décision assumée. La passe carburant mute toujours des
    fluides (co-occurrence), donc un dump réellement pollué est attrapé par
    l'invariant fluides ; cet entonnoir documente la frontière pour qu'elle ne
    soit pas un oubli, et la vérité reste le refus de l'exporter."""
    mutated = copy.deepcopy(CLEAN)
    entity = mutated["entities"]["burner-inserter"]
    entity.setdefault("energy_source", {})["fuel_categories"] = ["chemical", "nuclear"]
    boiler = mutated["entities"]["boiler"]
    for box in boiler.get("fluidbox_info", {}).get("detail", {}).values():
        if box.get("filter") == "water":
            box["filter"] = "sulfuric-acid"

    db = load_db_from_dump(mutated)
    assert db is not None