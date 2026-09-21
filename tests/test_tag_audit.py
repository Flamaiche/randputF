"""Tests de l'audit des tags (programme de vérification) : sur la
base vanilla réelle, aucun bâtiment (tags §1-8) ni item (tags §9) ne viole les
invariants d'orthogonalité/cohérence, et aucune recette cachée n'est orpheline.
"""

from __future__ import annotations

import json
from pathlib import Path

from tool.audit.tags import audit_building_tags, audit_item_tags, summarize_tags
from tool.common.demo import build_demo_db
from tool.common.db import has_hidden_recipe, is_fixed_crafter
from tool.parsers.vanilla import load_db_from_dump

DUMP_PATH = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"

DUMP = json.loads(DUMP_PATH.read_text(encoding="utf-8"))


def test_audit_vanilla_aucune_violation():
    db = load_db_from_dump(DUMP)
    report = audit_building_tags(db)
    item_report = audit_item_tags(db)
    assert report.ok, report.violations
    assert not item_report.item_violations, item_report.item_violations
    assert report.buildings_checked > 0
    assert item_report.items_checked > 0


def test_audit_toute_recette_cachee_routée():
    db = load_db_from_dump(DUMP)
    for name, b in db.buildings.items():
        if has_hidden_recipe(b):
            assert is_fixed_crafter(b), f"{name} : recette cachée non routée"
    hidden = [n for n, b in db.buildings.items() if has_hidden_recipe(b)]
    # En vanilla : boiler, heat-exchanger et reacteur (item → item).
    assert {"boiler", "heat-exchanger", "nuclear-reactor"} <= set(hidden)


def test_audit_items_environnementaux_non_fabriques():
    """Verification d'implementation §9 : un item environnemental (récolté à la
    main) ne doit être produit par AUCUNE recette vanilla (sinon cycle)."""
    db = load_db_from_dump(DUMP)
    produced = set()
    for r in db.recipes.values():
        for ptype, pname, _amount in r.products:
            if ptype == "item":
                produced.add(pname)
    for name, i in db.items.items():
        if i.is_environmental:
            assert name not in produced, f"{name} : environnemental mais crafté"
    assert any(i.is_environmental for i in db.items.values())


def test_audit_item_virtual_rail_pas_virtuel():
    """Le rail vanilla est type 'rail-planner' mais POSE du rail (place_result) :
    il ne doit PAS être tagué virtuel (il se fabrique)."""
    db = load_db_from_dump(DUMP)
    assert "rail" in db.items
    assert not db.items["rail"].is_virtual_item
    virtual = [n for n, i in db.items.items() if i.is_virtual_item]
    assert "blueprint" in virtual or "blueprint-book" in virtual


def test_audit_demo_aucune_violation():
    db = build_demo_db()
    report = audit_building_tags(db)
    item_report = audit_item_tags(db)
    assert report.ok, report.violations
    assert not item_report.item_violations, item_report.item_violations


def test_summarize_inclut_items():
    db = build_demo_db()
    report = audit_building_tags(db)
    item_report = audit_item_tags(db)
    report.item_violations = item_report.item_violations
    report.item_tag_counts = item_report.item_tag_counts
    report.uncraftable_violations = item_report.uncraftable_violations
    report.items_checked = item_report.items_checked
    out = summarize_tags(db, report)
    assert "Items audités" in out
    assert "is_environmental" in out