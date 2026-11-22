# L'amorçage du run

Retour : [docs/README.md](README.md).

L'amorçage couvre le début de la partie : le joueur doit pouvoir fabriquer les premières machines sans attendre une technologie lointaine. randputF prépare ce chemin pendant la génération, puis le corrige à plusieurs reprises. Les règles décrites ici sont partagées par les ressources, les recettes, l'énergie et l'arbre technologique.

## Ce que ça change pour le joueur

- Les premières recettes n'exigent pas d'atelier électrique.
- Une ressource devenue nécessaire est obtenable immédiatement, même si elle n'était pas prévue au départ.
- Les recherches qui suivent le starter se débloquent par craft manuel.

## Mots à connaître

- **Bootstrap** : ensemble des premières recettes fabriquables avant le réseau électrique. Voir le [glossaire](glossaire.md#génération).
- **Contrôle précoce** : contrôle du graphe initial, avant toute correction. Voir [solvabilite.md](solvabilite.md).
- **Recette orpheline** : recette de bâtiment créée sans être rattachée à une technologie.
- **Déclencheur de craft** : item à fabriquer à la main pour ouvrir une technologie.

## Règles de génération

### Les règles d'amorçage

1. Le premier générateur et le premier pylône sont forcés au craft manuel. Les autres recettes du starter restent réalisables dans un atelier non électrique.
2. Quand une recette demande une ressource absente, la seed crée son extraction, son craft intermédiaire ou son combustible sur le tas.
3. Les ateliers débloqués pendant cette opération sont rattachés à la technologie en cours. Leurs recettes sont ajoutées par ordre alphabétique, et non dans l'ordre de déblocage.
4. Les techs gratuites portent un coût nul. Les techs `randputf-prologue-*` et `randputf-ease-*` viennent ensuite : chacune se débloque par le craft manuel d'un item du bootstrap.
5. Les pools de déclencheurs des ease-up reprennent les candidats du starter, en excluant ceux déjà utilisés par les prologues.
6. L'oracle early vérifie le graphe au moment de sa création. La passe `enforce_usage` s'applique deux fois, avant et après `apply_extractor_timing`, qui peut régénérer des recettes d'extracteur une fois le graphe assemblé.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Un chemin de craft avant l'électricité pour le générateur et le pylône. | L'absence de tout avertissement résiduel de la passe d'usage. |
| Un rattachement des bâtiments débloqués sur le tas. | L'ordre de déblocage des recettes de bâtiments. |

## Aller plus loin

- [starter.md](starter.md#la-chaîne-initiale-starter) — à lire quand on veut le détail de la chaîne initiale.
- [recettes.md](recettes.md) — à lire quand on suit la génération récursive.
- [energie.md](energie.md) — à lire quand on cherche la règle du générateur et du pylône.
- [tech.md](tech.md) — à lire quand on veut voir où ces techs se placent dans l'arbre.

## Lectures associées

- **Parent** : [starter.md](starter.md) — la phase de démarrage.
- [recettes.md](recettes.md) — la phase récursive.
- [ressources.md](ressources.md#les-ressources-au-sol-1) — les ressources au sol ; [lacs.md](lacs.md) — la génération des lacs.
- [energie.md](energie.md) — électricité et chaleur.
- [tech.md](tech.md) — arbre technologique et fin de partie.
