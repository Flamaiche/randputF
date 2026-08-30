# randputF

**Randomizer total pour Factorio 2.0 (base, sans Space Age).**

randputF ne se contente pas de mélanger des recettes entre elles : il régénère
l'intégralité du jeu — ressources au sol, recettes (entrées *et* sorties),
bâtiments débloqués, arbre technologique, kit de départ — en garantissant à
chaque graine (*seed*) un parcours valide, sans boucle, du premier coup de pioche
au lancement de la fusée.

Ce document est la référence de conception du projet. Il décrit l'ensemble des
mécanismes du système, leur justification et les règles qu'ils doivent respecter.

---

## Table des matières

1. [Concept général](#1-concept-général)
2. [Périmètre et cible](#2-périmètre-et-cible)
3. [Terminologie](#3-terminologie)
4. [Architecture générale](#4-architecture-générale)
5. [Le modèle randput : classification des bâtiments](#5-le-modèle-randput--classification-des-bâtiments)
6. [Les ressources au sol](#6-les-ressources-au-sol)
7. [La phase de démarrage](#7-la-phase-de-démarrage)
8. [La chaîne initiale (starter)](#8-la-chaîne-initiale-starter)
9. [La phase récursive](#9-la-phase-récursive)
10. [L'électricité](#10-lélectricité)
11. [Combat et armement](#11-combat-et-armement)
12. [Transports avancés](#12-transports-avancés)
13. [L'arbre technologique](#13-larbre-technologique)
14. [Fin de partie](#14-fin-de-partie)
15. [Règles de solvabilité](#15-règles-de-solvabilité)
16. [Seed et configuration](#16-seed-et-configuration)
17. [Pipeline technique](#17-pipeline-technique)
18. [Structure du projet](#18-structure-du-projet)
19. [Roadmap](#19-roadmap)

---

## 1. Concept général

Un run classique de Factorio est appris par cœur : fer, cuivre, charbon,
pétrole ; les mêmes fours, les mêmes assembleurs, le même arbre de technologie.
randputF supprime toute connaissance préalable : **rien de ce que le joueur
connaît n'est garanti**.

À chaque partie, le randomizer :

- place au sol un nombre et des types de ressources tirés au hasard parmi
  **tout** ce que le jeu peut transporter (items sur tapis, fluides dans les
  tuyaux) ;
- choisit les bâtiments d'extraction, de transformation et de transport adaptés
  à ces ressources ;
- génère les recettes qui relient ces éléments entre eux ;
- distribue l'ensemble dans un arbre technologique lui-même généré ;
- fournit au joueur un kit de départ aléatoire.

Le principe central s'appelle le **randput** : la randomisation des entrées et
sorties. Un slot d'entrée ou de sortie déclaré pour un certain type (item ou
fluide) peut recevoir n'importe quel élément de ce type présent dans le jeu.
Un bâtiment capable de sortir un item peut donc sortir n'importe quel item ;
un bâtiment capable de manipuler des fluides peut manipuler n'importe quel
fluide. Le contenu change, la structure reste : c'est elle qui rend le monde
cohérent et jouable.

## 2. Périmètre et cible

| Élément | Décision |
|---|---|
| Version du jeu | **Factorio 2.0** |
| Contenu | **Base uniquement, sans Space Age** (pas de qualité, pas de planètes, pas de fondries/recycleurs) |
| Mods tiers | **Hors scope v1.** Le randomizer cible le jeu vanilla seul. Le support de contenu de mods tiers (Krastorio, Py, etc.) fera l'objet d'un projet séparé, bien plus tardif |
| Fin de partie | Classique : **lancement de la fusée** = victoire. Les technologies infinies restent disponibles ensuite, inchangées dans leur principe |

Ces choix sont volontairement conservateurs : verrouiller le périmètre sur le
vanilla permet de construire un moteur robuste avant d'envisager le parsing de
contenu arbitraire.

## 3. Terminologie

- **Randput** : contraction de *randomize input/output*. Mécanisme central :
  tout slot d'une recette typé « item » reçoit un item arbitraire, tout slot
  typé « fluide » reçoit un fluide arbitraire, parmi tous ceux existant dans
  le jeu.
- **Item beltable** : tout item pouvant circuler sur un tapis. Constitue le
  pool des candidats « ressource brute de type item ».
- **Fluide pipable** : tout fluide pouvant circuler dans un tuyau. Constitue
  le pool des candidats « ressource brute de type fluide ».
- **Ressource brute (raw)** : ressource extraite directement du sol — patch
  posé au sol (fini) ou fluide d'extraction (eau, pétrole brut, vapeur :
  « infinis » ou non). Seule elle alimente le début de la chaîne de production.
  **Un science pack ne peut jamais être crafté avec une ressource brute**
  (§13) : sa recette tire ses ingrédients parmi les intermédiaires craftés,
  invariant vérifié à la génération et par le validateur
  (`pools.raw_resources`, §16).
- **Ressource non automatisable** : entité récoltable à la main ou par
  interaction directe (arbres, poissons, …). Exclue du calcul des ressources
  durables (relais §9.5), mais réintroduite comme ingrédient possible dans les
  crafts ultérieurs — et, comme toute ressource brute, bannie des recettes de
  science packs (§13).
- **Recette relais** : pour un produit dont la recette générée consomme une
  ressource non automatisable, version **alternative du même produit** dont les
  ingrédients ne font appel qu'à des ressources durables — débloquée dans les
  3 premières techs (§9.5).
- **Ressource durable** : ressource infiniment disponible sur la durée du run
  (patch au sol, item fabriqué, fluide obtenu). Par opposition aux ressources
  non automatisables, qui s'épuisent.
- **Slot** : emplacement d'entrée ou de sortie d'un bâtiment ou d'une recette,
  caractérisé par son type (item, fluide, combustible, énergie).
- **Milieu** : environnement d'où un extracteur tire sa ressource (sol, eau,
  …). Deux extracteurs de milieux différents restent du même type : une pompe
  et une pompe offshore sont toutes les deux des extracteurs.
- **Directive** : possibilité déclarée d'un bâtiment — une capacité optionnelle
  qui distingue deux bâtiments d même type (voir §5).
- **Pool atteignable** : ensemble des choses que le joueur peut obtenir à un
  instant donné de la génération (ressources déjà posées, bâtiments déjà
  débloqués, crafts déjà validés).
- **Déblocage sur le tas** : mécanisme par lequel le randomizer crée, au
  moment même où il en a besoin, tout ce qui manque pour rendre une recette
  valide (extraction, craft, combustible…).
- **Graine / seed** : valeur déterministe pilotant tous les tirages du
  randomizer.

## 4. Architecture générale

Le système repose sur trois composants distincts :

```
┌─────────────────────┐      ┌──────────────────────────┐      ┌─────────────────┐
│   Tool externe      │      │   Mod Factorio           │      │  Runtime        │
│   Python            │ ───► │   data-stage             │ ───► │  control.lua    │
│                     │      │                          │      │                 │
│ • parse vanilla     │ YAML │ • lit config + seed      │      │ • placement des │
│ • génère le graphe  │ JSON │ • construit entités      │      │   patchs        │
│ • valide solvabilité│      │   ressources cachées     │      │ • déblocages    │
│ • écrit la seed     │      │ • construit recettes/    │      │   progressifs   │
│                     │      │   techs depuis la seed   │      │ • kit départ    │
└─────────────────────┘      └──────────────────────────┘      └─────────────────┘
```

### 4.1 Tool externe (Python)

La génération complète est effectuée **hors du jeu**, par un outil Python.
Raisons :

- Factorio ne permet **pas** de modifier les ingrédients d'une recette au
  runtime via l'API : tout doit être construit en *data-stage*. Le tool écrit
  donc les fichiers que le mod consommera à ce moment-là ;
- la **solvabilité** d'une seed (§15) est vérifiable hors du jeu, avant même
  de lancer Factorio — on refuse une seed injouable plutôt que de laisser le
  joueur tomber sur un blocage ;
- Python est choisi pour sa simplicité de développement et de débogage.

### 4.2 Formats de fichiers

- **YAML** pour les fichiers de configuration (lisibles, commentables) ;
- **JSON** pour les données générées consommées par le mod (seed, graphe,
  définitions de recettes/techs) ;
- d'autres formats pourront compléter si besoin.

### 4.3 Mod Factorio

En *data-stage*, le mod lit la configuration et la seed puis construit :

- une **entité ressource cachée** pour chaque item beltable et chaque fluide
  pipable candidat (des centaines), sans autoplace par défaut — elles ne
  seront placées que sur décision du runtime ;
- toutes les **recettes** générées ;
- tout l'**arbre technologique**.

Au runtime (*control.lua*), le mod :

- remplace les champs de ressources vanilles lors de la génération de la
  surface et place les entités ressources tirées par la seed ;
- gère les déblocages progressifs, le kit de départ, les recherches
  gratuites.

## 5. Le modèle randput : classification des bâtiments

C'est la fondation de tout le moteur. **Aucun bâtiment n'est traité comme
« bâtiment + ses recettes vanilles ».** Chaque bâtiment est défini par :

1. un **type** fonctionnel ;
2. des **slots** d'entrée/sortie **typés** ;
3. des **directives** : ses possibilités, ses capacités optionnelles.

Cette classification est lourde à construire mais c'est précisément sur elle
que repose le randomizer : c'est elle qui permet des combinaisons
« extraordinaires » tout en gardant un monde cohérent.

### 5.1 Types fonctionnels

| Type | Rôle | Exemples vanilles |
|---|---|---|
| Extracteur | Sort une ressource brute d'un milieu | perceuse, pompe offshore, tour de pompage |
| Transformateur | Convertit des entrées en sorties | fours, assembleurs, usine chimique, raffinerie, **chaudière** |
| Recherche | Convertit des science packs en technologie | **laboratoire** |
| Producteur d'énergie | Output spécial « énergie » | turbine, panneau solaire, réacteur |
| Consommateur d'énergie | Input spécial « énergie » | perceuse électrique, assembleur électrique… |
| Transport | Déplace items/fluides | tapis, splitters, undergrounds, tuyaux, pompes |
| Logistique | Manipule les objets sans flux continu | bras robotisés |

Points importants, volontairement soulignés car ils guident tout le modèle :

- **Il n'existe pas de chaîne figée.** Une pompe et une pompe offshore sont
  *toutes les deux* des extracteurs — simplement dans des milieux différents.
  Le moteur raisonne en types et milieux, jamais en objets précis.
- Une **chaudière** est un transformateur, similaire aux fours : elle prend
  des entrées (un fluide, un combustible) et produit une sortie (un autre
  fluide).
- Une **turbine** est un bâtiment électrique qui demande un fluide en entrée —
  et ce fluide est décidé **au moment où le bâtiment est créé** par le
  randomizer, pas avant.
- Un **laboratoire** n'est jamais un transformateur : détecté par sa capacité
  à consommer des science packs, il est classé dans le type dédié **recherche**
  et garanti dès le starter (§8) — il n'entre donc jamais dans le pool des
  ateliers de craft.

### 5.2 Slots typés

Chaque slot porte un type parmi :

- **item** (tout élément transportable sur tapis) ;
- **fluide** (tout élément transportable par tuyau) ;
- **combustible** (item ou fluide doté d'une valeur énergétique) ;
- **énergie** (cas particulier, voir §10).

### 5.3 Directives : les possibilités par tier

Les directives expriment ce qu'un bâtiment *peut faire*, indépendamment de ses
recettes vanilles. Elles créent des écarts de capacité entre tiers du même
type. Exemples canoniques :

- un **assembleur tier 1** n'accepte que des slots items ; un **assembleur
  tier 2** possède la capacité supplémentaire d'avoir une entrée fluide — une
  recette fluide peut donc lui être attribuée si la ressource sélectionnée en
  entrée est un fluide ;
- une **perceuse électrique** peut, dès le début du jeu, exiger un fluide pour
  fonctionner (directive « input auxiliaire »). Le moteur garantit alors que
  ce fluide est obtenable : les tuyaux qui le transportent peuvent être
  fabriqués **à partir de ce fluide lui-même**, ou d'une **autre ressource** —
  mais **jamais à partir de la ressource qui en a besoin** (règle anti-cycle,
  §8 et §15).

C'est cette matrice type × tier × directives qui remplace toute classification
manuelle figée.

## 6. Les ressources au sol

Au spawn, la carte est entièrement re-décidée :

- le nombre de patchs est aléatoire, dans une **fourchette de 3 à 8** ;
- chaque patch reçoit un type tiré au hasard parmi **tous** les candidats :
  - un item quelconque du pool « beltable », ou
  - un fluide quelconque du pool « pipable » ;
- le tirage est **sans remise** : une ressource apparaît au plus une fois sur
  la carte (jamais deux patchs de petroleum-gas, par exemple) ;
- il n'y a **aucune contrainte d'homogénéité** : certains patchs peuvent
  n'être que des fluides, d'autres que des items, ou un mélange des deux ;
  c'est totalement aléatoire ;
- l'abondance (richesse) des patchs est également variable ;
- les ressources **non automatisables** (arbres, poissons, etc.) sont
  **exclues** du calcul des ressources brutes : elles ne constituent jamais un
  patch. Elles demeurent **récoltables à la main dès le départ** (pool
  environnemental de base) et utilisables comme ingrédients, mais de manière
  **pondérée** :
  - quantité limitée et **petites** quantités demandées ;
  - **rarement** choisies (poids faible) tant qu'un item de production existe
    (patch item ou item déjà fabriqué) — elles apparaissent surtout dans les
    **tout premiers crafts** ;
  - en **priorité** uniquement quand la seed n'a **aucun** patch item : elles
    servent alors de matière première de démarrage, en particulier pour
    **fabriquer les extracteurs** (on débloque la fabrication du pumpjack / de
    la perceuse avant toute ressource au sol).
- les items « briques garanties » ne sont **jamais** des patchs : lab (§8),
  les 3 ingrédients de la fusée et le rocket-silo (§14). Ce sont des recettes
  générées et unlockées par une tech précise ; si un tel item tombait au sol,
  la recette garantie n'existerait pas et l'invariant d'endgame serait cassé.

Conséquence structurelle : plus aucune plaque de fer/cuivre/charbon ni gisement
de pétrole classique n'est garantie au sol — le joueur découvre à chaque
partie de quoi son monde est fait.

#### Identité des fluides : la température n'existe pas

Un fluide est défini uniquement par son **identité de ressource pipable** —
« tout ce qui peut circuler dans un tuyau ». Deux fluides portant le même nom
mais à des températures différentes sont **le même fluide** : pour randputF,
la température n'est pas une dimension, elle n'existe pas en tant que critère
de distinction.

Cette règle neutralise les cas ambigus du jeu (chaudière, réacteur nucléaire,
échangeurs de chaleur) : ces bâtiments **font une action** (chauffer,
transférer de la chaleur) mais leur chaleur n'est pas considérée comme une
transformation du fluide. Un fluide chauffé ou refroidi reste ce fluide ; seul
un changement de nom (eau → vapeur) constitue une autre ressource, et il passe
alors par une recette classique, jamais par un simple écart de température.

## 7. La phase de démarrage

Le randomizer détermine tout dès le spawn (l'électricité suivra sa propre
logique, §10) :

1. **Kit de départ randomisé** : le joueur ne commence pas forcément avec le
   même équipement. Son arme de départ est tirée au hasard, et **les munitions
   se calent sur l'arme** pour qu'il puisse effectivement l'utiliser.
2. **Techs gratuites du starter** : les premières recettes (la chaîne
   initiale, §8) sont débloquées par les techs du starter
   (`randputf-starter-*`), **gratuites** — coût nul, auto-complétées au
   runtime (free_researches). Elles se craftent avec **tout le pool du début**,
   ressources au sol ET ressources non-infinies (bois/pierre/poisson).
3. **Techs de prologue** (`randputf-prologue-*`) : juste après ces techs
   gratuites, les recettes **propres** des produits dont le bootstrap
   consommait des ressources non-infinies (§9.5) sont regroupées en techs de
   prologue de **≤ 5 unlocks chacune** (plafond §13, jamais une tech géante —
   une seule suffit s'il y a peu de recettes, aucune tech si aucune recette).
   Ce ne sont pas des
   free_researches : chaque prologue se débloque par **hand-craft** d'un item
   du bootstrap (§9.3) — façon vanilla (automation/logistics) : le joueur
   fabrique l'item déclencheur à la main et la tech s'active aussitôt. Le
   joueur sort vite de la dépendance au bois/pierre/poisson et débloque
   simultanément l'entrée en science avec
   le lab du starter.
4. **Site de crash randomisé** : les conteneurs `crash-site-*` du crash
   vanilla (munitions, plaques…) sont **vidés puis remplis aléatoirement**
   : chaque slot reçoit `n` copies d'un matériau aléatoire du pool de loot
   (`wreck.loot`, §16), avec `n ∈ {0, 1, 2, 3}` tiré selon une loi pondérée
   **strictement décroissante** (0 le plus fréquent → slot vide, 3 le plus
   rare) : `seed.wreck.counts = [c0, c1, c2, c3]` calculés par la formule
   générique `c3 = t`, `c2 = t + a`, `c1 = 100 − 5t − 2a`, `c0 = c1 + b`
   (exiger `6t + 3a < 100` et `b ≥ 1`), garantissant la somme des valeurs
   `0·c0 + 1·c1 + 2·c2 + 3·c3 = 100`. Défauts `(t,a,b) = (12, 9, 53)` →
   P(0) ≈ 57,7 %. Chaque conteneur n'est traité qu'une fois (loot préservé
   aux rechargements), le tirage est déterministe par seed (générateur
   indépendant `game.create_random_generator`). Le pool de loot se limite
   aux **ressources non-infinies** (bois, pierre, poisson) : ce sont les
   seules qu'on ne peut pas miner/automatiser, et on évite tout item crafté
   (plaques, fours…) dont la recette n'est pas garantie débloquée par
   l'arbre randomisé.
5. **Lacs de fluide** : 3e type de **raw ressource**, après les items et les
    fluides pumpjack (§6). Le mod **supprime toute l'eau vanilla de la carte**
    (océans, shallow…) puis ne génère QUE les lacs tirés par la seed
    (`seed.map.lakes = [{resource, richness}]`) : chaque lac est une tuile
    `randputf-lac-<fluid>` (copie de la tuile eau, **recolorée**) portant
    `fluid = <fluide tiré>` — une **pompe offshore vanilla** posée dessus
    débite ce fluide, **infini** comme l'eau. Richesse = taille du lac (volume
    illimité). Comptage `count ∈ [min, max]` (défaut 1, zéro possible via
    config) : un fluide non tiré n'a **aucun lac** (= indispo à l'extraction
    par lac), et si aucun lac n'est tiré la carte est sans eau. Placement
    généré par l'autoplace vanilla (`resource-autoplace`), proche du spawn
    quand la seed en tire un.
    **Neutralisation de l'eau vanilla** : forcer `autoplace.probability_expression = 0`
    sur les prototypes de tuiles d'eau ne suffit pas — le mapgen conserve des
    tuiles (mesuré : ~3 000 water/deepwater résiduelles sur la carte). La
    neutralisation réelle passe par l'override du mapgen de planète :
    `map_gen_settings.property_expression_names["tile:<eau>:probability"] =
    "<expression négative>"` (noise-expression `randputf-no-water`), appliqué
    à chaque tuile `water_tile_type_names` sur nauvis — résultat mesuré :
    **0 tuile d'eau vanilla**, les seules nappes étant les lacs tirés.
    **Couleur du lac** : chaque nappe conserve la *teinte* (hue) du fluide mais
    avec saturation/luminance relevées (`lake_color` : s=0.92, l=0.5) —
    visible au sol (`variants[].tint`) ET sur la carte (`map_color` 0-255) ;
    un simple `base_color` serait inutile (le crude-oil est noir → lac
    invisible sur la minimap). Fluides sans chromatisme : teinte de secours
    distincte par fluide (table `lake_fallback_hue` : crude-oil → brun huile
    orangé, steam → bleu clair, hydrogen → cyan…).
    **Bordures 1 lac sur 2** : la règle déterministe par seed
    `(seed_value + i) % 2 == 0` (i = index du lac dans `lake_list`) décide si
    un lac a une **berge** dessinée par les tuiles de terre voisines (sable /
    herbe : le mod ajoute les noms des lacs bordés aux `transitions[].to_tiles`
    de `grass-*` et `sand-*`, qui ciblent normalement l'eau vanilla) ou reste
    **net** (aucune transition, l'eau du lac borde directement la terre dure).
    Les berges sont donc entièrement générées par le mapgen, sans étendre de
    proto — vérifié sur carte réelle (ex : seed 5 → lac crude-oil bordé).
    **Purge runtime des cartes legacy** (`control.lua`) : les cartes créées
    avant le fix embarquent `property_expression_names` vide et conservent les
    tuiles d'eau vanilla du mapgen. Au premier chargement, `purge_chunk_water`
    remplace ces tuiles (`water`, `deepwater`, `water-shallow`, `water-green`,
    `deepwater-green`, `water-mud`, `water-wube`) par la tuile de terre
    dominante du chunk — balayage en carré croissant depuis le spawn, 32
    chunks/tick, curseur persisté dans `storage` (reprise après rechargement).
    Les lacs tirés par la seed sont préservés. Mesuré sur `testtest1`
    (139 546 tuiles) : purge complète en ~1 000 ticks sans impact perceptible
    sur l'UPS.

## 8. La chaîne initiale (starter)

Une fois les types de ressources brutes posés, le randomizer construit la
première boucle de production :

1. **Extraction** : un ou plusieurs bâtiments extracteurs sont choisis en
   fonction des ressources immédiatement à collecter — le milieu de chaque
   patch (sol / océan / fluide gazeux…) désigne la famille d'extracteurs
   possibles (perceuses pour le sol, pompes offshore pour l'eau, etc.).
2. **Transformation** : un bâtiment de fabrication est choisi pour créer ou
   transformer une ressource en une autre. Tout peut y passer : selon ses
   directives, il acceptera items, fluides ou les deux. Un assembleur tier 1
   refusera une recette fluide là où un assembleur tier 2 l'acceptera.
3. **Transport** : en fonction des besoins de ces quelques ressources de
   début, le joueur se voit débloquer tapis et tuyaux — randomisés, car il en
   existe plusieurs tiers — ainsi que les périphériques associés : splitters,
   tunnels/undergrounds côté tapis, équivalents côté tuyaux.
4. **Logistique** : des bras robotisés sont ajoutés si le besoin s'en fait
   sentir.

**Contrainte anti-cycle fondamentale** : si un bâtiment de cette phase exige
une entrée supplémentaire (le cas d'école : une perceuse électrique qui boit
un fluide dès le début), alors :

1. ce fluide doit pouvoir être obtenu ;
2. les tuyaux qui le transportent peuvent être fabriqués **à partir de ce
   fluide**, ou **d'une autre ressource** ;
3. mais **jamais à partir de la ressource qui en a besoin** — l'entrée
   auxiliaire provient toujours d'une branche déjà valide, indépendante du
   bâtiment qu'elle alimente.

**Extracteurs items-only** : la recette qui fabrique un extracteur (perceuse,
pumpjack, pompe offshore) n'utilise **jamais de fluide comme ingrédient** —
surtout pas celui qu'il sert justement à extraire. Dès le starter, ces
bâtiments se craftent uniquement avec des items, ce qui rend leur déblocage
possible avant même qu'aucune ressource au sol (et en particulier aucun
fluide) ne soit atteignable.

**Bootstrap non-infinies, puis relais** : au tout début, le joueur possède
*toutes* les ressources, y compris les non automatisables (arbres, rochers,
poissons). Ces dernières servent de matière première d'appoint du démarrage —
leur présence garantit un début de run qui marche, même pour les seeds sans
aucun patch item. Mais elles ne sont **pas tenables à long terme** : tout
produit dont la recette générée en consomme obtient une **recette relais**
(§9.5), débloquée dans les 3 premières techs.

**Le lab est une brique du starter — type « recherche »** : tout bâtiment
consommant des science packs (`lab_inputs`) est classé dans un type fonctionnel
dédié, `recherche` (§5.1), et non parmi les transformateurs : ce n'est pas un
atelier de craft, il n'a rien à faire dans le pool des recettes artisanales
(anti-cycle §8). Sans lab, la partie se fige dès les premières techs gratuites
consommées : le starter garantit donc par construction qu'un bâtiment de
recherche tombe dans la **2e recherche gratuite** (starter-transformation),
avec une recette craftée avec le pool de début.

**Un seul combustible — toutes catégories** : le mod redéfinit au data-stage la
catégorie de combustible de **chaque brûleur** pour qu'elle accepte *toutes* les
catégories du jeu (charbon, bois, combustible solide **et** cellules d'uranium,
etc.) — `mod/data-updates.lua`. La seed n'a donc **pas** à filtrer par
catégorie : le kit de départ glisse simplement le combustible à la plus grande
`fuel_value` du pool obtenu, et il est toujours utilisable quel que soit le
brûleur du kit (perceuse, chaudière, four, réacteur…). Sans ce patch, un kit
pouvait tirer une cellule d'uranium (catégorie « nuclear ») dans un
`burner-mining-drill` n'acceptant que « chemical » : inutilisable.

## 9. La phase récursive

Après le starter, la génération devient récursive. Le début aussi s'appuie
sur des pourcentages pour obtenir telle ou telle chose — mais ici ils sont
utilisés massivement et systématiquement :

### 9.1 Tirages pondérés

- Chaque catégorie (bâtiments, armes, science packs, transports avancés…)
  possède un **pourcentage d'obtention**.
- Ce pourcentage dépend du **type du bâtiment** et du **nombre total de
  bâtiments** déjà présents dans la partie.
- Plus on avance dans les recettes implémentées, plus il devient possible
  d'en débloquer davantage : le pool s'élargit avec la progression.

### 9.2 Génération des recettes

Les recettes restent simples dans leur forme :

1. regarder **tout ce que le joueur peut obtenir** (pool atteignable) ;
2. vérifier les **bâtiments** dont dispose le joueur (leurs types, slots et
   directives) ;
3. créer la recette à partir de choses prises **aléatoirement** dans ces
   ensembles compatibles.

### 9.3 Déblocage sur le tas

Puisque toutes les ressources sont plus ou moins déblocables :

- une recette peut d'un coup ajouter le besoin d'une ressource brute encore
  inconnue de la partie : le randomizer l'intègre immédiatement ;
- si une recette prend une ressource non automatisable, on débloque **au même
  moment** la façon de la créer/l'obtenir ;
- si quelque chose de plus est nécessaire pour débloquer cette ressource, cela
  est fait **sur le tas** : on choisit en fonction du type de la ressource
  demandée, et si elle n'est pas encore en possession du joueur, le craft
  correspondant est généré en même temps.

Le résultat : aucune impasse possible, mais aussi aucun chemin prévisible.

Les **déclencheurs hand-craft** des techs (prologue §13, et plus tard les
tirages aléatoires parmi les techs) obéissent à la même règle : l'item
demandé doit être **available AVANT** la tech qui le réclame. Bug classique à
éviter (et corrigé ici) : ne jamais tirer les candidats depuis une liste de
recettes **étendue après coup** par une phase postérieure — on prendrait des
items unlockés bien plus tard (four électrique, réacteur nucléaire, silo…),
et la tech resterait **bloquée pour toujours** (§9.3). Les candidats sont donc
calculés à partir des **seules recettes des techs gratuites du starter**
(disponibles au bootstrap), et chaque déclencheur est vérifié strictement
avant sa tech (voir `test_craft_trigger_prologue_craftable_des_le_starter`).
La quantité à hand-crafter n'est jamais un singleton trivial : chaque prologue
demande un **nombre d'items** (`research_trigger` `craft-item` avec `count`)
égal à **2^(n + indice_science/4)**, où `n` est tiré au hasard dans (1, 6]
(1 exclu, 6 inclu) et `indice_science` est la position de la science dans
l'ordre du tech tree (le prologue précède la chaîne des sciences : indice 1 ;
les bornes donnent donc 2^2.25 ≈ 5 à 2^6.25 ≈ 76 items). L'indice de science
rend le mécanisme directement réutilisable pour un tirage aléatoire parmi les
techs plus profondes : plus la science est avancée dans l'arbre, plus le
nombre d'items à fabriquer est grand.
Pour un tirage aléatoire parmi les techs en profondeur d'arbre, la même
contrainte s'applique : restreindre le pool aux items de recettes déjà
unlockées, jamais aux produits de recettes futures.

### 9.4 Cadence garantie des pylônes

La distribution du courant (§10) est vitale pour la progression : sans poteau,
un générateur ne transporte rien de jouable. Pour éviter le pire cas où le
premier pylône n'apparaît qu'en profondeur de l'arbre, on force une **cadence
de 3 pôles** pendant la phase récursive, indépendamment du hasard :

- **3 pôles verrouillés** (`dist_marks = (8, 28, 48)` par défaut) : un pôle tôt
  (dès ~8 steps récursifs), un deuxième ~20 steps plus loin, un troisième ~20
  encore après.
- Chaque pôle forcé tire un **type différent** (petit → moyen → grand /
  substation via `_pick_element`, jamais déjà déployé — donc pas de doublon).
- Si le starter a déjà débloqué un pylône **craftable** (électricité au
  bootstrap, §10), le premier jalon est **déjà satisfait** : on ne force rien
  tant que les jalons suivants ne sont pas atteints. Un pylône posé **en patch**
  au sol (§6) ne compte pas : il n'est pas constructible, le joueur ne peut pas
  s'en servir pour étendre son réseau (§9.6, `_has_product_recipe`).
- Les pylônes **au-delà** de ces 3 jalons restent randomisés comme de simples
  items/bâtiments (§9.1) — pas de sur-cadence.

Configurable dans `RecursiveConfig` (`dist_marks`, `dist_guaranteed`) via
`recursive` dans `settings` (§19).

### 9.5 Relais des ressources non-infinies

Les ressources non automatisables (arbres → `wood`, rochers → `stone`, poissons
→ `raw-fish`) sont obtenues dès le départ, mais s'épuisent : elles ne peuvent
pas être la colonne vertébrale d'un run. La phase relais, qui tourne **après
toutes les phases productrices de recettes**, garantit leur remplacement :

1. **Scan** : on détecte chaque recette générée dont un ingrédient est un item
   environnemental, et dont le produit n'est pas lui-même environnemental.
2. **Pool gelé du début de run** : les ingrédients et le bâtiment de craft du
   relais sont tirés **uniquement dans l'instantané du pool pris APRÈS le
   starter + l'électricité, AVANT le récursif**. Un relais ne dépend donc
   jamais d'un item ou d'un bâtiment uniquement débloqué en profondeur de seed
   (science pack, oil-refinery, AM3, …) — il est utilisable dès les premières
   recherches, pas au bout de 20 techs. Ce gel est ce qui rend la version
   relais du pumpjack (ou de l'assembleur) réellement jouable dès le début.
3. **Création du relais** : pour ce produit, on tire une **recette relais**
   (`randputf-relay-<produit>`) — même produit, mais ingrédients tirés dans ce
   pool gelé (patch, item fabriqué, fluide obtenu), bâtiment de craft limité à
   ceux du même instantané (jamais de déblocage sur le tas hors pool). Le
   relais coexiste avec la recette bootstrap d'origine, qui reste
   hand-craftable.
4. **Consolidation en prologue** : les recettes relais sont regroupées en
   **techs de prologue** (`randputf-prologue-*`, §7, **≤ 5 unlocks chacune**,
   plafond §13), placées
   **immédiatement après les techs gratuites du starter** (une seule si peu de
   recettes, aucune si rien). Elles ne sont pas des free_researches et se
   débloquent par **hand-craft** d'un item du bootstrap (§9.3) : le bootstrap
   reste la route de départ, et le
   joueur bascule sur les versions propres + l'entrée en sciences dès qu'il
   fabrique le déclencheur — sans compter sur le bois/pierre/poisson sur la durée.

Règles d'anti-cycle spécifiques au relais :

- ingrédients interdits : environnementaux + **le produit lui-même** + les
  produits **déjà relayés** (dans l'ordre de création pour les relais, jamais
  de dépendance vers un relais plus ancien → **DAG** par construction) ;
- les recettes relais ne peuvent **pas** référencer un fluide en ingrédient
  pour produire un **extracteur** (même règle items-only que §8) ;
- le scan est **relancé jusqu'à stabilité** : une recette créée « sur le tas »
  pendant un tirage (déblocage d'un bâtiment) peut à son tour consommer des
  environnementaux et mériter son propre relais.

Si aucun item durable n'est disponible (cas limite d'une seed sans aucun pool
item), le relais est simplement **manqué silencieusement** : la recette bootstrap
reste l'unique route — acceptable puisque la solvabilité, elle, est garantie.

**Conséquence sur la validation (§15)** : un relais n'est qu'une **route
alternative** à un produit — pas un doublon cyclique. L'anti-cycle est donc
vérifié au niveau **item** (un item est solvable dès que l'une de ses recettes
l'est), et non plus en tri topologique de Kahn au niveau recette.

### 9.6 Couverture complète : le balayage de contenu

Sans étape supplémentaire, la récursion (§9) ne touche que les 4 catégories
fonctionnelles + combat + science : une fois les bâtiments de ces catégories
recrutés, la boucle s'arrête (~35 techs) et le reste du jeu **n'a jamais de
recette**. Une phase **3bis**, exécutée **après** la récursion pondérée et
**après** la chaîne fusée (§14), garantit à **chaque item restant** sa recette
`randputf-<item>` et sa tech `randputf-content-<item>` :

- **Cibles** : tout item beltable sans recette produit, dans un ordre
  déterminé par la seed.
- **Coûts** : la récursion précédente a déjà unlocké **tous** les science packs,
  donc le coût de chaque tech de balayage est toujours un pack déjà disponible
  (payable production → consommation, §13).
- **Patches** : un item posé au sol (§6) garde quand même sa recette
  (`make_recipe`, pas `ensure_obtainable`) : « obtainable » ≠ « craftable ».
- **Exclusions** : chaîne fusée (`processing-unit`, `low-density-structure`,
  `rocket-fuel`, `rocket-silo` — sinon doublon d'unlock avec `randputf-endgame-*`),
  armes montées (rattachées à LEUR véhicule en §12 — jamais randomisées comme
  armes de poing), items de contrôle non empilables (`TOOL_LIKE_ITEMS` :
  blueprint, planner, *remotes*, rail-planner…) — jamais de recette ni de
  patch.
- **Empilabilité** : Factorio refuse qu'une recette produise **ou** consomme
  plus de 1 exemplaire d'un item non-empilable (armure, arme à feu, véhicule,
  capsule/remote…) — erreur de chargement « not stackable but has a max count
  of N ». Le générateur clampe donc `amount` à **1** pour tout produit ou
  ingrédient non-stackable (`ItemDef.is_stackable`) : le `stack_size` réel du
  dump fait foi quand il en porte un, sinon le type (`gun`, `armor`,
  `item-with-entity-data`, capsules…) déduit la non-empilabilité
  (`NON_STACKABLE_ITEM_TYPES`).
- **Nommage** : un ID finissant par `-<nombre>` est lu par Factorio comme un
  **palier d'upgrade** et exige des paliers contigus (uranium-235 puis
  uranium-238 → niveaux 235 puis 238 non contigus → erreur de chargement). Les
  suffixes numériques des techs sont donc **convertis en chiffres romains**
  (`_roman_value`), sauf la chaîne volontaire `randputf-prologue-1/2` dont les
  paliers 1→2 sont contigus.

Résultat : ~180 techs / ~200 recettes par seed, dont des techs de contenu
(belts, inserters, chests, modules, robots, trains, isotopes…).

## 10. L'électricité

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
  (classement §5).
- **Unlock du générateur** : les recettes créées pour l'électricité
  (générateur lui-même, combustible) sont **réintégrées aux techs du starter**
  après la phase — jamais une recette orpheline sans tech pour la débloquer.
- **Amorçage à la main (anti-boucle)** : le **premier** générateur électrique
  de la seed — qu'il vienne de la phase électricité ou d'un tirage récursif
  post-starter — a une recette **craftable à la main** : ingrédients 100%
  solides, aucune catégorie ni atelier. Un assembling-machine-2 ou une usine
  chimique exigeraient l'électricité que ce générateur doit justement amorcer
  (bootstrap impossible sinon). Les générateurs suivants retombent sur des
  ateliers normaux.
- **Pylônes (poteaux électriques)** : la distribution du courant entre le
  générateur et les bâtiments est indispensable — sans poteau, l'électricité
  produite ne transporte rien de jouable. Dès qu'un besoin électrique apparaît,
  un **bâtiment de distribution** (poteau) est aussi débloqué avec sa recette,
  dans la même phase (réintégrée aux techs du starter).
- **Combustible du générateur** :
  - si le bâtiment a besoin d'un combustible item, on lui **assigne** un item
    comme combustible ;
  - s'il a besoin d'un fluide, on lui en prend un **disponible** dans le pool ;
  - s'il n'existe aucune ressource disponible compatible, on **crée une
    recette et tout ce qui va avec** (même logique de déblocage sur le tas
    que §9.5).

Exemple d'enchaînement cohérent : turbine tirée → son fluide d'entrée est
décidé à sa création → ce fluide provient soit d'un patch existant, soit d'un
transformateur (type chaudière) alimenté par un combustible assigné ou créé.

## 11. Combat et armement

- **Les biters ne changent pas** (pour l'instant) : comportement, évolution et
  pollution restent vanilla.
- **Les armes sont randomisées** : elles sont déblocables selon le même
  système de pourcentages que les autres bâtiments.
- **Munitions** : chaque arme est obtensible avec un type de balles calé sur
  elle. Les *autres* types de munitions sont ensuite vus comme de simples
  crafts — plus tard ; ou potentiellement avant, s'ils ont été choisis comme
  recette plus tôt. Il est donc parfaitement possible qu'une arme soit
  débloquée **sans** sa munition dédiée : celle-ci a pu être entièrement
  débloquée avant.

## 12. Transports avancés

Trains, véhicules et logistique avancée suivent exactement le même modèle
que les armes : ce sont simplement des **catégories d'objets** déblocables par
les mêmes pourcentages, avec si besoin des dépendances — toujours
**minimes**, posées au moment du tirage. Forme attendue de ces dépendances :
un véhicule peut exiger un **combustible** pour être utilisable ; un train
exige les **rails avant ou en même temps** que lui. Rien de plus : aucun
traitement spécial.

### 12.1 Armes montées randomisées

Les armes **montées-uniquement** (`VEHICLE_GUNS` : cannons, mitrailleuses,
lance-flammes, artillerie, roquettes de spidertron) sont **exclues du pool de
poing** (§11) et du balayage (§9.6) : sans leur véhicule elles seraient du
contenu mort — elles ne sont **jamais craftées**. La randomisation des
véhicules repose sur une **pool cachée** : `pools.vehicle_weapons` liste de
vrais **items gun** (les armes montées ci-dessus, mais aussi des armes de poing
« adoptables » comme le fusil à pompe, le submachine-gun ou le lance-roquettes).
Chaque **véhicule armé** (tank, spidertron, wagon d'artillerie) reçoit
**1..4 armes** tirées dans TOUTE la pool (avec ou sans remise selon la config) :
un tank peut donc hériter d'un pompe, un spidertron d'une artillerie, etc.

**« Arme dans arme »** : chaque arme tirée est **CLONÉE pour CE véhicule** par
`data-updates.lua` (`randputf-<véhicule>-<arme>`, `table.deepcopy`) et **remplace
une arme vanilla** de l'entité — le véhicule ne garde que les armes tirées
(le tank/spidertron remplacent leur tableau `guns`, le wagon d'artillerie son
`gun` unique). Ni item, ni recette, ni unlock : la pool ne sert QU'à
l'assignation (les items de poing de la pool gardent, eux, leur recette de main
normale, §11). Les items *legacy* (tank-machine-gun vanilla,
spidertron-rocket-launcher-2/3/4, identiques au -1) restent du contenu mort :
jamais de recette ni d'unlock.

**Portée scalée selon la taille du véhicule** : la portée du clone est
augmentée pour un véhicule plus gros —
`range × (1 + max(taille - base_size, 0) × scale)`, avec `taille` = extent de
la `selection_box` de l'entité (tank 2.6, spidertron 2, wagon d'artillerie 6).
Avec les défauts (`base_size: 2`, `scale: 0.4`) : le tank étire ses armes
×1.24, le wagon ×2.6, le spidertron (à la taille de base) garde les portées
d'origine. La **munition** consommée par le clone (ammo_category) est celle de
l'arme source : tout ammo est déjà randomisé/craftable (§9.6).

**Munitions garanties après le véhicule** : quand la tech d'un véhicule est
créée, le générateur vérifie les munitions de ses armes montées (par
`ammo_category`). Celles qui n'ont pas encore de recette (elles auraient été
réparties au hasard, potentiellement très après le véhicule) sont créées
immédiatement et **dispatchées dans les 3 techs isolées qui suivent celle du
véhicule** (`randputf-ammo-<véhicule>-<munition>`, payées en science pack déjà
unlocké) : le joueur reçoit son véhicule avec ses munitions au labo dans la
foulée. Les munitions déjà présentes ne sont pas rejouées.

L'assignation est récoltée dans `vehicle_armament` de la seed (items gun réels,
pas de champ `vehicle_armament_items`), la pool dans `pools.vehicle_weapons` et
le scale dans `pools.vehicle_range_scaling` — **aucune valeur en dur** :
`armed_vehicles`, `vehicle_weapons`, `vehicle_slots_min/max`,
`vehicle_slots_with_replacement`, `vehicle_range_base_size` et
`vehicle_range_scale` se configurent via `recursive:` (§16).

**La randomisation est APPLIQUÉE aux prototypes d'entités** : `data-updates.lua`
clone et ré-arme chaque véhicule à partir de `vehicle_armament`. Sans cela la
seed ne changerait RIEN en jeu : les véhicules garderaient leur armement vanilla
figé.

## 13. L'arbre technologique

- **État actuel assumé** : l'arbre est **linéaire**, mais **valide** — sans
  boucle, tout y est déblocable et tout y est géré automatiquement. Chaque
  maillon généré par les phases précédentes y trouve sa place.
- **Un unlock par recette** : chaque recette est unlockée par **une seule**
  tech (jamais de double unlock — par ex. l'extracteur n'apparaît que dans la
  tech d'extraction, pas dans celle de transformation).
- **Aucune recette orpheline** : les macro-techs du starter sont **rejouées
  après la phase d'électricité** ; toute recette créée sur le tas au fil des
  phases (générateur, combustible, lab) est systématiquement rattachée à une
  tech — le validateur rejette toute seed avec une recette non déblocable.
- **Branchement** : un arbre en branches pourra être envisagé **à la fin de
  l'implémentation** ; ce point est explicitement mis de côté d'ici là.
- **Nombre d'objets par tech** : chaque tech « groupable » débloque **1 objet
  de base, étendu en chaîne probabiliste** — 75 % de chance d'un 2e objet,
  65 % d'un 3e, 35 % d'un 4e, 15 % d'un 5e (le premier tirage raté stoppe le
  groupe, plafond strict de 5). Probabilités configurables via
  `tree.group_chances` (§16). Les nœuds dédiés (sciences, pylônes, dispatch de
  munitions, techs de prologue §7, endgame §14) conservent leur forme isolée,
  capés à 5 aussi. Exception assumée : la **2e recherche gratuite du starter**
  (§8) reste monolithe — elle débloque tout le bootstrap d'un coup (lab, packs,
  premiers bâtiments), c'est la nature même du booster de départ.
- **Coûts de recherche** : le coût d'une recherche peut être un **matériau**
  arbitraire et pas seulement des packs de science (le jeu de base le permet,
  c'est juste rare). Point à ne surtout pas oublier : ce matériau doit être
  **à obtenir** dans la progression courante **et utile pour la suite** —
  jamais un cul-de-sac.
- **Cohérence des sciences** : chaque pack qui sert de coût possède une recette
  générée **et unlockée avant** la tech qui le consomme (production avant
  consommation, vérifié à la génération). Le lab étant garanti dès le starter
  (§8), l'économie de packs est réellement consommable.
- **JAMAIS de ressource brute dans un pack** : la recette d'un science pack ne
  consomme aucune matière extraite du sol — ni patch posé en ressource, ni item
  environnemental (bois/pierre/poisson), ni fluide d'extraction (eau, pétrole
  brut, vapeur — infinis ou non, §3). Elle se fabrique exclusivement à partir
  d'intermédiaires craftés. Appliqué au tirage (starter, branche science,
  balayage de contenu) et vérifié par l'invariant 7 (§15).
- **Coût systématique** : **toute tech récursive paie un coût en science pack**
  (bâtiments, armes, packs). Une tech gratuite en profondeur rendrait la
  progression triviale. Pour amorcer la filière, le **premier** science pack
  est rendu craftable et unlocké **gratuitement par le starter** (starter-
  transformation, façon red-science vanilla) — les techs de prologue
  (`randputf-prologue-*`, §7) se débloquent, elles, par **hand-craft**
  (cost vide, §9.3) d'un item **effectivement craftable dès le bootstrap** :
  le pool des déclencheurs est limité aux produits des recettes des techs
  gratuites du starter (jamais aux recettes étendues ensuite par les autres
  phases — §9.3), donc la quantité n'est jamais demandée avant d'être
  fabricable ; seuls les science
  packs (items type tool) sont admis comme coût de recherche par le moteur ;
  chaque pack suivant se débloque en consommation du pack précédent, donc
  chaque tech a toujours un pack déjà produit vers lequel pointer.
- Les **science packs** eux-mêmes suivent les pourcentages d'obtention, comme
  les bâtiments et tout le reste (§9.1).
- **Affichage du coût en nombre d'items** : le coût d'une tech s'affiche comme
  une **quantité de science packs** (le `count` de la recherche = nombre total
  d'items à fournir, `amount = 1` par pack), façon vanilla — la jauge de
  recherche compte exactement le nombre de packs, pas un « temps d'attente »
  dominant. La durée par unité reste fixée (`time = 60 s`) mais le nombre
  d'items est l'affichage privilégié.
- **Icônes des items débloqués** : chaque nœud de l'arbre affiche les **images
  des items/recettes qu'il débloque** (unités, bâtiments, armes, science packs)
  au lieu de l'icône par défaut du template (machine d'assemblage). Jusqu'à
  **4 icônes** en grille 2×2, comme les techs multi-icônes vanilla ; chaque
  nœud montre ainsi clairement ce qu'il déverrouille.

## 14. Fin de partie

Classique et inchangée :

- **victoire = lancement de la fusée** ;
- ensuite, le joueur peut continuer vers les **technologies infinies**, qui ne
  changent pas dans leur principe.

Le randomizer doit garantir l'atteignabilité de la fusée pour toute seed
acceptée (§15).

**Phase endgame** : en base 2.0, `rocket-part` (recette vanilla
exempte, jamais désactivée) consomme `processing-unit`, `low-density-structure`
et `rocket-fuel`. Leurs recettes vanilla étant désactivées par le randomizer,
une phase **après le récursif et avant les relais** garantit une recette
générée pour chacun de ces 3 items — ingrédients tirés dans le pool profond,
**jamais** environnementaux (pas de fusée au bois/pierre) — unlockés par la
dernière tech de l'arbre (`randputf-endgame-rocket`). Sans cette phase, la
fusée (et donc la victoire) serait inatteignable pour toutes les seeds.

La phase endgame garantit aussi le **rocket-silo lui-même** : `rocket-part` se
craft **dans** le silo. Si la récursion s'arrête sans déployer le silo, rien
ne peut lancer de fusée ; l'item `rocket-silo` (jamais un patch, §6) reçoit
donc sa recette générée dans la même tech finale `randputf-endgame-rocket`, ou
par sa tech récursive si la récursion l'a déjà déployé (chaque recette reste
débloquée par une seule tech, §15).

## 15. Règles de solvabilité

Cinq invariants, vérifiés par le tool externe avant validation d'une seed :

1. **Anti-cycle** : aucun maillon ne peut dépendre de sa propre production.
   Toute entrée auxiliaire d'un bâtiment provient d'une branche déjà valide ;
   les tuyaux d'un fluide requis peuvent être faits de ce fluide ou d'une
   autre ressource, jamais de la ressource qui en a besoin (règle des tuyaux,
   §8). La vérification se fait au niveau **item** par point fixe
   (`_detect_unreachable_products`) : un item est solvable dès que **l'une**
   de ses recettes l'est — les recettes relais
   (§9.5) sont des routes alternatives, pas des doubles-arêtes cycliques ;
   un aller-retour `relais-A → bootstrap-B → relais-A` n'est pas une boucle
   bloquante tant que chaque item de la paire reste solvable par une autre
   route.
2. **Progressivité** : chaque nouveau maillon (recette, bâtiment, combustible,
   ressource) n'est ajouté que si ses prérequis sont satisfaits par le pool
   atteignable — ou rendus satisfaits immédiatement par déblocage sur le tas
   (§9.5), lui-même soumis à la règle 1.
3. **Complétude** : la chaîne générée mène nécessairement à tous les
   composants requis par le lancement de fusée (les 3 ingrédients de
   `rocket-part` ET le rocket-silo générés et unlockés, §14) ; les coûts de
   recherche en matériaux sont couverts par la progression (chaque pack de
   coût possède une recette unlockée avant la tech qui le consomme, §13).
4. **Unlock unique** : toute recette de la seed est déblocable par **au moins
   une** tech et **une seule**. Les phases peuvent réclamer plusieurs fois la
   même `randputf-<item>` (une recette de bâtiment d'abord créée comme produit
   d'un autre bâtiment, un item de fusée, ...) : au montage de l'arbre, seule
   la **première** tech qui la revendique compte — l'invariant est garanti par
   construction, pas par chance (§13).
5. **Packs sans ressource brute** : aucune recette de science pack ne consomme
   une ressource brute (patch au sol, item environnemental récolté à la main,
   fluide d'extraction — infinis ou non, §3/§13). Vérifié en fin de pipeline
   sur les recettes de la graine (`_check_packs_no_raw`), en plus de
   l'exclusion appliquée au tirage par la génération.

Une seed qui viole l'un de ces invariants est rejetée et régénérée par le tool,
jamais livrée au joueur.

## 16. Seed et configuration

- Pour l'instant, la seed est fixe et renseignée dans **le fichier des
  settings** (`config/settings.yaml`, key `seed`).
- La config est **réellement consommée** par la génération : `seed`, `paths`,
  `map`, la section `recursive:` (poids des catégories, cadence des
  pylônes §9.4, **armes montées §12.1** : `armed_vehicles`, `vehicle_weapons`,
  `vehicle_slots_min/max`, `vehicle_slots_with_replacement`,
  `vehicle_range_base_size`, `vehicle_range_scale`) puis la section `tree:`
  (`group_chances`, nombre d'objets par tech §13) — aucune valeur
  d'algorithme codée en dur dans le moteur.
- La seed exporte en plus des structures de documentation/jouabilité :
  `pools.vehicle_weapons` (items gun de la pool montée §12.1),
  `pools.vehicle_range_scaling` (`base_size` + `scale`, §12.1),
  `vehicle_armament` (assignation véhicule → armes de la graine courante) et
  `pools.raw_resources` (ressources brutes de la graine, §3 — vérifiable sans
  re-génération).
- Ultérieurement, une génération automatique pourra être ajoutée (probablement
  dérivée de la date et de l'heure) — mais on démarre volontairement avec une
  seed fixe pour maîtriser le développement et le débogage.

## 17. Pipeline technique

Chaîne complète, de l'écriture d'une seed à une partie jouable :

1. `config/settings.yaml` — paramètres généraux (fourchettes, pondérations,
   pools, récursion/armes montées, loot du site de crash §7).
2. Tool Python :
   1. parse les prototypes vanilla 2.0 (items beltables, fluides pipables,
      bâtiments avec leurs slots/directives par tier) ;
   2. tire le graphe complet depuis la seed (phases §6 → §14) ;
   3. vérifie les invariants de solvabilité (§15) ;
   4. écrit `seed.json` (+ données associées) dans le dossier du mod.
3. Mod Factorio, data-stage : lecture YAML/JSON → construction des entités
   ressources cachées, des recettes et de l'arbre technologique.
4. Runtime (`control.lua`) : génération de la surface (placement des patchs
   tirés, remplacement des ressources vanilles), kit de départ, recherches
   gratuites, déblocages progressifs au fil des recherches.

## 18. Structure du projet

```
randputF/
├── README.md            # ce document
├── .gitignore
├── config/              # configurations YAML
├── tool/                # générateur externe Python
│   ├── parsers/         # extraction des prototypes vanilla
│   ├── generator/       # moteur de tirage & graphe
│   │   ├── relay_phase.py  # recettes relais + techs de prologue (≤5 unlocks, §7/§9.5)
│   │   └── …
│   ├── prototypes/      # classes de génération (RecetteConfig, RelayConfig…)
│   └── validator/       # vérification de solvabilité
└── mod/                 # le mod Factorio 2.0
    ├── data.lua         # data-stage : lecture seed, construction
    ├── control.lua      # runtime : carte, déblocages, kit
    └── seed/            # seed.json et données générées
```

(La structure fine pourra évoluer pendant l'implémentation ; les rôles de
haut niveau restent ceux décrits en §4.)

## 19. Roadmap

1. **v1 — vanilla seul** : implémentation complète de tout ce document
   (starter récursif, électricité, armes, arbre linéaire, fusée).
2. **Fins d'implémentation v1** :
   - passage possible de l'arbre technologique linéaire à un arbre **branché** ;
   - génération automatique de seed (date/heure).
3. **Projet futur séparé** : support de **mods tiers** — parsing dynamique du
   contenu arbitraire (Krastorio, Py, …). Bien plus tardif, conditionné au
   succès du moteur sur vanilla.

## 20. Mise en route

### 20.1 Environnement de développement

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

### 20.2 Récupérer la base vanilla (une fois par version du jeu)

Le tool ne devine rien : il consomme un **dump JSON des prototypes** produit
par ton propre jeu, via le mod compagnon `exporter/` :

1. copie (ou symlink) `exporter/` dans `~/.factorio/mods/randputf-exporter_0.1.0/` ;
   si le symlink n'est pas détecté (sandbox Flatpak), utilise une copie du dossier ;
2. lance Factorio une partie quelques secondes — à l'init, il écrit
   `script-output/randputF/vanilla_dump.json` dans le dossier user-data
   (sans `randputF` monté, sinon c'est sa data-stage qui bloque l'export : retire
   ou désactive temporairement le mod principal) ;
3. copie ce fichier dans `data/vanilla_dump.json` du projet ;
4. **désactive `randputf-exporter` avant toute partie avec le mod principal.**

> ⚠️ **Pour l'instant, `randputF` et `randputf-exporter` ne peuvent pas être
> lancés ensemble : ne cohabitent pas.** C'est temporaire : par la suite, ils
> iront naturellement ensemble — l'exporter n'est qu'un outil compagnon de
> développement destiné à disparaître ou fusionner dans le mod principal.

### 20.3 Générer et jouer une seed

```bash
.venv/bin/python -m tool parse --demo      # vérifie la base (mode synthétique)
.venv/bin/python -m tool generate          # génère + valide + exporte mod/seed/
```

Puis symlink le mod principal : `~/.factorio/mods/randputF_0.1.0 -> mod/`,
lance Factorio : les patchs tirés remplacent toutes les ressources vanilles
autour du spawn, le kit de départ est injecté, les recherches gratuites
déblocées.

### 20.4 État actuel du code

| Composant | État |
|---|---|
| `tool/parsers/vanilla.py` | Normalisation dump → `VanillaDB` (items/fluides/bâtiments classés/recettes) |
| `tool/generator/map_patches.py` | Phase 1 implémentée (3–8 patchs, types aléatoires, richesse variable) ; briques garanties jamais en patch (lab §8, fusée + silo §14) |
| `tool/generator/starter_chain.py` | Kit de départ (arme + munitions calées), extraction→transformation→transport, pool environnemental, extracteurs items-only, **bâtiment de recherche dans la 2e recherche gratuite** (§8) + **premier science pack craftable** (§13) |
| `tool/generator/recursive_phase.py` | Phase récursive pondérée (déblocage sur le tas) ; produits = intermédiaires (jamais un item de bâtiment ni la chaîne fusée) ; **coût systématique en science pack**, amorcé par le premier pack craftable du starter (§13) ; **cadence garantie des pylônes** (§9.4) |
| `tool/generator/electricity.py` | Générateur + combustible à la demande (accumulateur exclu du tirage) + **pylône/construction de distribution** ; techs starter rejouées ensuite (§10) |
| `tool/generator/endgame_phase.py` | Chaîne fusée intable : les 3 ingrédients de `rocket-part` **et le rocket-silo** générés, tech finale `randputf-endgame-rocket` (§14) |
| `tool/generator/relay_phase.py` | Recettes relais tirées dans le **pool gelé du début de run** (après starter+électricité) + techs de prologue `randputf-prologue-*` (≤5 unlocks, hand-craft) (§7, §9.5, §13) |
| `tool/generator/tech_tree.py` + `tech_graph.py` | Arbre linéaire assemblé depuis les macro-steps ; **unlock unique par recette** (premier claim gagne, §13/§15) |
| `tool/validator/pipeline_validator.py` | Invariants §15 : anti-cycle par **point fixe de solvabilité** (routes relais = alternatives), progressivité, complétude, unlock unique |
| `mod/data.lua` | Lit la seed : entités ressources cachées, recettes, technologies ; option désactivation arbre vanilla |
| `mod/control.lua` | Runtime : destruction ressources vanilles, placement patchs déterministe, kit départ, recherches gratuites |

La génération valide une seed complète sur la base vanilla réelle (`data/vanilla_dump.json`), seed figure d'exemple : `seed: 5` dans
`config/settings.yaml`. Le mode demo (`parse --demo`) reste utile pour tester
le moteur sur une base synthétique légère.


---

*randputF — chaque partie est un jeu que personne n'a jamais vu.*
