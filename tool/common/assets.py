"""Résolution des assets top-level du tool (``mod/``, ``data/``, ``config/``).

En install classique (``pip install .``), les trois dossiers voyagent dans le
wheel comme namespace packages (``mod``, ``data``, ``config``) ; en dev
(checkout du dépôt ou ``pip install -e .``), ce sont les dossiers réels à la
racine. ``asset_path`` préfère le chemin installé puis vérifie le marqueur
attendu, et retombe sinon sur la racine du dépôt (éditable). Exemple :

- wheel →  site-packages/mod, site-packages/data, site-packages/config
- dépôt  →  <racine>/mod, <racine>/data, <racine>/config
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

# Marqueur attendu par asset : sa présence valide le chemin résolu.
_ASSET_MARKERS = {
    "mod": "info.json",
    "data": "vanilla_dump.json",
    "config": "settings.yaml",
}


def repo_root() -> Path:
    """Racine du paquet ``tool`` (repos du dépôt en dev, site-packages en wheel)."""
    return Path(__file__).resolve().parent.parent.parent


def asset_path(name: str) -> Path:
    """Chemin d'un asset embarqué ou présent dans le dépôt.

    ``name`` ∈ {"mod", "data", "config"}. Résolution : (1) le dossier installé
    (namespace package, e.g. ``site-packages/mod``) si le marqueur y est ;
    (2) sinon la racine du dépôt (install -e / checkout). Lève une erreur
    explicite si aucun des deux ne porte le marqueur.
    """
    if name not in _ASSET_MARKERS:
        raise ValueError(
            f"Asset inconnu: {name!r} (connus: {', '.join(sorted(_ASSET_MARKERS))})"
        )
    marker = _ASSET_MARKERS[name]
    candidates = []
    try:
        candidates.append(Path(str(importlib.resources.files(name))))
    except Exception:  # non installé en namespace package
        pass
    candidates.append(repo_root() / name)

    for candidate in candidates:
        if (candidate / marker).exists():
            return candidate
    raise FileNotFoundError(
        f"Asset '{name}' introuvable (marqueur '{marker}' absent de : "
        + " ; ".join(str(c) for c in candidates)
        + ") — réinstalle le paquet (pip install .) ou exécute depuis un "
        "checkout du dépôt."
    )