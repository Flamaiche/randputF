# Tags de bâtiment et d'item

Retour : [docs/README.md](README.md).

La base normalisée classe chaque prototype avec des tags cumulables. Un bâtiment peut porter plusieurs rôles à la fois. Le générateur utilise ces tags, complétés par les ensembles figés centralisés dans `tool/common/tagsets.py`.

## Ce que ça change pour l'utilisateur

- Un bâtiment peut être à la fois atelier et producteur d'énergie.
- Le classement vient des capacités du dump, complétées par les ensembles figés de `tool/common/tagsets.py`.
- Les rôles de transport sont choisis par le bâtiment posé par un item.

## Mots à connaître

- [tag](glossaire.md) — propriété calculée à partir d'une capacité.
- [prototype](glossaire.md) — définition d'un objet du jeu.
- [rôle](glossaire.md) — usage d'un bâtiment dans le graphe.
- [vanilla](glossaire.md) — contenu du jeu de base, sans mod.

## Fonctionnement

### Rôles fonctionnels

| Tag | Rôle |
|---|---|
| `is_research` | consomme des packs de science |
| `is_crafter` | transforme des entrées en sortie de craft |
| `is_generator` | produit courant ou chaleur |
| `is_distribution` | distribue courant ou effets |
| `is_extractor` | prélève une ressource du monde |
| `is_other` | aucune capacité reconnue |

`PRODUCING_TAGS` regroupe les quatre premiers rôles. Les rôles distribution et other ne produisent rien. `equivalent_functional_type` reconstruit l'ancienne classification exclusive pour vérification.

### Raffinements courants

| Tag | Signal utilisé |
|---|---|
| `is_power_pole` | type poteau électrique |
| `is_accumulator` | type accumulateur |
| `is_energy_storage` | `buffer_capacity` positif, avec repli sur l'accumulateur |
| `is_offgrid` | production sans réseau |
| `consumes_electricity` | courant consommé sans production ni stockage |
| `is_lake_extractor` | extracteur de médium lac |
| `is_deposit_extractor` | extracteur de gisement fluide |
| `is_ground_extractor` | extracteur de minerai solide |

## Logistique & transport (raffinement des `is_other`)

Les tags de transport viennent du type de prototype. Le kit de départ résout chaque rôle vers le bâtiment posé par l'item correspondant. Les motifs de noms ont été supprimés.

| Rôle | Tag |
|---|---|
| courroie | `is_belt` |
| répartiteur | `is_splitter` |
| courroie souterraine | `is_underground_belt` |
| inserteur | `is_inserter` |
| tuyau | `is_pipe` |
| tuyau souterrain | `is_pipe_to_ground` |
| transport fluide | `is_fluid_transport` |
| stockage | `is_storage` |

## Énergie & chaleur (raffinement d'`is_generator`)

La chaleur suit une triade. Une source produit la chaleur. Un transport l'emmène. Un consommateur la transforme.

### Modèle « chaleur » (producteur / transport / consommateur)

| Tag | Rôle |
|---|---|
| `is_heat_source` | source de chaleur, réacteur ou producteur burner |
| `is_heat_transport` | conduite de chaleur |
| `is_heat_sink` | consommateur de chaleur |

La triade est tentée quand un consommateur reçoit sa recette fluide à fluide. Quand elle est posée, la source et le transport sont placés dans des technologies strictement antérieures. Sans consommateur dans le pool, le modèle reste inerte. Une erreur de composition est interceptée sans rejeter la seed.

`produces_heat` est réservé à la source. Le réacteur n'est pas un producteur de courant. L'accumulateur n'est pas un producteur, malgré sa puissance de décharge.

### Écart connu

D'anciens textes indiquaient que `buffer_capacity` n'était pas exporté. Le champ est désormais exporté par `exporter/control.lua`, lu par `tool/parsers/vanilla.py` et conservé sur `BuildingDef`. Reste à faire : retirer l'ancienne formulation de repli des commentaires et des notes historiques.

## Extraction et fabricateurs à recette fixe

`is_pumpjack` vient des catégories de ressources fluides. `is_offshore_pump` vient du médium lac. `pumped_fluid` est résolu côté Python depuis la version 0.1.5 de l'exporteur.

Les bâtiments à recette cachée reçoivent une transformation randomisée. C'est le cas des chaudières et des échangeurs thermiques. Les résidus de combustible restent déduits du dump.

## Tags items

| Tag | Signal utilisé |
|---|---|
| `is_environmental` | ensemble figé des matières récoltées à la main |
| `is_virtual_item` | type de contrôle sans bâtiment posé |
| `is_science_pack` | coûts de technologies et entrées de laboratoire |
| `is_mounted_gun` | arme listée dans `entity.guns` |
| `is_handheld_gun` | arme non montée |
| `is_stackable` | taille de pile supérieure à un |

Un item environnemental ou virtuel n'est produit par aucune recette vanilla. Un dump moddé peut exposer d'autres liens ; l'audit les classe alors en information.

## Ensembles dérivés en dur (résiduels)

Les listes figées vivent dans `tool/common/tagsets.py`. Elles servent de source unique aux modules qui les importent. Elles restent nécessaires quand le dump n'expose pas encore le signal correspondant.

| Ensemble | Rôle |
|---|---|
| `ENVIRONMENTAL_ITEMS` | matières premières environnementales |
| `NON_STACKABLE_ITEM_TYPES` | repli pour les items non empilables |
| `VEHICLE_GUNS` | repli pour les armes montées vanilla |
| `ROCKET_CHAIN` | chaîne de victoire |
| `VALID_RECIPE_CATEGORIES` | catégories de craft reconnues |
| `RAIL_TYPES` | types de rails |
| `VIRTUAL_ITEM_TYPES` | types d'items de contrôle |
| `FLUID_RECIPE_CATEGORIES` | catégories de recettes fluides |
| `STARTER_TRANSFORMERS` | transformations du départ |
| `EXCLUDED_BUILDINGS` | bâtiments écartés |
| `ENDGAME_EXCLUDED` | bâtiments écartés de la fin de partie |

`ARMED_VEHICLES` reste une constante de test. Les anciennes listes de poteaux et de motifs de transport ont été supprimées au profit des tags.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les tags sont calculés depuis les capacités du dump. | Les mods tiers peuvent exposer des capacités nouvelles. |
| Les rôles sont cumulables sans ambiguïté. | Les ensembles résiduels restent nécessaires. |
| L'audit contrôle les invariants de classement. | Un dump moddé peut produire des informations supplémentaires. |

## Aller plus loin

- [vanilladb.md](vanilladb.md) — à lire quand l'origine d'un tag est cherchée.
- [energie.md](energie.md) — à lire quand la triade thermique est étudiée.
- [model.md](model.md) — à lire quand le vocabulaire du modèle est nécessaire.
- [DEVIANCES.md](DEVIANCES.md) — à lire quand un écart de classement est observé.
- [testeur.md](testeur.md) — à lire quand l'audit doit être rejoué.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [exporter.md](exporter.md) — faits bruts du dump.
- [runtime.md](runtime.md) — usage des tags pendant la partie.
- [etat-code.md](etat-code.md) — composants d'audit.
