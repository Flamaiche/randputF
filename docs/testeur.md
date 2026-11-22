# Testeur de dump — contrôle, rejeu et trois vues HTML

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Le testeur (`tool/tester.py`) vérifie un état de jeu déjà acquis et produit ses statistiques. Il ne tire aucune graine et n'assemble aucun mod : la graine appartient uniquement à la création d'un mod avec `randputf generate`.

## Entrées

| Entrée | Commande | Origine de l'état testé |
|---|---|---|
| Dump fixe | `randputf test --dump <fichier.json>` | état normalisé directement depuis le dump |
| Mod existant | `randputf test --dump <fichier.json> --mod-dir <dossier>` | état déjà assemblé lu depuis `seed/seed.json` |

Dans les deux cas, le dump fourni reste la source de vérité pour l'identité, les noms et les trois pages HTML. Le nom canonique du dossier et des fichiers vient de `meta.mod_label` pour les dumps 0.1.8+, sinon du nom du fichier ; les HTML vont toujours dans `output/reports/<nom>/`.

## Les cinq étapes

| Étape | Fonction | Rôle |
|---|---|---|
| `acquisition` | `json.loads` / `build_vanilla_seed()` | lit le dump et normalise les faits disponibles |
| `controle` | `validate_seed()` | détecte cycles, invariants violés et déblocages incohérents |
| `rejeu` | `play()` | simule une partie « vrai joueur » depuis les faits du dump |
| `mesure` | `write_full_report()` / `compute_difficulty()` | calcule complexité, profil multi-axes, difficulté et partie simulée |
| `rapport` | `run_dump_test()` | écrit les trois HTML préfixés par le nom canonique de la source |

Ces noms sont exposés dans `tool.tester.STAGES` et servent de référence commune à la CLI, aux tests et à cette documentation. `tool.tester.STAGE_LABELS` donne les libellés affichés par la barre de progression : « Acquisition du dump », « Contrôle de l'état », « Rejeu joueur », « Mesure de la difficulté » et « Rapport HTML ».

La CLI `randputf test` affiche cette progression en Python pur, sans dépendance : nom de l'étape, barre, pourcentage de l'étape courante, numéro de l'étape sur le total, action en cours, temps écoulé en secondes et fin estimée de l'étape. Sur un terminal, la ligne est rafraîchie sur place ; sinon chaque changement d'étape produit une ligne. L'ETA par pourcentage est recalculée au changement de pourcentage puis maintenue ; elle ne grandit pas avec le seul temps écoulé. Le rejeu fournit une ETA propre depuis `techs recherchées/total`. Le dépliage affiche `i/N techs · E étapes` et estime la fin après la première
 technologie terminée, depuis le coût moyen des techs récentes et le débit d'étapes ; avant cela, ou pour les phases sans total connu, il affiche `fin étape —`. Le dépliage précise aussi `profondeur P/64 · dernier → chemin → item · Q unités`, avec les trois derniers ancêtres de la branche de recettes en cours. Cette position change à chaque rafraîchissement, mais ne modifie pas le calcul.

```text
Rejeu joueur [████████░░░░░░░░░░░░]  40% 3/5 — partie simulée · 78/196 techs · 3.2s · fin étape ~5s
```

La CLI accepte des `--no-...` pour omettre une partie du travail : `--no-checks` (validation et rejeu), `--no-complexity`, `--no-difficulty` et `--no-playthrough` pour le calcul, `--no-cache` pour ignorer la simulation persistée, puis `--no-report-html`, `--no-dump-html`, `--no-graph-html` ou `--no-html` pour les sorties. La partie simulée longue est désactivée par défaut sur `test` et `report` : `--playthrough` l'active quand le détail de la partie est nécessaire. Par défaut, la complexité et le profil partagent un unique calcul de graphe mémoïsé (`tool/audit/graph.py`) à partir des recettes et stats du dump, sans rejouer la partie. Quand `--playthrough` est actif, la complexité réutilise les compteurs de la simulation et le résultat est enregistré dans le dump sous `randputf_cache.playthrough_v1` avec une empreinte de la seed, du dump et de la version de l'outil : une commande suivante le réutilise sans relancer la simulation. Les sections omises ne sont pas écrites dans le rapport et les contrôles ignorés ne font plus échouer la commande.

