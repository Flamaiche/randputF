"""Déterminisme de la seed ENTRE PROCESSUS (§16/§6.5).

Les sets Python (itération ordonnée par hash des chaînes) varient entre
processus (PYTHONHASHSEED). Toute itération de set alimentant un `rng` rend
deux générations de la MÊME graine différentes. Ici on génère la même seed en
sous-processus sous deux PYTHONHASHSEED différents et on compare le résultat
byte à byte.

Régression : l'assignation des fluides des générateurs à vapeur itérait
`lake_resources` (set) avant un `rng.choice` (electricity.py, building_fluids.py)
→ seed 1337 rendait `input: heavy-oil` ou `water` selon le processus.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _generate(seed: int, hash_seed: str, out: Path) -> Path:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    subprocess.run(
        [sys.executable, "-m", "tool", "generate", "--seed", str(seed), "--out", str(out)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        timeout=120,
    )
    return out / "randputF_0.1.0" / "seed" / "seed.json"


def test_seed_identique_entre_processus_hashseed_differents():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"
        other = Path(d) / "other"
        a = _generate(1337, "0", base)
        b = _generate(1337, "1", other)
        assert a.read_bytes() == b.read_bytes(), "seed.json diffère selon PYTHONHASHSEED"