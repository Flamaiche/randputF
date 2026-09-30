"""Témoin de déterminisme de la release : md5 « à l'octet près » du mod assemblé.

Le témoin prouve qu'un visiteur, en régénérant une seed depuis le tag, retombe
sur exactement le même mod. C'est une méthode de MESURE : elle doit être
reproductible à l'octet près sur n'importe quelle machine, indépendamment de
l'ordre de lecture du système de fichiers.

Pitfalls évités ici (les deux ont déjà fuité en production) :
- ``sorted(os.walk(dir))`` trie les tuples APRÈS que le générateur a déjà
  parcouru l'arborescence : l'ordre d'émission reste celui d'``os.scandir``,
  qui varie selon la machine (vu en réel : locale/en vs locale/fr) → on
  collecte d'abord les chemins, puis on trie par chemin relatif canonique ;
- ``seed.graph.html`` embarque un commentaire de version Graphviz dans son
  ``<svg>`` → exclu du témoin (régénérable, il ne porte pas la garantie).

Le zip de référence est construit en mode déterministe : entrées triées par
chemin relatif, dates et modes fixés, déflation de niveau 9. Le résultat ne
dépend plus que du CONTENU des fichiers.
"""

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from pathlib import Path

# Entrées exclues du témoin (voir docstring).
WITNESS_EXCLUDED = {"seed.graph.html"}

# Timestamp figé des entrées du zip (Indiana Jones : 1980-01-01) et mode 0644.
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_ZIP_MODE = 0o100644 << 16


def canonical_entries(mod_dir: Path, excluded: set[str] = WITNESS_EXCLUDED):
    """Énumère (chemin relatif canonique, chemin absolu) de tous les fichiers
    du mod, trié par chemin relatif en ``/`` — indépendant de l'ordre de
    lecture du système de fichiers."""
    entries = []
    for root, _, files in os.walk(mod_dir):
        for name in files:
            if name in excluded:
                continue
            path = Path(root) / name
            rel = path.relative_to(mod_dir).as_posix()
            entries.append((rel, path))
    entries.sort(key=lambda entry: entry[0])
    return entries


def witness_md5(mod_dir: Path) -> str:
    """md5 du mod assemblé, canonisé en zip déterministe.

    ``mod_dir`` doit être le dossier du mod ``randputF_<version>/``. L'entrée
    racine est préfixée ``randputF_<version>/`` (le nom du mod installé).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, path in canonical_entries(mod_dir):
            zi = zipfile.ZipInfo(f"{mod_dir.name}/{rel}", _ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = _ZIP_MODE
            zf.writestr(zi, path.read_bytes())
    return hashlib.md5(buf.getvalue()).hexdigest()