Le rapport contient aussi un **profil de difficulté multi-axes** calculé par `tool/audit/profile.py` : structure du graphe, volume de production, temps critique, nouveauté et infrastructure. Chaque axe est la moyenne géométrique des rapports de ses indicateurs, normalisés contre la baseline vanilla quand elle est disponible (`1,00` = même difficulté) ; l'indice global applique les poids 25/20/20/20/15. Les volumes et temps sont estimés linéairement puis comparés en `log10(1 + valeur)` : leur valeur brute reste affichée dans le tableau, mais l'indice ne explode pas quand un cycle moddé multiplie les quantités. Cette mesure compare des parties sans prétendre prédire un temps de jeu réel. Les valeurs du bandeau complexité, des classements ateliers/ressources et du tableau du profil portent leur ratio `×N` contre vanilla, affiché directement à côté de la valeur ; pour les volumes et temps du profil, le ratio reste logarithmique et la valeur brute est conservée. Le coût unitaire de chaque objet est mémoïsé une seule fois : la complexité n'est plus un dépliage récursif par chemin, donc les scores de complexité peuvent différer de ceux de l'ancien modèle exact. Le tableau des indicateurs est dans `#profil-difficulte-table`, omis avec `--no-difficulty`.

Le rejeu ne suit pas un ordre linéaire :
 à chaque passe, il cherche toutes les techs dont les prérequis sont satisfaits et dont le coût est abordable, en recherche une, puis recalcule la fermeture. Un blocage n'est donc signalé que si aucune tech disponible ne peut être financée. C'est indispensable aux arbres moddés où une tech tardive dans l'ordre topologique peut être le prochain déblocage utile.

Un échec de contrôle ou de rejeu n'est pas masqué : il est affiché en console et écrit dans la section `#controles` du rapport. La commande sort avec le code 2, sans relancer de génération ni essayer une autre valeur.

## Trois pages HTML

Pour un dump `vanilla_dump.json` identifié `vanilla` :

```text
output/reports/vanilla/vanilla.dump.html     navigateur du dump
output/reports/vanilla/vanilla.graph.html    graphe de production
output/reports/vanilla/vanilla.report.html   contrôles + complexité + profil + difficulté (+ partie simulée avec --playthrough)
```

Le dossier porte le nom canonique du dump (`meta.mod_label`, sinon le nom du fichier), ou le nom du dossier du mod avec `--mod-dir`. Les noms `randputF-<version>` sont normalisés en `randputF_<version>` pour que le dossier du mod et celui du rapport concordent. Quand `--mod-dir` fournit un état déjà assemblé, la baseline de comparaison reste le dump vanilla par défaut (`data/vanilla_dump.json`), pas le dump d'entrée : le profil et la courbe de difficulté comparent donc bien le modpack au vanilla.

Au-delà de 10 000 recettes, le rapport passe en vue réduite : résumé, contrôles, couverture, profil et difficulté sont conservés ; les courbes de complexité et la partie simulée détaillée sont omises. Les grands graphes utilisent `sfdp` au lieu de `dot` pour éviter les erreurs mémoire ; si Graphviz ne peut pas rendre le SVG, la page graphe contient une vue textuelle des technologies et recettes.

Les ancres stables du rapport sont décrites par `tool.tester.SECTIONS` : `controles`, `couverture-dump`, `profil-difficulte`, `complexite-courbes`, `difficulte`, `partie-simulee`.

La section `#couverture-dump` classe les champs réellement présents dans le dump en quatre états : consommé, partiel, à consommer et cosmétique. La CLI affiche les mêmes totaux avant les problèmes de contrôle, par exemple :

```text
Couverture : Consommé 45 · Partiel 9 · À consommer 0 · Cosmétique 54
```

## Commandes

```bash
randputf test --dump data/vanilla_dump.json
randputf test --dump /chemin/au/dump.json --out output/reports/
randputf test --dump /chemin/au/dump.json --mod-dir output/mods/randputF_0.0.1/
```

Aucune de ces commandes ne génère de mod. Les options `--seed` et `--seed-file` de l'ancien flux n'existent plus sur `test`.

## Lectures associées

- **Parent** : [architecture.md](architecture.md) — structure du projet et outillage.
- **Concepts liés** : [exporter.md](exporter.md) — acquisition du dump ; [modules.md](modules.md) — place du testeur parmi les modules ; [solvabilite.md](solvabilite.md) — invariants et rejoueur ; [graphe-interactif.md](graphe-interactif.md) — graphe de production ; [witness.md](witness.md) — déterminisme de l'assemblage.
