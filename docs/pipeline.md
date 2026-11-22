# Pipeline de génération

Retour : [docs/README.md](README.md).

Le pipeline transforme une seed et un dump en contenu de partie. Il enchaîne des phases courtes, chacune avec un rôle précis. Il n'écrit aucun fichier : l'assemblage vient ensuite.

## Ce que ça change pour l'utilisateur

- Une même seed produit toujours le même monde.
- Les ressources, recettes et technologies sont construites dans un ordre fixe.
- Seule la commande `generate` relance une génération si la seed est jugée non jouable.

## Mots à connaître

- [seed](glossaire.md) — graine qui fixe tous les tirages.
- [jalon](glossaire.md) — étape qui garantit une catégorie de contenu.
- [RNG](glossaire.md) — générateur aléatoire contrôlé par la seed.
- [bootstrap](glossaire.md) — phase initiale qui rend le départ fabriquable.
- [validateur](glossaire.md) — contrôle appliqué à une seed ou au pipeline.

## Fonctionnement

### Les trois fonctions d'orchestration

| Fonction | Rôle |
|---|---|
| `_build_prefix` | construit le départ, l'électricité, les fluides et les gisements |
| `generate_seed` | choisit la configuration, les tirages de carte et la passe à retenir |
| `_finalize_pipeline` | ajoute la récursion, la fusée, les techs et la validation journalisée |

Cette séparation permet de rejouer le préfixe quand les jalons de ressources tardives sont actifs.

### Les étapes courantes

1. La configuration est fusionnée puis distribuée aux phases.
2. Les lacs sont tirés avant les gisements, pour ne jamais donner deux usages au même fluide.
3. Le départ, l'électricité et les fluides de bâtiments sont construits.
4. Un état figé sert de source aux recettes de secours.
5. La récursion couvre les items, les armes, les sciences et les bâtiments.
6. La chaîne de fusée, les relais, les prologues et les techs sont assemblés.
7. Le validateur structurel journalise ses observations sans bloquer la génération.
8. La seed complète est renvoyée à l'appelant.

Le dictionnaire de sortie contient notamment `meta`, `pools`, `map`, `starter_kit`, `recipes`, `technologies` et `progression_order`. La clé `difficulty` est ajoutée plus tard, lors de l'export.

### Les flux RNG du pipeline

Chaque flux porte un préfixe stable et dérive de la seed. Le flux principal est partagé par la plupart des phases.

| Préfixe | Usage |
|---|---|
| `randputF:` | flux principal : gisements, départ, électricité, récursion, techs |
| `randputF:lakes:` | lacs |
| `randputF:wells:` | positions des puits et centres de gisements |
| `randputF:nonfinite:` | facteurs de richesse et de rayon |
| `randputF:easeup:` | recettes de secours |
| `randputF:craft_quantity:` | quantités de craft |

Les deux passes de jalons de ressources tardives reposent sur le même état de RNG. La configuration est copiée avant la seconde passe pour éviter toute fuite entre seeds.

### La reprise du CLI

`generate` appelle `generate_with_retry`. Le solver vérifie la seed et, en cas de problème, une graine dérivée est essayée jusqu'à dix fois. `difficulty` et `witness` appellent `generate_seed` directement, sans cette reprise.

### Écart connu

D'anciens documents décrivaient la reprise comme commune à plusieurs commandes. Le code ne l'applique qu'à `generate`. Reste à faire : limiter cette mention à la seule commande concernée dans les documents historiques.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| L'ordre des phases est stable pour un triplet dump, configuration, seed donné. | Une seed peut être structurellement correcte et non solvable. |
| Les flux RNG sont séparés par préfixe. | Le nombre de tentatives de `generate` est limité à dix. |
| Le pipeline ne modifie aucune entité de jeu. | Les modules non branchés ne changent pas la seed. |

## Aller plus loin

- [architecture.md](architecture.md) — à lire quand il faut situer le pipeline dans le projet.
- [modules.md](modules.md) — à lire quand il faut identifier le module d'une phase.
- [nondeterminism.md](nondeterminism.md) — à lire quand le déterminisme doit être vérifié.
- [graphe-interactif.md](graphe-interactif.md) — à lire quand il faut consulter les sorties HTML.
- [DEVIANCES.md](DEVIANCES.md) — à lire quand une dérive de génération est observée.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [seed.md](seed.md) — graine et configuration.
- [solvabilite.md](solvabilite.md) — validation et rejeu.
- [etat-code.md](etat-code.md) — état courant des composants.
