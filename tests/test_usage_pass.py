"""Garantie d'usage dure (D2) : invariants U1/U2 sur seed finale.

Vérifie que `usage_pass` (passe primaire + complément post-ease/relais) tient
sur plusieurs graines, avec l'audit partagé avec `tools/audit_usage.py`
(source unique de vérité, miroir de `usage_pass._correct_u1/_correct_u2`) :

- U1 : tout bâtiment-hôte unlocké (`randputf-<b>` présent) héberge ≥ 1 recette
  du PRIMAIRE (les relais/ease masqueraient les bâtiments morts) ;
- U2 : recette R hébergée dans B ⇒ unlock(R) ≥ unlock(B), avec les exemptions
  du §7 (kit tech 0, double-free bootstrap, auto-consommation du bootstrap —
  R consommé par une recette débloquée avant B : le déblocage précoce est
  voulu, le décaler créerait une recette injouable).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from tool.generator.pipeline import generate_seed
from tools.audit_usage import audit

DB = json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text())

SEEDS = tuple(range(20))


def test_u1_batiments_hotes_non_morts() -> None:
    """U1 : aucun bâtiment unlocké sans recette primaire hébergée."""
    for seed_value in SEEDS:
        from tool.parsers.vanilla import load_db_from_dump

        db = load_db_from_dump(copy.deepcopy(DB))
        db.seed_value = seed_value
        seed = generate_seed(db, validate=False)
        res = audit(seed, db)
        assert not res["u1"], (
            f"seed {seed_value}: bâtiments morts (U1) {res['u1'][:5]}"
        )


def test_u2_ordre_tech_avant_usage() -> None:
    """U2 : aucune recette hébergée avant le déblocage de son bâtiment."""
    for seed_value in SEEDS:
        from tool.parsers.vanilla import load_db_from_dump

        db = load_db_from_dump(copy.deepcopy(DB))
        db.seed_value = seed_value
        seed = generate_seed(db, validate=False)
        res = audit(seed, db)
        assert not res["u2"], (
            f"seed {seed_value}: recettes < bâtiment (U2) {res['u2'][:5]}"
        )