# Témoin de déterminisme

randputF prouve son déterminisme par les faits. Son témoin est une empreinte numérique que chacun peut calculer et vérifier lui-même.

Ce document présente le rôle de ce témoin, la méthode de canonisation qui assure sa reproductibilité et les pièges techniques contournés.

Retour : [README.md](../README.md) · [nondeterminism.md](nondeterminism.md).

---

## 1. Le témoin en une commande

```bash
pip install .
randputf witness --seed 5 --expect ce428c2140ec7031f9604637ecf70cbc
```

L'empreinte de la version actuelle (1.0.1) s'établit ainsi :

```
ce428c2140ec7031f9604637ecf70cbc
```

> Ce hash correspond à la **v1.0.1**, la version courante sur le dépôt.
> Il **change à chaque bump de version** (le dossier racine de l'archive intègre `randputF_<version>`, voir §3.4), même si le contenu du mod ne change pas.
> Pour la version que vous testez, lisez l'empreinte consignée dans `.github/workflows/ci.yml`, qui est toujours à jour.

L'instruction `witness --seed 5` assemble le mod lié à la seed 5 avant d'en calculer le md5 canonique. L'option `--expect <hash>` effectue la comparaison et produit une erreur en cas d'écart. Sans `--expect`, la commande se contente de générer et d'afficher le témoin.

L'assemblage s'effectue sur l'arbre de travail courant (le wheel embarque l'intégralité des ressources), et non depuis un tag : ce parcours reproduit fidèlement la situation d'un utilisateur.

Dans le workflow d'intégration, `ci.yml` utilise `--expect` (une divergence produit une sortie 1, ce qui est bloquant). À l'inverse, `release.yml` lance le témoin sans `--expect` (la divergence n'y est pas bloquante, seule la réussite de la génération compte).

## 2. Ce qui est garanti

- **Au bit près** : un contenu de mod identique produit le même md5 sur n'importe quelle machine, peu importe la version de Python ou de zlib.
- **Vérifié automatiquement** : l'action CI « wheel » (`.github/workflows/ci.yml`, Python 3.12) installe le paquet depuis une copie vierge, réévalue le témoin **depuis `/tmp`, hors checkout**, puis contrôle sa concordance avec le hash attendu.
- **Identique depuis les tags** : chacun peut réexécuter la commande ci-dessus depuis le tag de la version testée pour retrouver la même empreinte. Le témoin dépendant de la version (§3.4), le hash attendu est celui associé à cette version dans `ci.yml`.

Périmètre du contrôle : le témoin prouve la reproductibilité **à contenu égal**. Il ne garantit pas la solubilité d'une seed (ce point relève des invariants du §15 et du rejoueur, voir [solvabilite.md](solvabilite.md)).

## 3. La canonisation

Le md5 s'applique à un zip de référence généré de manière strictement déterministe par `tool/common/witness.py`. Chaque règle élimine une source d'instabilité mesurée :

| Brique | Ce qu'elle élimine |
|---|---|
| Chemins triés par chemin relatif canonique (`/`) | L'ordre de lecture du système de fichiers |
| Entrées **stockées** (`ZIP_STORED`, pas compressé) | La variation de zlib d'une machine à l'autre |
| Timestamp figé (1980-01-01) et mode 0644 | Les dates et permissions des fichiers |
| Champ « version made by » figé (`create_system = 3`) | La dérivation de `sys.platform` dans le zip |
| Préfixe racine fixé à `randputF_<version>` | Le nom du dossier d'assemblage local |

### 3.1 `os.walk` ne suffit pas

Un piège subtil réside dans `sorted(os.walk(dir))` : cette syntaxe trie les tuples **après** le parcours de l'arborescence par le générateur. Les fichiers sortent donc dans l'ordre fourni par `os.scandir`, lequel **varie selon la machine**. La méthode correcte exige de **collecter d'abord l'intégralité des chemins**, puis de les trier par chemin relatif canonique (`canonical_entries`). C'est le choix appliqué dans le code.

### 3.2 La déflation n'est pas stable

Constat mesuré : zlib 1.3.1.zlib-ng (Python 3.14) et zlib 1.3.2 (Python 3.12) compressent un octet identique en deux blocs distincts. Le témoin recourt donc uniquement à des entrées **stockées** (non compressées) : le md5 repose directement sur le **contenu**, sans subir l'encodage de la compression.

### 3.3 Le champ « version made by » du zip

Par défaut, la bibliothèque `zipfile` dérive `create_system` depuis `sys.platform` (0 sous win32, 3 sur les autres systèmes), et ce champ altère le md5. Ce comportement produisait un témoin divergent entre Windows et POSIX. Fixer cette valeur à POSIX (`create_system = 3`) assure la parité Windows↔POSIX.

### 3.4 Préfixe racine et nom de dossier

Le nom du répertoire d'assemblage ne doit pas influer sur le md5 : exécuter le traitement sur un dossier renommé doit renvoyer le même résultat pour un contenu inchangé. Le zip de référence ajoute donc en préfixe de chaque entrée la chaîne `randputF_<version>`, issue de la version du mod (`tool/common/version.py`, tirée de `mod/info.json`). Le mod installé conserve systématiquement cette dénomination.

> **Conséquence pour une release** : le md5 du témoin dépend directement du numéro de version (le préfixe racine intégrant `randputF_<version>`). Modifier la version génère un nouveau témoin. Pour la procédure de publication, voir `docs/release.md`. Le fichier `notes/README.md` (accessible via [notes/README.md](../notes/README.md)) sert quant à lui de gabarit d'écriture de note.

## 4. Ce qui est exclu du témoin

Le fichier `seed.graph.html` est **exclu** du zip de référence (`WITNESS_EXCLUDED`). En cause : le bloc `<svg>` embarqué contient un commentaire mentionnant la version de Graphviz, variable d'un système à l'autre. Ce graphe reste régénérable et ne fait pas l'objet d'une garantie au bit près. L'ensemble du reste du mod (incluant `seed.json` et `seed.lua`) demeure couvert.

## 5. Relation avec le déterminisme de la seed

Le témoin atteste la **reproductibilité de l'assemblage** (pour un même contenu de seed, le zip produit reste identique). Le déterminisme de la seed elle-même (obtenir un contenu généré identique pour une même valeur `--seed`) constitue une propriété distincte, documentée et contrôlée dans [nondeterminism.md](nondeterminism.md) et [seed.md](seed.md) (§16) : absence d'itération sur un `set`/`frozenset` pour alimenter un `rng`, tri systématique avant d'exploiter un `set`, et indépendance du traitement de chaque seed au sein d'un même processus.
