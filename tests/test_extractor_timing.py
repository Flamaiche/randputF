"""C3 — déblocage « juste-au-besoin » des extracteurs.

Vérifie sur plusieurs graines (avec l'audit partagé avec `tools/audit_usage.py`
et le mapping `seed["extractor_timing"]`, source de vérité posée par la passe
pipeline `extractor_timing.apply_extractor_timing`) que :

- EXT1/2/3 : le claim d'un extracteur n'est jamais avant son atelier (craftable
  dès le claim), jamais après max(premier-usage, atelier), et jamais-utilisé
  n'est jamais dans une tech gratuite ;
- E3 : les extracteurs au starter (bucket ``starter``) sont des techs gratuites ;
- E4 : les extracteurs jamais utilisés (bucket ``random``) sont payants.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from tool.generator.pipeline import generate_seed
from tools.audit_usage import audit

DB = json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text())

SEEDS = tuple(range(20))


def _free_claim(seed: dict) -> set[str]:
    """Recettes réclamées par les techs gratuites du starter."""
    free_ids = set(seed["free_researches"])
    free: set[str] = set()
    for tech in seed["technologies"]:
        if tech["id"] not in free_ids:
            continue
        for effect in tech.get("effects", []):
            if effect.get("type") == "unlock-recipe":
                free.add(effect["recipe"])
    return free


def test_c3_extracteurs_respectent_invariants() -> None:
    """EXT1/2/3 : aucun extracteur hors de son fenêtre
    [atelier, max(premier-usage, atelier)] ; jamais-utilisé hors tech gratuite."""
    for seed_value in SEEDS:
        from tool.parsers.vanilla import load_db_from_dump

        db = load_db_from_dump(copy.deepcopy(DB))
        db.seed_value = seed_value
        seed = generate_seed(db, validate=False)
        res = audit(seed, db)
        assert not res["extractors"], (
            f"seed {seed_value}: extracteurs hors invariant {res['extractors'][:5]}"
        )


def test_c3_extracteur_au_starter_tech_gratuite() -> None:
    """E3 : tout extracteur du bucket ``starter`` est réclamé par une tech
    gratuite (il sert dès le spawn)."""
    for seed_value in SEEDS:
        from tool.parsers.vanilla import load_db_from_dump

        db = load_db_from_dump(copy.deepcopy(DB))
        db.seed_value = seed_value
        seed = generate_seed(db, validate=False)
        free = _free_claim(seed)
        report = seed.get("extractor_timing") or {}
        for recipe in report.get("starter", []):
            assert recipe in free, (
                f"seed {seed_value}: extracteur au starter {recipe} hors techs gratuites"
            )


def test_c3_extracteur_sans_usage_est_payant() -> None:
    """E4 : un extracteur jamais utilisé (bucket ``random``) n'est pas dans une
    tech gratuite — il suit le balayage du contenu."""
    for seed_value in SEEDS:
        from tool.parsers.vanilla import load_db_from_dump

        db = load_db_from_dump(copy.deepcopy(DB))
        db.seed_value = seed_value
        seed = generate_seed(db, validate=False)
        free = _free_claim(seed)
        report = seed.get("extractor_timing") or {}
        for recipe in report.get("random", []):
            assert recipe not in free, (
                f"seed {seed_value}: extracteur jamais utilisé {recipe} gratuit"
            )