"""Audit « rejoueur » : rejoue chaque seed comme si un joueur la jouait.

Vérifie sur les seeds 0..N que la partie est réellement terminable :
chaque tech est recherchée dès que ses coûts (packs / déclencheur prologue)
sont produisibles avec ce que le joueur PEUT avoir à ce moment — en modélisant
l'extraction (patchs par foreuse, lacs par pompe offshore), l'énergie des
ateliers (électricité / combustible / chaleur selon le bâtiment), le réseau
électrique (générateur obtenable et alimenté + pylône), le kit du spawn et les
sources environnementales. La victoire = chaîne fusée atteignable.

Une seed qui ne finit pas révèle un softlock réel à corriger en phase de
génération (jamais dans le rejoueur).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tool.__main__ import _load_config, _load_db
from tool.generator.pipeline import generate_seed
from tool.replay.player import play

DUMP = Path(__file__).resolve().parent.parent / "data" / "vanilla_dump.json"


def main() -> int:
    cfg = _load_config()
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 201
    victories = 0
    bad = []
    for seed_value in range(lo, hi):
        db = _load_db(False, DUMP)
        db.seed_value = seed_value
        cfg2 = dict(cfg)
        cfg2["seed"] = seed_value
        seed = generate_seed(db, cfg2, validate=False)
        report = play(db, seed)
        if report.victory:
            victories += 1
        else:
            bad.append((seed_value, report.researched, str(report.blocker)))
    print(
        f"seeds {lo}-{hi-1}: {victories} victoires, {len(bad)} échecs "
        f"({hi - lo - victories} parts sans fusée)"
    )
    for s in bad[:20]:
        print("  ", s)
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())