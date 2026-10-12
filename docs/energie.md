# L'électricité

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## L'électricité

L'électricité est un **type à part**. Dans Factorio elle constitue un réseau
propre (ni item ni fluide) : elle ne sera donc pas « randputisée » en tant que
ressource. Ce qui se randomise, c'est tout ce qui l'entoure :

- **Déclenchement à la demande** : si un bâtiment tiré a besoin d'électricité
  dès le début, alors le réseau électrique est débloqué au début. Sinon, tout
  arrive au fur et à mesure des besoins.
- **Générateurs** : tout ce qui peut produire de l'électricité est dans le
  même cas. Si un besoin électrique apparaît, un générateur est choisi
  aléatoirement, puis le besoin de ce bâtiment entraîne la suite, décidée
  *après* que tout le reste est posé.
  Un accumulateur (ou toute entité de stockage) **n'est pas un générateur** :
  il ne produit pas d'énergie. Sa classification l'écarte du tirage des
  générateurs pour ne pas « résoudre » l'électricité par une simple batterie
  (classement [model.md](model.md#le-modèle-randput--classification-des-bâtiments)).
- **Unlock du générateur** : les recettes créées pour l'électricité
  (générateur lui-même, combustible) sont **réintégrées aux techs du starter**
  après la phase — jamais une recette orpheline sans tech pour la débloquer.
- **Amorçage à la main (anti-boucle)** : le **premier** générateur électrique
  de la seed — qu'il vienne de la phase électricité ou d'un tirage récursif
  post-starter — a une recette **craftable à la main** : ingrédients 100%
  solides, aucune catégorie ni atelier. Un assembling-machine-2 ou une usine
  chimique exigeraient l'électricité que ce générateur doit justement amorcer
  (bootstrap impossible sinon). Les générateurs suivants retombent sur des
  ateliers normaux. Ces recettes de bootstrap **doublent le coût de leurs
  ingrédients non infinis** (bois/pierre/poisson, [recettes.md](recettes.md#relais-des-ressources-non-infinies)) — le début de run se
  joue à la main sur des ressources rares.
- **Ingrédients du générateur sans électricité** : en plus du handcraft, les
  **ingrédients** du premier générateur ne doivent pas eux-mêmes être produits
  par un **bâtiment électrique** — sans quoi il faudrait déjà l'électricité
  qu'il amorce pour les fabriquer (même boucle). Le tirage des ingrédients
  **bannit** donc tout item dont la production passe par un atelier électrique ;
  ne restent que ceux obtenables sans réseau : ressource brute (patch minerais),
  kit, environnement, ou recette dans un atelier non-électrique/à la main.
- **Générateur à vapeur = fluide combustible en entrée (pas l'eau)** : un
  steam-engine / steam-turbine (générateur à vapeur) prend **un fluide** en
  entrée — n'importe quel fluide pipable, pas spécifiquement l'eau ([starter.md](starter.md#la-chaîne-initiale-starter)). En
  vanilla un générateur produit de l'électricité à partir de la **température**
  du fluide : un fluide froid sorti d'une nappe afficherait « ~0 W ». Le mod
  bascule donc les générateurs en mode **combustible** (`burns_fluid`) et donne
  à **tous** les fluides un `fuel_value` générique (200 kJ/unité, [ressources.md](ressources.md#les-ressources-au-sol) fires
  arbitrary) : tout fluide est brûlé comme carburant. Il est **amorçable
  (fonctionnel)** si et seulement si la seed tire au moins **un LAC** (fluide
  extractible sans électricité via la pompe offshore) : une ressource oil posée
  en **patch** exigerait un pumpjack électrique → boucle fuel→électricité ([energie.md](energie.md#lélectricité)).
- **Aucun bâtiment figé sur steam/water ([ressources.md](ressources.md#les-ressources-au-sol))**: dans l'univers randputF un
  fluide n'a pas d'identité fixe. Le vanilla câble pourtant en dur certains
  bâtiments sur un fluide précis via le `filter` de leurs fluid boxes
  (steam-turbine/steam-engine → `steam` ; boiler/heat-exchanger → `water` en
  entrée). Le mod retire **génériquement** (aucune liste codée en dur) le
  `filter` de **toute** fluid box : la turbine/le moteur acceptent ainsi
  **n'importe quel fluide** (l'UI ne dit plus « steam »), et le boiler/chaudière
  traitent un **fluide d'entrée → fluide de sortie** arbitraires. La règle
  s'applique automatiquement aux bâtiments qu'un mod ajoutera.
- **Résolution robuste** : on ne décide pas a priori quel générateur
  « doit » marcher. `resolve_electricity` **shuffle** les générateurs et les
  **teste un par un** jusqu'à en trouver un fonctionnel (vapeur ⇒ un lac ;
  burner/solaire ⇒ toujours). Si **aucun** n'est fonctionnel, on **force un
  patch réparateur** (item OU lac fluide, ressource ≠ du type précédent) pour
  changer le pool obtenable, puis on **re-shuffle** et on revérifie. Après
  **20 essais** (et si aucun patch réparateur n'est disponible), on lève une
  **erreur explicite** — jamais une seed silencieusement cassée. La carte est
  donc **toujours réparée par ajout** ; les lacs/patches forcés sont fusionnés
  dans la seed ([seed.md](seed.md#seed-et-configuration)).
- **Pylônes (poteaux électriques)** : la distribution du courant entre le
  générateur et les bâtiments est indispensable — sans poteau, l'électricité
  produite ne transporte rien de jouable. Dès qu'un besoin électrique apparaît,
  un **bâtiment de distribution** (poteau) est aussi débloqué avec sa recette,
  dans la même phase (réintégrée aux techs du starter). Le pôle d'amorçage est
  **craftable à la main** comme le générateur : son atelier exigerait
  l'électricité que le poteau est censé transporter (même anti-boucle [energie.md](energie.md#lélectricité)).
- **Combustible du générateur** :
  - si le bâtiment a besoin d'un combustible item, on lui **assigne** un item
    comme combustible ;
  - s'il a besoin d'un fluide, on lui en prend un **disponible** dans le pool ;
  - s'il n'existe aucune ressource disponible compatible, on **crée une
    recette et tout ce qui va avec** (même logique de déblocage sur le tas
    que [recettes.md](recettes.md#relais-des-ressources-non-infinies)).

Exemple d'enchaînement cohérent : turbine tirée → son fluide d'entrée est
décidé à sa création → ce fluide provient soit d'un patch existant, soit d'un
transformateur (type chaudière) alimenté par un combustible assigné ou créé.

## La chaleur

La chaleur est un **second milieu** à part, décrit avec ses tags et sa garantie
de triade dans [chaleur.md](chaleur.md#la-chaleur).

## Lectures associées

- **Parent** : [docs/README.md](README.md)
- **Enfants** : [chaleur.md](chaleur.md) — le milieu chaleur (source / transport / sink)
- **Concepts liés** : [ressources.md](ressources.md#les-ressources-au-sol) (fluid boxes / identity) ;
  [tags.md](model.md#types-fonctionnels) et (classification générateur / stockage / chaleur) ;
  [runtime.md](runtime.md#catégories-de-combustible-unifiées) (fuel categories unifiées, fluides génériques) ;
  [recettes.md](recettes.md#relais-des-ressources-non-infinies) (relais, déblocage sur le tas) ;
  [seed.md](seed.md#seed-et-configuration) (fusion des patches réparateurs).
