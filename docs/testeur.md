# Testeur de dump — contrôle, rejeu et trois vues HTML

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Le testeur (`tool/tester.py`) vérifie un état de jeu déjà acquis et produit ses statistiques. Il ne tire aucune graine et n'assemble aucun mod : la graine appartient uniquement à la création d'un mod avec `randputf generate`.

## Entrées

| Entrée | Commande | Origine de l'état testé |
|---|---|---|
| Dump fixe | `randputf test --dump <fichier.json>` | état normalisé directement depuis le dump |
| Mod existant | `randputf test --dump <fichier.json> --mod-dir <dossier>` | état déjà assemblé lu depuis `seed/seed.json` |

Dans les deux cas, le dump fourni reste la source de vérité pour l'identité, les noms et les trois pages HTML. Le préfixe des fichiers vient de `meta.mod_label` pour les dumps 0.1.8+, sinon du nom du fichier.

## Les cinq étapes

| Étape | Fonction | Rôle |
|---|---|---|
| `acquisition` | `json.loads` / `build_vanilla_seed()` | lit le dump et normalise les faits disponibles |
| `controle` | `validate_seed()` | détecte cycles, invariants violés et déblocages incohérents |
| `rejeu` | `play()` | simule une partie « vrai joueur » depuis les faits du dump |
| `mesure` | `write_full_report()` / `compute_difficulty()` | calcule complexité, difficulté et partie simulée |
| `rapport` | `run_dump_test()` | écrit les trois HTML préfixés par la source |

Ces noms sont exposés dans `tool.tester.STAGES` et servent de référence commune à la CLI, aux tests et à cette documentation. `tool.tester.STAGE_LABELS` donne les libellés affichés par la barre de progression : « Acquisition du dump », « Contrôle de l'état », « Rejeu joueur », « Mesure de la difficulté » et « Rapport HTML ».

La CLI `randputf test` affiche cette progression en Python pur, sans dépendance : nom de l'étape, barre, pourcentage de l'étape courante, numéro de l'étape sur le total, action en cours, temps écoulé en secondes et fin estimée de l'étape. Sur un terminal, la ligne est rafraîchie sur place ; sinon chaque changement d'étape produit une ligne.

```text
Rejeu joueur [████████░░░░░░░░░░░░]  40% 3/5 — partie simulée ·   3.2s · fin étape ~5s
```

Le rejeu ne suit pas un ordre linéaire : à chaque passe, il cherche toutes les techs dont les prérequis sont satisfaits et dont le coût est abordable, en recherche une, puis recalcule la fermeture. Un blocage n'est donc signalé que si aucune tech disponible ne peut être financée. C'est indispensable aux arbres moddés où une tech tardive dans l'ordre topologique peut être le prochain déblocage utile.

Un échec de contrôle ou de rejeu n'est pas masqué : il est affiché en console et écrit dans la section `#controles` du rapport. La commande sort avec le code 2, sans relancer de génération ni essayer une autre valeur.

## Trois pages HTML

Pour un dump `vanilla_dump.json` identifié `vanilla` :

```text
output/vanilla/vanilla.dump.html     navigateur du dump
output/vanilla/vanilla.graph.html    graphe de production
output/vanilla/vanilla.report.html   contrôles + complexité + difficulté + partie simulée
```

Le dossier porte le nom du dump (`meta.mod_label`, sinon le nom du fichier), ou le nom du dossier du mod avec `--mod-dir`.

Au-delà de 10 000 recettes, le rapport passe en vue réduite : résumé, contrôles, couverture et difficulté sont conservés ; les courbes de complexité et la partie simulée détaillée sont omises. Les grands graphes utilisent `sfdp` au lieu de `dot` pour éviter les erreurs mémoire ; si Graphviz ne peut pas rendre le SVG, la page graphe contient une vue textuelle des technologies et recettes.

Les ancres stables du rapport sont décrites par `tool.tester.SECTIONS` : `controles`, `couverture-dump`, `complexite-courbes`, `difficulte`, `partie-simulee`.

La section `#couverture-dump` classe les champs réellement présents dans le dump en quatre états : consommé, partiel, à consommer et cosmétique. La CLI affiche les mêmes totaux avant les problèmes de contrôle, par exemple :

```text
Couverture : Consommé 45 · Partiel 9 · À consommer 0 · Cosmétique 54
```

## Commandes

```bash
randputf test --dump data/vanilla_dump.json
randputf test --dump /chemin/au/dump.json --out output/modpack/
randputf test --dump /chemin/au/dump.json --mod-dir output/randputF_0.0.1/
```

Aucune de ces commandes ne génère de mod. Les options `--seed` et `--seed-file` de l'ancien flux n'existent plus sur `test`.

## Lectures associées

- **Parent** : [architecture.md](architecture.md) — structure du projet et outillage.
- **Concepts liés** : [exporter.md](exporter.md) — acquisition du dump ; [modules.md](modules.md) — place du testeur parmi les modules ; [solvabilite.md](solvabilite.md) — invariants et rejoueur ; [graphe-interactif.md](graphe-interactif.md) — graphe de production ; [witness.md](witness.md) — déterminisme de l'assemblage.
