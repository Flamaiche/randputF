# Témoin de déterminisme

randputF ne **réclame** pas le déterminisme, il le **démontre** : le témoin est
un hash que n'importe qui peut recalculer et comparer.

Ce document explique ce qu'est le témoin, comment la canonisation le rend
reproductible, et les pièges qu'elle évite (tous mesurés en réel, pas supposés).

Retour : [README.md](../README.md) · [nondeterminism.md](nondeterminism.md).

---

## 1. Le témoin en une commande

```bash
pip install .
randputf witness --seed 5 --expect 12ac143e06174df126537b978ff928d3
```

Le témoin v1.0.0 (tag `v1.0.0`) est :

```
12ac143e06174df126537b978ff928d3
```

`witness --seed 5` assemble le mod pour la seed 5 puis calcule son md5
canonique. `--expect <hash>` compare et sort en erreur si le résultat diffère.
Sans `--expect`, la commande se contente de générer et d'afficher le témoin.

La commande assemble le mod **depuis le tag** (le wheel embarque tous les
assets), pas depuis un checkout de développement : c'est le chemin le plus
proche de ce que fait un visiteur.

## 2. Ce qui est garanti

- **À l'octet près** : même contenu de mod → même md5, sur n'importe quelle
  machine, quelle que soit la version de Python ou de zlib.
- **Vérifié automatiquement** : le job CI « wheel » (`.github/workflows/ci.yml`,
  Python 3.12) installe le paquet depuis un checkout frais et recalcule le
  témoin **depuis `/tmp`, hors checkout**, puis le compare au hash attendu.
- **Le même depuis les tags** : n'importe qui peut refaire la commande ci-dessus
  depuis le tag `v1.0.0` et retomber sur le même hash.

Ce que le témoin ne couvre pas : il prouve la reproductibilité **à contenu
égal**, pas la solubilité d'une seed (ça, ce sont les invariants §15 et le
rejoueur, voir [solvabilite.md](solvabilite.md)).

## 3. La canonisation

Le md5 est calculé sur un zip « de référence » construit de façon déterministe
(`tool/common/witness.py`). Chaque brique supprime une source de variation
réelle :

| Brique | Ce qu'elle élimine |
|---|---|
| Chemins triés par chemin relatif canonique (`/`) | L'ordre de lecture du système de fichiers |
| Entrées **stockées** (`ZIP_STORED`, pas compressé) | La variation de zlib d'une machine à l'autre |
| Timestamp figé (1980-01-01) et mode 0644 | Les dates et permissions des fichiers |
| Champ « version made by » figé (`create_system = 3`) | La dérivation de `sys.platform` dans le zip |
| Préfixe racine fixé à `randputF_<version>` | Le nom du dossier d'assemblage local |

### 3.1 `os.walk` ne suffit pas

Le piège le plus subtil : `sorted(os.walk(dir))` trie les tuples **après** que
le générateur a déjà parcouru l'arborescence. L'ordre d'émission des fichiers
reste celui d'`os.scandir`, qui **varie selon la machine**. La bonne approche est
de **collecter d'abord tous les chemins**, puis de trier par chemin relatif
canonique (`canonical_entries`). C'est ce que fait le code.

### 3.2 La déflation n'est pas stable

Mesuré : zlib 1.3.1.zlib-ng (Python 3.14) et zlib 1.3.2 (Python 3.12)
compressent le même octet en deux blocs différents. Le témoin n'utilise donc que
des entrées **stockées** (non compressées) : le md5 dépend du **contenu**, pas
de l'encodage de sa compression.

### 3.3 Le champ « version made by » du zip

Par défaut, `zipfile` dérive `create_system` de `sys.platform` (0 sur win32, 3
ailleurs) et ce champ entre dans le md5. Il rendait le témoin différent sur
Windows et POSIX. Il est forcé à POSIX (`create_system = 3`), d'où la promesse
Windows↔POSIX.

### 3.4 Préfixe racine et nom de dossier

Le nom du dossier assemblé ne doit pas entrer dans le md5 (un appel sur un
dossier renommé doit donner le même digest pour le même contenu). Le zip de
référence préfixe donc chaque entrée par `randputF_<version>`, la version
« versioned » du mod (`tool/common/version.py`, issue de `mod/info.json`). Le
mod installé portera toujours ce nom.

> **Conséquence pour une release** : le md5 du témoin dépend de la version (le
> préfixe racine contient `randputF_<version>`). Bump de version = nouveau
> témoin. Voir `RELEASE.md` (procédure de publication).

## 4. Ce qui est exclu du témoin

`seed.graph.html` est **exclu** du zip de référence (`WITNESS_EXCLUDED`). Raison :
le `<svg>` embarqué porte un commentaire de version de Graphviz, qui varie d'une
machine à l'autre ; le graphe est régénérable et ne porte pas la garantie de
l'octet. Le reste du mod (y compris `seed.json`, `seed.lua`) est couvert.

## 5. Relation avec le déterminisme de la seed

Le témoin prouve la **reproductibilité de l'assemblage** (étant donné le même
contenu de seed, le même zip). Le déterminisme de la seed elle-même (étant donné
la même valeur `--seed`, le même contenu généré) est une propriété distincte,
documentée et testée dans [nondeterminism.md](nondeterminism.md) et
[seed.md](seed.md) (§16) : absence d'itération de `set`/`frozenset` alimentant
un `rng`, tri systématique avant toute consommation d'un `set`, indépendance de
l'ordre des seeds dans un même process.