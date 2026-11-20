"""Régression CLI : ``generate --install`` avec ``paths.factorio_mods`` vide.

Le défaut de ``config/defaults.yaml`` (``paths.factorio_mods: ""``) laisse le
champ vide sauf surcharge dans ``config/user.yaml``. Bug corrigé :
la chaîne vide (falsy) faisait retomber sur ``Path()`` = ``.``, un dossier
TOUJOURS valide — le mod était alors déposé à la racine du dépôt (plus un
``mod-list.json``) au lieu du fallback ``output/``. Ce test verrouille qu'aucun
``randputF_*`` / ``mod-list.json`` n'apparaît jamais à la racine.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from tool.common.version import MOD_NAME_VERSIONED


@pytest.fixture
def empty_user_config(tmp_path: Path):
    """Isole le test des surcharges réelles de ``config/user.yaml``."""
    user = ROOT / "config" / "user.yaml"
    backup = None
    if user.exists():
        backup = tmp_path / "user.yaml"
        shutil.copy2(user, backup)
        user.unlink()
    try:
        yield
    finally:
        if backup is not None:
            shutil.copy2(backup, user)


def test_install_factorio_mods_vide_retombe_sur_output(empty_user_config):
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
    assert not (ROOT / MOD_NAME_VERSIONED).exists()
    assert not (ROOT / "mod-list.json").exists()

    # Le fallback atteint bien output/ : le mod y est assemblé tel quel.
    asm = ROOT / "output" / MOD_NAME_VERSIONED
    assert asm.is_dir()
    assert (asm / "info.json").is_file()
    assert (asm / "data.lua").is_file()
    assert not (asm / "seed.graph.html").exists()  # pas de graphe avec --install


@pytest.fixture
def user_config_mods(tmp_path: Path):
    """Isole le test avec un dossier mods temporaire et l'exporter actif."""
    mods = tmp_path / "mods"
    mods.mkdir()
    (mods / "mod-list.json").write_text(
        json.dumps(
            {
                "mods": [
                    {"name": "base", "enabled": True},
                    {"name": "randputf-exporter", "enabled": True},
                ]
            }
        ),
        encoding="utf-8",
    )
    user = ROOT / "config" / "user.yaml"
    backup = None
    if user.exists():
        backup = tmp_path / "user.yaml"
        shutil.copy2(user, backup)
        user.unlink()
    user.write_text(f"paths:\n  factorio_mods: {mods.as_posix()}\n", encoding="utf-8")
    try:
        yield mods
    finally:
        user.unlink(missing_ok=True)
        if backup is not None:
            shutil.copy2(backup, user)


def test_install_ne_desactive_pas_l_exporter(user_config_mods: Path):
    out = subprocess.run(
        [sys.executable, "-m", "tool", "generate", "--seed", "5", "--install"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr

    data = json.loads((user_config_mods / "mod-list.json").read_text(encoding="utf-8"))
    exporter = next(m for m in data["mods"] if m["name"] == "randputf-exporter")
    assert exporter["enabled"] is True
