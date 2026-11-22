# Runtime Lua : ce que le mod fait de la seed

Retour : [docs/README.md](README.md).

Le mod Lua applique la seed dans Factorio. Trois fichiers agissent avant la partie. Le quatrième agit pendant la partie. Le cinquième appartient au mod compagnon d'export.

## Ce que ça change pour le joueur

- Les recettes et technologies vanilla sont neutralisées au chargement des données.
- Les patchs, les lacs et le kit de départ sont posés pendant la partie.
- Le dump modifié par le mod est accepté par l'outil Python.

## Mots à connaître

- [data-stage](glossaire.md) — phase de chargement des prototypes, sans accès au monde.
- [runtime](glossaire.md) — phase où le mod agit sur une partie en cours.
- [autoplace](glossaire.md) — mécanisme Factorio qui place les ressources sur la carte.
- [flood-fill](glossaire.md) — propagation de tuile depuis une tuile fantôme.
- [seed.lua](glossaire.md) — miroir Lua de la seed, lu directement par le mod.

## Fonctionnement

### Comment lire ce document

1. `data.lua` crée les recettes et les technologies depuis la seed.
2. `data-updates.lua` prépare les ressources, les lacs et les armes de véhicules.
3. `data-final-fixes.lua` neutralise le contenu vanilla après tous les mods.
4. `control.lua` applique la seed au monde pendant la partie.
5. `exporter/control.lua` produit le dump repris par l'outil Python.

Les trois premières étapes sont de la data-stage. La quatrième est le runtime. La cinquième n'appartient pas à la chaîne de génération.

### Chaîne de vérité

| Forme | Producteur | Consommateur |
|---|---|---|
| `seed.json` | pipeline Python | validation, partage et rapports |
| `seed.lua` | export Python | les quatre fichiers Lua du mod |
| `mod-data` | data-stage | runtime, exporter et parseur Python |

Le mapping tuile à fluide des lacs vit dans `mod-data`. Le runtime ne le reconstruit qu'en repli. L'outil Python le lit depuis le dump.

## Les cinq fichiers Lua

| Fichier | Moment | Rôle principal |
|---|---|---|
| `mod/data.lua` | data-stage | recettes, technologies, icônes et sous-groupes |
| `mod/data-updates.lua` | data-stage | entités de ressources, lacs, fluides et armement des véhicules |
| `mod/data-final-fixes.lua` | data-stage | neutralisation vanilla, autoplace et rochers |
| `mod/control.lua` | runtime | kit, lacs, patchs, épaves et événements joueur |
| `exporter/control.lua` | partie d'export | écriture du dump vanilla ou moddé |

Les quatre fichiers du mod chargent `seed.seed` avec `pcall`. Une seed absente laisse une table vide, sans arrêter Factorio.

### Ce que fait la data-stage

1. `mod/data.lua` étend `data.raw` avec les recettes et technologies préfixées.
2. `mod/data-updates.lua` clone les ressources et arme les véhicules selon la seed.
3. `mod/data-final-fixes.lua` désactive les recettes et technologies vanilla non exemptées.
4. La chaîne de fusée reste exemptée pour conserver la victoire possible.
5. Les contrôles d'autoplace vanilla passent en taille nulle. Les ressources randputF prennent le relais.
6. Le charbon des rochers devient de la pierre, pour ne pas court-circuiter les patchs.

La neutralisation vise toutes les recettes et technologies vanilla non préfixées. Les protections venaient de listes courtes ; le comportement courant repose sur le préfixe `randputf-`.

### Ce que fait le runtime

| Événement | Action |
|---|---|
| `on_configuration_changed` | neutralise le kit freeplay |
| `on_init` | range la seed, débloque les recherches gratuites, traite les épaves |
| `on_load` | ne modifie rien, car le monde n'est pas disponible |
| `on_player_created` | affiche le récapitulatif et dépose le kit complet |
| `on_player_respawned` | dépose un kit mince après le premier spawn |
| `on_tick` | applique le kit, purge l'eau, balaie les épaves |
| `on_surface_created` | traite les conteneurs de crash de la nouvelle surface |
| construction d'une pompe offshore | force la couleur du lac sous la pompe |
| `on_chunk_generated` | remplit les lacs et pose les patchs du chunk |

Les patchs item deviennent infinis après la pose d'une foreuse. Les patchs fluide exigent un pumpjack. Les lacs exigent une pompe offshore.

## Catégories de combustible unifiées

Le runtime n'impose plus de catégorie de combustible par climatiseur. Les catégories vanilla restent interchangeables pour les bâtiments concernés. Les combustibles disponibles viennent du dump et des recettes générées.

Cette unification évite deux machines incompatibles pour un même rôle thermique. Elle ne supprime pas les résidus de combustion, qui restent déduits du dump. Le détail des tags figure dans [tags.md](tags.md).

### Dumps moddés

L'ancien garde-fou `EXPORT REFUSE` a été retiré de `exporter/control.lua`. Un dump produit avec randputF actif est donc accepté. La canonisation à la lecture remplace le refus. Les recettes préfixées actives sont choisies quand elles existent. Les artefacts à double préfixe sont ignorés.

### Écart connu

D'anciens documents décrivaient des garde-fous et des lignes de code précises dans ce fichier. Ces descriptions ne reflètent plus le code courant. Reste à faire : les remplacer par les rôles de fichiers et les événements décrits ci-dessus.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les quatre fichiers du mod lisent le même `seed.lua`. | Les événements Lua peuvent changer avec la version de Factorio. |
| Les patches sont posés au chargement des chunks. | Les mods tiers modifient le comportement du monde. |
| Les dumps moddés sont acceptés puis canonisés. | Un dump moddé peut produire une seed différente. |

## Aller plus loin

- [architecture.md](architecture.md) — à lire quand il faut situer le mod dans le projet.
- [pipeline.md](pipeline.md) — à lire quand la construction de la seed importe.
- [exporter.md](exporter.md) — à lire quand le dump doit être régénéré.
- [lacs.md](lacs.md) — à lire quand le remplissage des lacs est étudié.
- [DEVIANCES.md](DEVIANCES.md) — à lire quand un écart de gameplay est observé.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [vanilladb.md](vanilladb.md) — base construite depuis le dump.
- [tags.md](tags.md) — classement des bâtiments par capacité.
- [etat-code.md](etat-code.md) — état courant des composants.
