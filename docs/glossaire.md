# Glossaire randputF

Retour : [docs/README.md](README.md).

Ce glossaire définit les mots utilisés dans la documentation. Les définitions
décrivent leur rôle dans randputF, pas seulement leur sens général.

## Notions de base

| Terme | Définition |
|---|---|
| seed | Graine numérique qui fixe tous les tirages d'une partie. Une même seed produit le même monde. |
| dump vanilla | Photographie des prototypes du jeu de base, produite par l'exporteur Factorio et lue par l'outil Python. |
| prototype | Définition d'un objet du jeu : item, fluide, machine, technologie ou recette. |
| randput | Remplacement du contenu d'une entrée ou d'une sortie par un autre élément du même type. |
| mod | Ensemble de fichiers Lua et de données installé dans Factorio pour modifier le jeu. |
| runtime | Partie du mod qui s'exécute pendant la partie. |
| data-stage | Partie du mod qui s'exécute au chargement des données, avant le début de la partie. |
| vanilla | Contenu du jeu de base, sans randputF ni mod tiers. |
| dump | Fichier exporté depuis Factorio ; le dump vanilla en est la référence. |
| graphe | Structure qui relie recettes, items et technologies. |
| pipeline | Suite ordonnée d'étapes qui transforment le dump et la seed en mod. |
| artefact | Fichier généré, non suivi dans git. |
| promotion | Passage d'une branche de travail vers la branche destinée à la publication. |
| note de release | Fichier de version qui porte le titre et les points saillants d'une release. |
| dérive | Changement involontaire d'une sortie considérée comme stable. |
| divergence assumée | Écart volontaire par rapport au jeu de base. |
| tag | Propriété calculée à partir d'une capacité du dump. |
| cycle | Dépendance circulaire entre recettes ou entre technologies. |
| Graphviz | Outil externe utilisé pour dessiner le graphe SVG. |

## Monde généré

| Terme | Définition |
|---|---|
| patch | Gisement posé sur la carte. Un patch d'item se mine ; un patch de fluide se pompe avec une pumpjack. |
| lac | Tuile de fluide créée au runtime et pompée avec une pompe offshore. |
| ressource brute | Élément de départ obtenu dans le monde, sans recette préalable. |
| item | Objet transportable sur tapis ou dans un inventaire. |
| fluide | Substance transportable en tuyau. |
| science pack | Objet consommé par un laboratoire pour rechercher une technologie. |
| lab | Bâtiment vanilla de recherche, utilisé pour consommer les science packs. |
| atelier | Bâtiment qui fabrique un objet ou transforme une ressource. |
| slot | Emplacement d'entrée ou de sortie d'un bâtiment ou d'une recette. |
| recette | Règle de fabrication : ingrédients, atelier et produit. |
| extracteur | Bâtiment qui prélève une ressource du monde. |
| rôle | Fonction assignée à un élément par ses tags. |
| seed.lua | Fichier Lua du mod qui transmet la seed au runtime. |
| autoplace | Règle du jeu qui décide où une tuile ou une ressource apparaît sur la carte. |
| flood-fill | Propagation déterministe qui attribue une même valeur à une zone contiguë. |

## Génération

| Terme | Définition |
|---|---|
| pool | Ensemble fini de candidats parmi lesquels la seed tire un élément. |
| RNG | Générateur aléatoire contrôlé par la seed. Tous les tirages passent par lui. |
| jalon | Étape de la chronologie de génération qui garantit une catégorie de contenu. |
| tier | Niveau de profondeur d'un élément dans l'arbre de fabrication. |
| bootstrap | Phase initiale qui rend le premier générateur, le premier pylône et les premières recettes fabriquables. |
| déblocage sur le tas | Création immédiate d'une méthode d'obtention quand une ressource devient nécessaire. |
| compagnon | Élément lié à un autre parce que l'un sans l'autre serait inutilisable. |
| force-fill | Remplacement déterministe d'un tirage vase par un contenu utilisable. |

## Vérification

| Terme | Définition |
|---|---|
| validateur | Contrôle qui vérifie une propriété de la seed ou du pipeline. |
| invariant | Propriété qui doit rester vraie à chaque génération. |
| rejeu | Simulation de la progression du joueur à partir de la seed, sans interface Factorio. |
| fake player | Rejoueur Python qui tente de reproduire les actions d'un joueur réel. |
| témoin | Empreinte du mod assemblé, utilisée pour détecter toute dérive de déterminisme. |
| canonisation | Normalisation d'un dump moddé à la lecture, sans rejet du dump. |
| rapport HTML | Vue générée du graphe, de la complexité ou de la difficulté d'une seed. |
| solvabilité | Propriété d'une seed dont le parcours reste possible jusqu'à la victoire. |
| blocker | Motif d'arrêt de la progression avant la victoire. |

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [model.md](model.md) — classification des bâtiments.
- [solvabilite.md](solvabilite.md) — garanties vérifiées à la génération.
