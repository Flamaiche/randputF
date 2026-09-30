"""Témoin de déterminisme de la release : md5 « à l'octet près » du mod assemblé.

Le témoin prouve qu'un visiteur, en régénérant une seed depuis le tag, retombe
sur exactement le même mod. C'est une méthode de MESURE : elle doit être
reproductible à l'octet près sur n'importe quelle machine, indépendamment de
l'ordre de lecture du système de fichiers.

Pitfalls évités ici (tous mesurés en réel, pas supposés) :
- ``sorted(os.walk(dir))`` trie les tuples APRÈS que le générateur a déjà
  parcouru l'arborescence : l'ordre d'émission reste celui d'``os.scandir``,
  qui varie selon la machine → on collecte d'abord les chemins, puis on trie
  par chemin relatif canonique ;
- ``seed.graph.html`` embarque un commentaire de version Graphviz dans son
  ``<svg>`` → exclu du témoin (régénérable, il ne porte pas la garantie) ;
- la DÉFLATION n'est PAS stable d'une machine/version à l'autre : mesuré,
  zlib 1.3.1.zlib-ng (Python 3.14) et 1.3.2 (Python 3.12) compressent le même
  octet en deux blocs différents → le témoin n'utilise que des entrées
  STOCKÉES, pour que le md5 dépende du contenu, pas de l'encodage de sa
  compression.

Le zip de référence est construit en mode déterministe : entrées stockées
(non compressées), triées par chemin relatif, dates et modes fixés. Le
résultat ne dépend que du CONTENU des fichiers — le md5 est donc reproductible
à l'octet près sur n'importe quelle machine, quelle que soit la version de
Python/zlib.
"""

from __future__ import annotations

import hashlib
import io
import os
import zipfile
from pathlib import Path

from tool.common.version import MOD_NAME_VERSIONED

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


def witness_md5(mod_dir: Path, prefix: str | None = None) -> str:
    """md5 du mod assemblé, canonisé en zip déterministe.

    ``mod_dir`` est le dossier du mod assemblé. L'entrée racine est préfixée
    par ``prefix``, fixé à ``MOD_NAME_VERSIONED`` (ex. ``randputF_1.0.0``) —
    PAS au nom du dossier : un appel sur un dossier renommé doit donner le
    même digest pour le même contenu. Le mod installé PORTERA toujours ce
    nom (``_build_mod``) : le témoin publié ne dépend pas de l'endroit où on
    a assemblé.
    """
    root_prefix = prefix or MOD_NAME_VERSIONED
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:  # entrées STOCKÉES : zlib build-indépendant
        for rel, path in canonical_entries(mod_dir):
            zi = zipfile.ZipInfo(f"{root_prefix}/{rel}", _ZIP_DATE)
            zi.compress_type = zipfile.ZIP_STORED
            # Field « version made by » figé : par défaut, zipfile dérive
            # create_system de sys.platform (0 sur win32, 3 ailleurs) et ce
            # champ entre dans le md5. Forcé à POSIX pour que le témoin soit
            # identique sur n'importe quelle machine.
            zi.create_system = 3
            zi.create_version = 20
            zi.external_attr = _ZIP_MODE
            zf.writestr(zi, path.read_bytes())
    return hashlib.md5(buf.getvalue()).hexdigest()