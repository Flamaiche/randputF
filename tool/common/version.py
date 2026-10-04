"""Version unique du mod randputF (source de verite : ``mod/info.json``).

Centralise ``name``/``version``/``factorio_version`` pour que le tool, la seed
et l'assemblage partagent la MÊME valeur de version (plus de 5 endroits a
synchroniser a la main a chaque release). Toute version part d'ici.
"""

from __future__ import annotations

import json
from pathlib import Path

_MOD_INFO = Path(__file__).resolve().parent.parent.parent / "mod" / "info.json"


def _read_info() -> dict:
    try:
        return json.loads(_MOD_INFO.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # Wheel installé hors dépôt : mod/info.json n'est pas embarqué, on
        # retombe sur les métadonnées du paquet (pyproject.toml). Dans une
        # copie du dépôt (ou un install -e), mod/info.json reste l'autorité.
        from importlib.metadata import version

        return {
            "name": "randputF",
            "version": version("randputf"),
            "factorio_version": "2.0",
        }


_INFO = _read_info()

MOD_NAME = _INFO["name"]                 # "randputF"
VERSION = _INFO["version"]               # lu dans mod/info.json
MOD_NAME_VERSIONED = f"{MOD_NAME}_{VERSION}"  # "randputF_<version>"
FACTORIO_VERSION = _INFO["factorio_version"]  # "2.0"