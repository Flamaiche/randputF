"""Bootstrap inline (§10ter, redesign) : invariants sur 20 graines.

Depuis le redesign « contrainte à la création », il n'y a PLUS de passe de
rattrapage : aucune recette de secours `randputf-bootsafe-*`, aucune tech
`randputf-starter-bootsafe`. À la place, chaque recette promise (produit des
techs gratuites) est créée avec des ingrédients ⊆ watershed pré-électricité et
sans atelier électrique (oracle early). Le test diagnostique chaque seed
(avec ``pytest -s``) :

- cycles de production trouvés (SCC) et leur sort (atteignable / négatif,
  INFO : NET≤0 n'est plus un gate des corrections) ;
- promesses du starter : combien sont craftables sans électricité ;
- linéarité du départ : profondeur maximale de l'arbre technologique, taille
  des techs (unlocks), multiplicité des branches.

Invariants vérifiés (en plus du solveur §15) :
- AUCUNE recette `randputf-bootsafe-*` ni tech `randputf-starter-bootsafe` ;
- TOUTE promesse du starter est atteignable sans électricité (aucun gap)."""

from __future__ import annotations

import collections
import copy
import json
import logging
from pathlib import Path

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_ITEM
from tool.generator import bootstrap_guard
from tool.generator.early_oracle import compute_early_reachable
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump
from tool.validator.solver import validate_seed

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-5s %(name)s: %(message)s",
    force=True,
)

log = logging.getLogger("test.bootstrap_guard")

DB = load_db_from_dump(json.loads((Path(__file__).parent.parent / "data/vanilla_dump.json").read_text()))

SEEDS = tuple(range(20))


def _unlocks(techs):
    by_recipe: dict[str, list[str]] = collections.defaultdict(list)
    for t in techs:
        for e in t.get("effects") or []:
            if e.get("type") == "unlock-recipe":
                by_recipe[e["recipe"]].append(t["id"])
    return by_recipe


def _made_by(recipes):
    made: dict[str, str] = {}
    for r in recipes:
        for res in r.get("results") or []:
            if res["type"] == SLOT_ITEM:
                made.setdefault(res["name"], r["name"])
    return made


def _sources(seed):
    items = set(ENVIRONMENTAL_ITEMS) & set(DB.items)
    items |= {p["resource"] for p in seed["map"]["patches"] if p.get("kind") == "item"}
    fluids = {p["resource"] for p in seed["map"]["patches"] if p.get("kind") != "item"}
    fluids |= {la["resource"] for la in seed["map"]["lakes"]}
    return items, fluids


def _tech_depth(techs):
    """Profondeur max de l'arbre tech (longueur de la plus longue chaîne
    de prérequis) puis taille max de tech (nombre d'unlocks)."""
    prereq = {t["id"]: list(t.get("prerequisites") or []) for t in techs}
    memo: dict[str, int] = {}

    def depth(tid):
        if tid in memo:
            return memo[tid]
        memo[tid] = 0
        d = 1 + max((depth(p) for p in prereq.get(tid, [])), default=0)
        memo[tid] = d
        return d

    deepest = max((depth(t["id"]) for t in techs), default=0)
    sizes = [len([e for e in t.get("effects") or [] if e.get("type") == "unlock-recipe"]) for t in techs]
    return deepest, max(sizes, default=0), sizes


def _diagnose(seed) -> dict:
    unlocked = _unlocks(seed["technologies"])
    made_by = _made_by(seed["recipes"])
    free_ids = set(seed["free_researches"])
    free_recipe_names = {
        rn
        for rn, techs in unlocked.items()
        if any(t in free_ids for t in techs)
    }
    promised = {it for it, rn in made_by.items() if rn in free_recipe_names}
    items, fluids = _sources(seed)
    early, early_fluids = compute_early_reachable(
        DB, seed["recipes"], items, fluids
    )
    cycles = bootstrap_guard.find_cycles(DB, seed["recipes"], early)
    deepest, biggest, sizes = _tech_depth(seed["technologies"])
    return {
        "free_techs": len(free_ids),
        "promised": sorted(promised),
        "early": early,
        "cycles": cycles,
        "tech_depth": deepest,
        "tech_max_size": biggest,
        "tech_mean_size": sum(sizes) / len(sizes) if sizes else 0.0,
        "solver": validate_seed(seed),
    }


def test_bootstrap_inline_20_seeds() -> None:
    """Invariants du bootstrap inline : plus de passe de rattrapage (0 recette
    `randputf-bootsafe-*`, 0 tech `randputf-starter-bootsafe`), solveur §15
    propre et TOUTE promesse du starter atteignable sans électricité."""
    for s in SEEDS:
        db = copy.deepcopy(DB)
        db.seed_value = s
        seed = generate_seed(db)
        d = _diagnose(seed)
        bootsafe = [
            r["name"] for r in seed["recipes"]
            if r["name"].startswith("randputf-bootsafe-")
        ]
        starter_bootsafe_tech = [
            t["id"] for t in seed["technologies"]
            if t["id"] == "randputf-starter-bootsafe"
        ]
        unreachable = [c["members"] for c in d["cycles"] if not c["reachable"]]
        neg = [c["members"] for c in d["cycles"] if c["net_yield"] <= 0]
        missing = [it for it in d["promised"] if it not in d["early"]]
        log.info(
            "seed=%-3d techs=%d dépt=%d mean_size=%.1f max_size=%d | "
            "promesses=%d (pré-élec=%d) | cycles=%d (inaccessibles=%d, négatifs=%d) | "
            "non_couvertes=%d bootsafe=%d solver=%d",
            s,
            len(seed["technologies"]),
            d["tech_depth"],
            d["tech_mean_size"],
            d["tech_max_size"],
            len(d["promised"]),
            len([p for p in d["promised"] if p in d["early"]]),
            len(d["cycles"]),
            len(unreachable),
            len(neg),
            len(missing),
            len(bootsafe),
            len(d["solver"]),
        )
        assert not d["solver"], f"seed {s}: solveur {d['solver'][:4]}"
        assert not bootsafe, f"seed {s}: recettes du garde supprimé {bootsafe}"
        assert not starter_bootsafe_tech, f"seed {s}: tech du garde supprimé présente"
        assert not missing, f"seed {s}: promesses non atteignables {missing}"


def test_bootstrap_promesses_atteignables_20_seeds() -> None:
    """Chaque promesse du starter est dans le watershed pré-électricité de la
    seed finale (correct-by-construction, aucun gap)."""
    for s in SEEDS:
        db = copy.deepcopy(DB)
        db.seed_value = s
        seed = generate_seed(db)
        d = _diagnose(seed)
        missing = [it for it in d["promised"] if it not in d["early"]]
        assert not missing, f"seed {s}: promesses non atteignables {missing}"