"""Version unique du mod randputF (source de verite : ``mod/info.json``).

Centralise ``name``/``version``/``factorio_version`` pour que le tool, la seed
et l'assemblage partagent la MÊME valeur de version (plus de 5 endroits a
synchroniser a la main a chaque release). Toute version part d'ici.
"""

from __future__ import annotations

import json
from pathlib import Path

_MOD_INFO = Path(__file__).resolve().parent.parent.parent / "mod" / "info.json"
_INFO = json.loads(_MOD_INFO.read_text(encoding="utf-8"))

MOD_NAME = _INFO["name"]                 # "randputF"
VERSION = _INFO["version"]               # "1.0.0"
MOD_NAME_VERSIONED = f"{MOD_NAME}_{VERSION}"  # "randputF_1.0.0"
FACTORIO_VERSION = _INFO["factorio_version"]  # "2.0"