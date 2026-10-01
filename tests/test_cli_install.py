"""Régression CLI : ``generate --install`` avec ``paths.factorio_mods`` vide.

Le défaut de ``config/defaults.yaml`` (``paths.factorio_mods: ""``) laisse le
champ vide sauf surcharge dans ``config/user.yaml``. Bug corrigé :
la chaîne vide (falsy) faisait retomber sur ``Path()`` = ``.``, un dossier
TOUJOURS valide — le mod était alors déposé à la racine du dépôt (plus un
``mod-list.json``) au lieu du fallback ``output/``. Ce test verrouille qu'aucun
``randputF_*`` / ``mod-list.json`` n'apparaît jamais à la racine.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_install_factorio_mods_vide_retombe_sur_output():
    out = subprocess.run(
        [sys.executable, "-m", "tool", "generate", "--seed", "5", "--install"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr

    assert "mod assemble dans" in out.stdout
    assert "Aucun dossier mods configure" in out.stdout

    # Le bug déposait le mod à la racine : ces deux artefacts ne doivent JAMAIS
    # exister ici (le fallback va dans output/).
    assert not (ROOT / "randputF_1.0.0").exists()
    assert not (ROOT / "mod-list.json").exists()

    # Le fallback atteint bien output/ : le mod y est assemblé tel quel.
    asm = ROOT / "output" / "randputF_1.0.0"
    assert asm.is_dir()
    assert (asm / "info.json").is_file()
    assert (asm / "data.lua").is_file()
    assert not (asm / "seed.graph.html").exists()  # pas de graphe avec --install