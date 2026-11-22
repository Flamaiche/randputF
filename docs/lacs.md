# Les lacs de fluide

Retour : [docs/README.md](README.md).

Un lac est une nappe de fluide créée pendant la partie. La seed choisit les fluides et enregistre une richesse ; elle ne place aucune tuile. Le mod colore les tuiles d'eau au moment où les chunks apparaissent.

## Ce que ça change pour le joueur

- Une pompe offshore posée sur un lac fournit le fluide tiré, en volume illimité.
- La pompe offshore n'a pas besoin d'électricité.
- Un même fluide n'est jamais à la fois un lac et un gisement de fluide.

## Mots à connaître

- **Lac** : tuile de fluide pompée avec une pompe offshore. Voir le [glossaire](glossaire.md#monde-généré).
- **Richesse** : valeur enregistrée dans la seed et affichée en chat ; elle ne fixe pas la taille du lac.
- **Tuile fantôme** : tuile d'eau neutre que le mod remplace pendant la partie.
- **Flood-fill** : propagation du remplissage de tuile en tuile dans un chunk.

## Règles de génération

### Tirage de la seed

1. Le nombre de lacs est tiré entre 1 et 3 avec les réglages par défaut.
2. Chaque lac reçoit un fluide pipable, au plus un par fluide, et une richesse tirée entre 100000 et 600000.
3. La seed ne garde que le fluide et la richesse. Elle n'enregistre ni position ni rayon. La richesse sert d'information de difficulté et apparaît dans le message chat ; elle ne décrit ni la taille ni la densité de la nappe.

### Prototypes et données publiées

4. Le mod neutralise l'eau vanilla et dépose une tuile fantôme à sa place.
5. Chaque fluide tiré reçoit une tuile colorée. La couleur passe par `effect_color` et `map_color` ; `variants[].tint` reste réservé à la tuile fantôme blanche.
6. Une table de secours ne couvre que quelques fluides. Les autres gardent la couleur de base du fluide, ramenée dans une palette claire.

### Remplissage au runtime

7. Le mod parcourt les tuiles fantômes de chaque chunk et remplit les nappes connexes par flood-fill.
8. Le fluide vient d'une tuile voisine déjà colorée, sinon du tourniquet des fluides de la seed. Les nappes se prolongent ainsi entre chunks.
9. Le remplacement laisse le moteur recalculer les berges.

### Purge des cartes legacy

10. Les cartes anciennes gardent de l'eau vanilla. Le mod la remplace par la tuile de terre dominante, sans toucher aux tuiles des lacs tirés.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Au plus un lac par fluide. | Une taille ou une densité liée à la richesse. |
| Une pompe offshore amorçable sans courant. | Une couleur de secours pour chaque fluide. |

## Aller plus loin

- [ressources.md](ressources.md) — à lire quand on veut comparer lacs et gisements de fluide.
- [ressources-brutes.md](ressources-brutes.md) — à lire quand on cherche l'extracteur d'une ressource fluide.
- [starter.md](starter.md#la-phase-de-démarrage) — à lire quand on vérifie le kit fourni au départ.
- [config.md](config.md) — à lire quand on veut changer le nombre de lacs ou les bornes de richesse.

## Lectures associées

- **Parent** : [ressources.md](ressources.md) — les ressources au sol.
- [ressources-brutes.md](ressources-brutes.md#les-formes-dune-ressource-brute) — catalogue des formes et des extracteurs.
- [starter.md](starter.md#la-phase-de-démarrage) — kit de départ et extracteurs amorcés.
- [energie.md](energie.md) — énergie `void` des pompes offshore.
- [config.md](config.md) — bornes `lakes.min`, `lakes.max` et `lakes.richness_fluid`.
