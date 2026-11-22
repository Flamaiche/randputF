# Les ressources brutes et leur extraction

Retour : [docs/README.md](README.md).

Une ressource brute vient directement du monde, sans recette préalable. randputF distingue trois formes : le gisement d'item, le gisement de fluide et le lac. Chaque forme a son support, son extracteur et son milieu.

## Ce que ça change pour le joueur

- Un gisement d'item se mine avec une foreuse, un gisement de fluide se pompe avec une foreuse à fluide, un lac se pompe avec une pompe offshore.
- La pompe offshore fonctionne sans courant, contrairement à la pompe à fluide classique.
- Le kit fournit une unité de chaque extracteur retenu pour la chaîne initiale.

## Mots à connaître

- **Ressource brute** : élément obtenu dans le monde, sans craft. Voir le [glossaire](glossaire.md#monde-généré).
- **Patch** : gisement posé sur la carte. Voir le [glossaire](glossaire.md#monde-généré).
- **Lac** : tuile de fluide créée pendant la partie. Voir le [glossaire](glossaire.md#monde-généré).
- **Milieu** : sol, dépôt ou lac ; il détermine la famille d'extracteurs.

## Règles de génération

### Les formes d'une ressource brute

1. Le gisement d'item est une entité minière au sol, exploitée par un extracteur de milieu `ground` sans sortie fluide. Son énergie est à combustible ou électrique.
2. Le gisement de fluide est une entité de dépôt exploitée par une foreuse `basic-fluid`, de préférence non électrique. La foreuse classique du jeu reste électrique.
3. Le lac est une tuile exploitée par une pompe offshore, sans besoin d'électricité.
4. Les extracteurs sont choisis d'après le milieu et les catégories du dump, jamais d'après le nom de la ressource.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Un extracteur adapté à chaque forme tirée. | La présence d'une ressource précise au sol. |
| Une seule amorce par nom d'extracteur retenu. | Un extracteur non électrique pour les gisements de fluide. |

## Aller plus loin

- [ressources.md](ressources.md) — à lire quand il faut savoir comment les gisements sont posés et dimensionnés.
- [lacs.md](lacs.md) — à lire quand la seed tire des nappes de fluide.
- [starter.md](starter.md#la-phase-de-démarrage) — à lire quand on cherche ce que contient le kit initial.
- [energie.md](energie.md) — à lire quand on veut comprendre l'énergie `void` des pompes offshore.

## Lectures associées

- **Parent** : [ressources.md](ressources.md) — les ressources au sol.
- [lacs.md](lacs.md) — la génération des lacs.
- [starter.md](starter.md#la-phase-de-démarrage) — la phase de démarrage.
- [model.md](model.md) — terminologie et classification des bâtiments.
