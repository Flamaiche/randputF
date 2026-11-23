# Les ressources au sol

Retour : [docs/README.md](README.md).

<a name="les-ressources-au-sol-1"></a>

La seed remplace les repères du spawn par des gisements tirés au hasard. Leur nombre, leur ressource, leur richesse et leur forme changent à chaque partie. Le mod pose ces gisements pendant la partie ; le générateur de carte n'en dessine aucun.

## Ce que ça change pour le joueur

- Le nombre total de gisements est tiré une fois, entre 3 et 8 avec les réglages par défaut.
- Une ressource n'apparaît qu'une seule fois sur la carte, en gisement ou en lac.
- Aucune ressource précise n'est garantie : tout dépend du tirage. Les moyens d'extraction liés au tirage le sont.

## Mots à connaître

- **Patch** : gisement posé sur la carte, d'item ou de fluide. Voir le [glossaire](glossaire.md#monde-généré).
- **Richesse** : quantité totale d'un gisement, ou rendement d'un puits fluide.
- **Puits** : point de pompage d'un gisement de fluide.
- **Lac** : nappe de fluide tirée avant les gisements. Voir [lacs.md](lacs.md).

## Règles de génération

### Pools et exclusions

1. Le pool d'items part des objets transportables sur tapis. Le code écarte les objets de combat et les armes, les objets environnementaux ou virtuels, les bâtiments de recherche, la chaîne de fusée et le silo, ainsi que les science packs.
2. Le pool de fluides part des fluides transportables en tuyau. Les fluides déjà tirés comme lacs en sont retirés.
3. Le tirage est sans remise : une ressource tirée ne revient pas dans le pool.

### Écart connu

La spécification historique demande de n'exclure que les science packs.
 Le code courant exclut aussi les catégories listées au point 1 ; cette intention n'est pas appliquée.

### Composition de la carte

4. Un seul tirage fixe la composition : 15 % d'items seuls, 15 % de fluides seuls et 70 % de mélange avec les réglages par défaut. Le chiffre de 70 % suppose au moins deux gisements. Si la configuration réduit le tirage à un seul gisement, la branche dite mixte donne un item et zéro fluide.
5. La richesse est tirée entre 400000 et 1500000 pour un item, et entre 100000 et 600000 pour un fluide.
6. Si un pool est vide, la composition bascule vers l'autre type.

### Pose au runtime

7. Chaque gisement reçoit un centre, un rayon, un compte et une graine locale. Les prototypes ont un `autoplace` à densité nulle.
8. Au chargement d'un chunk, le mod crée les entités et applique la richesse. Une tuile occupée est ignorée ; les autres positions sont conservées.

### Réparation par ajout de ressource

9. Si aucun générateur ne fonctionne, la résolution électrique peut ajouter un lac ou un item encore absent de la carte. Après 20 tentatives sans succès, la génération échoue.

### Géométrie : item versus fluide

10. Un fluide garde quelques puits éparpillés ; la richesse s'applique à chaque puits.
11. Un item forme un disque bruité ; la richesse totale est répartie sur les tuiles réellement posées.
12. La randomisation non-finie est désactivée par défaut. Quand elle est active, elle module la richesse et le rayon sans changer l'identité du gisement.

### Identité des fluides : la température n'est pas un critère

13. Un fluide est identifié par son nom. Deux températures du même fluide comptent comme une seule ressource.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Un tirage sans doublon, lacs compris. | Une ressource précise au sol. |
| Une pose déterministe, indépendante de l'ordre des chunks. | Un mélange item/fluide quand un seul gisement est tiré. |

## Aller plus loin

- [ressources-brutes.md](ressources-brutes.md) — à lire quand on veut connaître l'extracteur de chaque forme.
- [lacs.md](lacs.md) — à lire quand on cherche la troisième forme de ressource brute.
- [config.md](config.md) — à lire quand on veut changer les bornes de tirage.
- [energie.md](energie.md) — à lire quand la résolution électrique ajoute une ressource.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [ressources-brutes.md](ressources-brutes.md) — catalogue des formes et des extracteurs.
- [lacs.md](lacs.md) — source unique de la génération des lacs.
- [starter.md](starter.md#la-phase-de-démarrage) — kit de départ et extracteurs amorcés.
- [config.md](config.md) — bornes et valeurs par défaut.
