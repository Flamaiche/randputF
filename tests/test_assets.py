"""Les assets (mod/, data/, config/) voyagent dans le wheel.

Régression du packaging : ``randputf generate`` planterait sur
``MOD_SOURCE.iterdir()`` si ``pip install .`` n'embarquait pas les trois
dossiers (namespace packages). Ces tests verrouillent la résolution en mode
dépôt/éditable (où tourne pytest) ; le wheel lui-même est couvert par le job
CI « wheel » qui joue la recette du témoin de release.
"""

from pathlib import Path

from tool.common.assets import asset_path, repo_root


def test_asset_mod_resolved():
    assert (asset_path("mod") / "info.json").exists()


def test_asset_data_resolved():
    assert (asset_path("data") / "vanilla_dump.json").exists()


def test_asset_config_resolved():
    assert (asset_path("config") / "settings.yaml").exists()


def test_asset_inconnu_leve_erreur_claire():
    import pytest

    with pytest.raises(ValueError, match="Asset inconnu: 'missing'"):
        asset_path("missing")