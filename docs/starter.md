# Démarrage et chaîne initiale

Retour : [docs/README.md](README.md).

Le mod remplace le kit freeplay au premier spawn. Il fournit de quoi extraire, fabriquer et transporter les ressources tirées. Les premières recherches sont gratuites ; les suivantes se débloquent par craft manuel.

## Ce que ça change pour le joueur

- Le kit contient une arme, ses munitions, un fabricateur et un exemplaire de chaque extracteur retenu.
- Un combustible est ajouté quand le fabricateur ou un extracteur fonctionne au combustible.
- Les techs `randputf-starter-extraction` et `randputf-starter-transformation` sont acquises dès l'initialisation.

## Mots à connaître

- **Bootstrap** : phase qui rend les premières recettes fabriquables. Voir le [glossaire](glossaire.md#génération).
- **Extracteur** : bâtiment qui prélève une ressource brute. Voir [ressources-brutes.md](ressources-brutes.md#les-formes-dune-ressource-brute).
- **Tech gratuite** : recherche sans coût, marquée comme faite au lancement.
- **Déblocage sur le tas** : création immédiate d'une méthode d'obtention quand une ressource manque. Voir le [glossaire](glossaire.md#génération).

## Règles de génération

### La phase de démarrage

1. L'arme est tirée au hasard ; les munitions suivent sa catégorie et leur quantité est plafonnée par la taille de pile.
2. La seed rend l'arme, les munitions, le fabricateur et les extracteurs refabriquables. Le kit ne donne qu'un stock initial.
3. Le site de crash reçoit des matériaux récoltables à la main, jamais des objets craftés.
4. Quand un lac est tiré, la pompe offshore et le remblai sont garantis dès le départ.

### La chaîne initiale (starter)

5. Un extracteur est retenu pour chaque ressource immédiatement nécessaire, d'après son milieu.
6. Un bâtiment de fabrication est choisi pour créer ou transformer une ressource.
7. Les transports sont débloqués pour les types extraits ; un inserter peut s'ajouter quand des items sont extraits.
8. Le lab fait partie du starter : sans lui, la recherche s'arrêterait après les techs gratuites.
9. Une ressource non automatisable sert d'appoint au début ; les produits qui en consomment reçoivent une recette relais.

### Contraintes de craft

10. Le premier générateur électrique et le premier pylône sont forcés au craft manuel. Les autres recettes du starter peuvent utiliser un atelier non électrique.
11. Les tuyaux et tapis doivent être fabriquables à partir d'une ressource déjà obtenable : c'est une intention de conception, pas une propriété vérifiée. Le champ `required_fluid` n'est pas utilisé pour choisir les extracteurs.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une arme, des munitions et un fabricateur au premier spawn. | L'absence de dépendance circulaire dans les recettes de transport. |
| Un lab et les recettes des extracteurs retenus. | Le même kit au retour en jeu : seul un kit mince est fourni. |

## Aller plus loin

- [amorcage.md](amorcage.md#les-règles-damorçage) — à lire quand on veut les règles communes de démarrage.
- [ressources.md](ressources.md) — à lire quand on cherche l'origine des ressources extraites.
- [lacs.md](lacs.md) — à lire quand la seed tire des nappes de fluide.
- [energie.md](energie.md) — à lire quand on veut comprendre le générateur et le pylône forcés au craft manuel.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [ressources.md](ressources.md#les-ressources-au-sol-1) — tirage et géométrie des patchs.
- [ressources-brutes.md](ressources-brutes.md#les-formes-dune-ressource-brute) — catalogue des formes et extracteurs.
- [lacs.md](lacs.md) — génération des lacs.
- [amorcage.md](amorcage.md#les-règles-damorçage) — règles transverses d'amorçage.
