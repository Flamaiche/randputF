# Configuration

Retour : [docs/README.md](README.md).

randputF lit ses réglages dans deux fichiers YAML. Les valeurs par défaut vivent au même endroit. Les surcharges locales sont validées avant chaque génération.

## Ce que ça change pour l'utilisateur

- Les réglages se modifient dans `config/user.yaml`, sans toucher aux défauts.
- Une clé inconnue ou une valeur impossible provoque une erreur explicite.
- Modifier un défaut change l'espace des seeds et le témoin de déterminisme.

## Mots à connaître

- [seed](glossaire.md) — graine qui fixe tous les tirages.
- [pool](glossaire.md) — ensemble de candidats utilisé par un tirage.
- [validateur](glossaire.md) — contrôle appliqué à la configuration.
- [jalon](glossaire.md) — étape garantie par la génération.

## Fonctionnement

### Les deux fichiers

| Fichier | Rôle | Modifiable |
|---|---|---|
| `config/defaults.yaml` | source unique des valeurs par défaut | non |
| `config/user.yaml` | surcharges locales | oui |

Les deux fichiers sont fusionnés en profondeur. Le moteur lit ensuite chaque valeur par un accès typé. Il ne fabrique aucune valeur de secours.

### La validation

Le chemin CLI utilise `runtime_config`, qui refuse les sections inconnues. Le pipeline appelle `full_config` avec `strict_sections=False`. Les clés racine hors schéma sont alors tolérées pour les outils d'analyse, mais les sections connues restent validées.

Les types, les bornes, les contraintes `min <= max` et les contraintes croisées sont contrôlés. Une erreur arrête la commande.

### Les sections utiles

| Section | Rôle principal |
|---|---|
| `factorio_version` | clé documentaire inerte ; la version effective vient de `mod/info.json` |
| `paths` | dossiers du mod, du dump et de Factorio |
| `map` | nombre de gisements, rayons, richesses, puits |
| `starter` | kit de départ et champ interne `deferred` |
| `recipes` | poids, durées et équilibre des recettes |
| `recursive` | poids des catégories et limites de la récursion |
| `tree` | coûts et déblocages des technologies |
| `relay`, `easeup` | recettes de secours et prologues |
| `usage` | garantie d'utilisation des bâtiments |
| `wreck`, `lakes` | butin du site de crash et lacs |
| `late_raws`, `nonfinite`, `craft_quantity` | sections conditionnelles |
| `pools`, `weights` | réservées, sans effet courant |

Le champ `starter.deferred` est interne au pipeline. Il ne doit pas être renseigné dans `config/user.yaml`.

### Ce qui reste hors du YAML

Quelques constantes de structure restent dans le code. C'est le cas du miroir Lua et Python des formes de gisements et des invariants de solvabilité. Le chemin du dossier mods se règle avec `paths.factorio_mods`.

### Écart connu

Certains textes plus anciens présentaient les sections `pools` et `weights` comme actives. Elles sont lues et validées, mais sans effet sur le moteur. Reste à faire : retirer ces mentions des notes historiques.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une configuration fusionnée contient toutes les clés lues par le moteur. | Les sections réservées ne produisent aucun effet. |
| `defaults.yaml` reste la source unique des valeurs algorithmiques. | Une surcharge locale peut rendre une seed non jouable. |
| Les sections conditionnelles ne s'activent que si `enabled` est vrai. | Le témoin n'est pas conservé après un changement de défaut. |

## Aller plus loin

- [modules.md](modules.md) — à lire quand le module qui lit une clé est recherché.
- [pipeline.md](pipeline.md) — à lire quand l'ordre d'application des réglages importe.
- [seed.md](seed.md) — à lire quand la configuration sérialisée doit être consultée.
- [exporter.md](exporter.md) — à lire quand le chemin du dump doit être changé.
- [witness.md](witness.md) — à lire quand un changement de défaut est vérifié.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [architecture.md](architecture.md) — place des fichiers YAML dans le projet.
- [graphe-interactif.md](graphe-interactif.md) — profils calculés à partir des réglages.
- [nondeterminism.md](nondeterminism.md) — impact des changements de valeurs.
