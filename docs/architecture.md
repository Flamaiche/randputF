# Architecture du projet

Retour : [docs/README.md](README.md).

randputF sépare la génération, le mod Factorio et les rapports. Python prépare la seed. Le mod Lua l'applique pendant la partie.

## Ce que ça change pour l'utilisateur

- L'outil Python assemble le mod avant le lancement de Factorio.
- Le mod lit la seed au chargement des données, puis pendant la partie.
- Les rapports HTML restent hors du mod installé.

## Mots à connaître

- [seed](glossaire.md) — graine qui fixe tous les tirages.
- [dump vanilla](glossaire.md) — photographie des prototypes du jeu.
- [data-stage](glossaire.md) — phase de chargement des données, avant la partie.
- [runtime](glossaire.md) — phase où le mod agit pendant la partie.
- [mod](glossaire.md) — ensemble de fichiers Lua installé dans Factorio.

## Fonctionnement

### Architecture générale

| Bloc | Rôle | Fichiers principaux |
|---|---|---|
| Outil Python | lit le dump, tire la seed, valide, écrit les sorties | `tool/`, `config/`, `data/` |
| Mod Factorio | construit recettes et technologies, puis agit en jeu | `mod/data.lua`, `mod/data-updates.lua`, `mod/data-final-fixes.lua`, `mod/control.lua` |
| Rapports | décrivent le graphe, la complexité et la difficulté | `tool/exporters/`, `output/reports/` |

La version cible est Factorio 2.1. Les versions 2.0 appartiennent aux tags historiques `v0.0.0` et `v0.0.1`.

### Structure du projet

| Dossier ou fichier | Rôle |
|---|---|
| `config/defaults.yaml` | réglages par défaut, source unique |
| `config/user.yaml` | surcharges locales |
| `data/vanilla_dump.json` | dump des prototypes utilisé par l'outil |
| `tool/common/` | base normalisée, configuration, RNG, tags |
| `tool/parsers/` | lecture et canonisation du dump |
| `tool/generator/` | phases de génération de la seed |
| `tool/prototypes/` | objets de configuration des phases |
| `tool/validator/` | contrôles structurels et solvabilité |
| `tool/audit/` | tags, difficulté, profils |
| `tool/exporters/` | seed du mod et vues HTML |
| `tool/replay/` | rejoueur qui simule une partie |
| `mod/` | source Lua du mod assemblé |
| `exporter/` | mod compagnon qui produit le dump |
| `tests/`, `tools/` | suite de tests et scripts de développement |
| `output/` | mods assemblés et rapports générés |

Le dépôt ne suit aucun artefact généré. Les détails d'exécution sont dans [pipeline.md](pipeline.md) et les rôles de modules dans [modules.md](modules.md).

### Le passage de la seed au jeu

1. Les fichiers YAML sont fusionnés puis validés.
2. Le dump est lu et transformé en base normalisée.
3. Les phases de génération produisent un dictionnaire de seed.
4. Le validateur structurel journalise ses observations.
5. Le solver vérifie la solvabilité ; `generate` peut relancer avec une graine dérivée.
6. `seed.json`, `seed.lua` et les fichiers Lua sont assemblés dans le mod.
7. Les vues HTML disponibles sont écrites dans `output/reports/randputF_<version>/`.
8. Le mod lit `seed.lua` sans lire `seed.json`.

`generate --no-html` supprime toutes les écritures HTML.
 Les options de rapport sont décrites dans [graphe-interactif.md](graphe-interactif.md).

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une même seed et un même dump donnent le même mod. | La structure interne des dossiers peut évoluer. |
| Les rapports ne font pas partie du mod Lua. | Les modules non branchés n'influencent aucune seed. |
| Factorio 2.1 reste la cible courante. | Les mods tiers ne sont pas pris en charge. |

## Aller plus loin

- [pipeline.md](pipeline.md) — à lire quand l'ordre des étapes de génération importe.
- [modules.md](modules.md) — à lire quand il faut savoir quel module agit sur une seed.
- [config.md](config.md) — à lire quand un réglage doit être modifié.
- [runtime.md](runtime.md) — à lire quand il faut suivre la seed dans le jeu.
- [release.md](release.md) — à lire quand une version doit être publiée.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [developpement.md](developpement.md) — environnement de développement.
- [etat-code.md](etat-code.md) — état courant des composants.
- [exporter.md](exporter.md) — acquisition du dump vanilla.
