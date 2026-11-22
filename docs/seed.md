# Seed et configuration

Retour : [docs/README.md](README.md).

Une seed est la graine numérique qui fixe tous les tirages d'une partie. Cette
page décrit la valeur retenue, la configuration lue et les fichiers écrits. Les
faits anciens et les corrections demandées sont séparés des garanties actuelles.

## État de la page

- Garantie actuelle : un même dump, la même configuration et la même graine
  produisent la même seed.
- Implémentation actuelle : seule la clé `paths.factorio_mods` est consommée
  parmi les clés de `paths`.
- Fait historique : d'anciens textes annonçaient un hash sha256 dans
  `seed.lua` ; ce champ n'existe pas.
- Spécification historique : elle ne demande pas de changement de fond
  pour cette page ; elle reste concise et à jour.

## Ce que ça change pour le joueur

- Sans option, l'heure sert de graine et la valeur s'affiche dans la console.
- Avec `--seed`, la même partie est reproductible.
- Les rapports HTML n'empêchent pas la génération du mod.

## Mots à connaître

- [Seed](glossaire.md) — graine qui fixe les tirages.
- [Dump vanilla](glossaire.md) — photographie des prototypes du jeu.
- [Pool](glossaire.md) — ensemble fini de candidats au tirage.
- [Témoin](glossaire.md) — empreinte du mod assemblé.
- [Rapport HTML](glossaire.md) — vue générée du graphe ou du profil.

## Seed et configuration

- Sans `--seed`, l'outil lit l'horloge en millisecondes.
- `--seed` fixe la valeur ; la graine alimente les générateurs aléatoires.
- Aucune borne supérieure n'est imposée à la valeur numérique.
- `validate_seed` juge la solvabilité, pas la taille de la graine.
- `generate_with_retry` essaie la valeur demandée, puis les suivantes, jusqu'à
  dix tentatives.

<a id="seed-et-configuration-1"></a>

## Configuration lue et données exportées

- `config/defaults.yaml` porte les valeurs par défaut.
- `config/user.yaml` porte les surcharges, fusionnées puis validées.
- `paths.factorio_mods` est la seule clé de `paths` utilisée ; `mod_dir` et
  `vanilla_dump` sont inertes.
- Les autres sections sont décrites dans [config.md](config.md).
- La seed exporte recettes, technologies, ressources, jalons tardifs et
  métadonnées ; `seed.lua` n'a pas de champ sha256.

## Règles de génération

- Les tirages passent par des flux dérivés de la graine.
- Les ensembles sont triés avant d'alimenter un tirage.
- Les rapports vont dans `output/reports/randputF_<version>/`.
- `--no-html` supprime l'écriture des trois vues.
- Sans Graphviz, le graphe est omis ; sans technologies dans le dump, la
  difficulté est omise.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Le même triplet produit le même mod, octet pour octet. | Un hash sha256 dans `seed.lua`. |
| La reprise essaie au plus dix graines. | Toute valeur demandée est conservée. |
| Les vues HTML sont régénérables. | Le graphe et la difficulté sont toujours écrits. |

## Aller plus loin

- [nondeterminism.md](nondeterminism.md) — à lire pour les contrôles de
  reproductibilité.
- [witness.md](witness.md) — à lire pour le md5 canonique du mod.
- [config.md](config.md) — à lire pour les clés et les valeurs.
- [graphe-interactif.md](graphe-interactif.md) — à lire pour les trois vues HTML.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [pipeline.md](pipeline.md) — à lire pour l'ordre des phases.
- [testeur.md](testeur.md) — à lire pour contrôler une seed existante.
