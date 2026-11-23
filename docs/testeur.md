# Testeur et audit de seed

Retour : [docs/README.md](README.md).

Le testeur contrôle une seed avec le rejoueur Python. Il valide la structure, simule la progression, puis peut écrire un rapport détaillé. La simulation fait partie du contrôle, pas d'une option.

## Ce que ça change pour l'utilisateur

- `randputf test` rejoue la seed par défaut.
- Le dump moddé est accepté, comme pour les autres commandes.
- `--playthrough` n'ajoute que la section simulée dans le rapport.

## Mots à connaître

- [rejeu](glossaire.md) — simulation de la progression sans interface Factorio.
- [blocker](glossaire.md) — point où la progression s'arrête.
- [solvabilité](glossaire.md) — capacité d'une seed à atteindre la victoire.
- [dump](glossaire.md) — photographie des prototypes utilisée comme base.

## Fonctionnement

### Ce que fait la commande

`randputf test` lit l'état depuis le dump ou depuis le mod, charge la configuration, puis appelle le contrôle. Le contrôle enchaîne deux étapes.

| Étape | Rôle |
|---|---|
| validation structurelle | vérifie cycles, progression et cohérence des liens |
| simulation | joue la seed avec le joueur simulé, jusqu'à la victoire ou au blocage |

La simulation est toujours exécutée par `check_state`. La fonction `run_dump_test` l'appelle également. Le rapport peut ensuite masquer ou afficher la section détaillée.

### Le rôle de `--playthrough`

`--playthrough` ne déclenche pas le rejeu. Il commande seulement l'impression de la section « partie simulée » du rapport. Sans lui, cette section est marquée comme ignorée, alors que le rejeu a bien eu lieu.

L'option n'est pas disponible sur toutes les commandes. `report` la porte avec `--dump`. `test` utilise l'option `--dump`, dont la valeur par défaut est `data/vanilla_dump.json`.

### Résultats du joueur simulé

| État | Signification |
|---|---|
| `blocker` | la progression s'arrête avant la victoire |
| `mastered` | la catégorie est entièrement maîtrisée |
| `never_masterable` | aucune voie ne permet d'atteindre la catégorie |
| `victory` | la chaîne de fusée est achevée |

Un succès affiche le nombre de technologies recherchées. Un échec affiche le premier motif rapporté par le validateur ou le rejoueur.

### Écart connu

D'anciens documents présentaient le rejeu comme activé uniquement par `--playthrough`. Le code appelle `play` dans tous les contrôles de `tool/tester.py` ; l'option ne met en forme que le rapport.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une seed est rejouée avant d'être déclarée valide. | Un rejeu réussi ne remplace pas une partie humaine. |
| Le dump moddé est traité comme dans les autres commandes. | Les mods tiers peuvent introduire des cas non couverts. |
| Le rapport sépare clairement structure et simulation. | La section simulée peut être masquée. |

## Aller plus loin

- [solvabilite.md](solvabilite.md) — à lire quand un motif de blocage est recherché.
- [nomenclature-rejoueur.md](nomenclature-rejoueur.md) — à lire quand le vocabulaire du joueur simulé est nécessaire.
- [graphe-interactif.md](graphe-interactif.md) — à lire quand le rapport HTML est utilisé.
- [witness.md](witness.md) — à lire quand la reproductibilité doit être vérifiée.
- [DEVIANCES.md](DEVIANCES.md) — à lire quand un bug de graphe est revisité.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [modules.md](modules.md) — rôle du module `test`.
- [pipeline.md](pipeline.md) — rôle du validateur dans la génération.
- [etat-code.md](etat-code.md) — état du rejoueur et du validateur.
