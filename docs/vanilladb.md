# VanillaDB

Retour : [docs/README.md](README.md).

VanillaDB est la base interne construite à partir du dump. Elle rassemble les prototypes du jeu, leurs capacités et les pools utilisés par la génération. Le dump contient des prototypes et quelques champs dérivés par l'exporteur.

## Ce que ça change pour l'utilisateur

- Un dump vanilla ou moddé peut être lu sans être rejeté.
- Les pools de ressources viennent des faits présents dans le dump.
- Un dump modifié est canonisé à la lecture, puis utilisé tel quel.

## Mots à connaître

- [dump vanilla](glossaire.md) — photographie des prototypes du jeu.
- [prototype](glossaire.md) — définition d'un item, fluide, bâtiment ou technologie.
- [pool](glossaire.md) — ensemble fini de candidats pour un tirage.
- [canonisation](glossaire.md) — normalisation d'un dump moddé à la lecture.
- [tag](tags.md) — propriété calculée à partir des capacités d'un prototype.

## Fonctionnement

### Les trois couches

| Couche | Rôle |
|---|---|
| `exporter/control.lua` | écrit les faits bruts dans le dump |
| `tool/parsers/vanilla.py` | normalise le dump et calcule les tags |
| `tool/common/db.py` | déclare `VanillaDB` et expose les pools |

`load_db_from_dump` est appelé par le service et par les outils de rapport. La version du dump est décrite dans [exporter.md](exporter.md).

### Ce que contient le dump

| Section | Usage |
|---|---|
| `meta` | version du jeu, schéma, version de l'exporteur, identité du dump |
| `items`, `fluids` | objets solides et fluides transportables |
| `entities` | bâtiments, leurs entrées, sorties et sources d'énergie |
| `recipes` | ingrédients, produits, catégorie, état activé ou caché |
| `technologies` | coûts, prérequis et effets de recherche |
| `tiles` | couches de collision et fluides associés |
| `inventory` | inventaire A à Z des prototypes |
| `mod_data` | données de mods, dont le mapping des lacs |

Les faits dérivés comme les packs de science et la chaîne de fusée sont calculés côté Python. Ils ne sont pas des champs du dump.

### Les inférences importantes

1. `inject_pumped_fluids` résout le fluide pompé par les extracteurs de lac.
2. `science_pack_names` réunit les coûts de techs et les entrées de laboratoire.
3. `rocket_chain_from_dump` déduit la chaîne de victoire des prototypes.
4. `tag_parse_entity` classe les bâtiments par capacité, sans liste de noms.
5. Les prototypes préfixés `randputf-` vont dans des ensembles séparés, hors des pools.

### pumped_fluid / pumped_fluids (résolution Python depuis 0.1.5)

L'exporter ne porte plus le littéral `pumped_fluid`. La résolution se fait dans `tool/parsers/vanilla.py`.

1. Une source pure est reconnue par son absence d'entrée fluide. Sa sortie unique désigne le fluide pompé.
2. Sinon, les règles de placement de l'entité mènent à des tuiles. Un seul fluide distinct est accepté.
3. `mod_data` fournit le mapping des lacs quand plusieurs lacs partagent une tuile source.
4. Le fluide fantôme reste exclu des ressources.

### Tags énergétiques & chaleur

Les bâtiments sont classés par source d'énergie et par comportement thermique. Les tags de chaleur forment une triade : source, transport, consommateur. Le détail figure dans [tags.md](tags.md).

`is_energy_storage` utilise `buffer_capacity`, désormais exporté par `exporter/control.lua`, lu par `tool/parsers/vanilla.py` et conservé sur `BuildingDef`. L'accumulateur reste un repli quand la valeur est absente.

### Dumps moddés

Un dump produit avec randputF actif est accepté. Les recettes vanilla neutralisées gardent leurs liens. Une recette `randputf-X` active devient la recette canonique du produit `X`. Les artefacts à double préfixe sont ignorés. Le tool ne refuse plus un dump modifié.

### Écart connu

D'anciens commentaires et pages indiquaient que `buffer_capacity` n'était pas exporté. Le code exporte, lit et utilise cette valeur. Reste à faire : mettre à jour ces commentaires et retirer l'ancienne formulation de repli.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les pools sont dérivés des prototypes présents dans le dump. | Un dump moddé peut produire une seed différente du dump historique. |
| La chaîne de fusée est déduite des faits du dump. | Les listes de tuiles dépendent de la version du jeu. |
| Un dump modifié est canonisé, pas rejeté. | Les mods tiers sortent du périmètre annoncé. |

## Aller plus loin

- [exporter.md](exporter.md) — à lire quand le dump doit être régénéré.
- [tags.md](tags.md) — à lire quand une règle de classement est recherchée.
- [pipeline.md](pipeline.md) — à lire quand l'usage d'un pool doit être suivi.
- [runtime.md](runtime.md) — à lire quand l'origine d'une mutation de prototype est cherchée.
- [config.md](config.md) — à lire quand un réglage change un pool.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [architecture.md](architecture.md) — place de la base dans le projet.
- [model.md](model.md) — vocabulaire du modèle randput.
- [DEVIANCES.md](DEVIANCES.md) — écarts liés aux dumps et aux lacs.
