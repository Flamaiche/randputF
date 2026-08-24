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
- **Ressource brute (raw)** : ressource extraite directement du sol. Seule
  elle alimente le début de la chaîne de production.
- **Ressource non automatisable** : entité récoltable à la main ou par
  interaction directe (arbres, poissons, …). Exclue du calcul des ressources
  brutes, mais réintroduite comme ingrédient possible dans les crafts
  ultérieurs.
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
- il n'y a **aucune contrainte d'homogénéité** : certains patchs peuvent
  n'être que des fluides, d'autres que des items, ou un mélange des deux ;
  c'est totalement aléatoire ;
- l'abondance (richesse) des patchs est également variable ;
- les ressources **non automatisables** (arbres, poissons, etc.) sont
  **exclues** du calcul des ressources brutes : elles ne constituent jamais un
  patch. En revanche elles demeurent utilisables comme ingrédients dans des
  crafts, et seront alors obtenables/utilisables plus tard dans la partie.

Conséquence structurelle : plus aucune plaque de fer/cuivre/charbon ni gisement
de pétrole classique n'est garantie au sol — le joueur découvre à chaque
partie de quoi son monde est fait.

## 7. La phase de démarrage

Le randomizer détermine tout dès le spawn (l'électricité suivra sa propre
logique, §10) :

1. **Kit de départ randomisé** : le joueur ne commence pas forcément avec le
   même équipement. Son arme de départ est tirée au hasard, et **les munitions
   se calent sur l'arme** pour qu'il puisse effectivement l'utiliser.
2. **Une ou deux recherches gratuites** : après le stuff de départ, le jeu
   présente au joueur une ou deux recherches « gratuites » pour lui donner
   quelque chose à faire. En pratique : elles apparaissent dans l'arbre tech
   comme les autres mais sont détectées comme gratuites et donc passées en
   recettes déjà débloquées. Cela ne concerne que le tout début.

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
- **Combustible du générateur** :
  - si le bâtiment a besoin d'un combustible item, on lui **assigne** un item
    comme combustible ;
  - s'il a besoin d'un fluide, on lui en prend un **disponible** dans le pool ;
  - s'il n'existe aucune ressource disponible compatible, on **crée une
    recette et tout ce qui va avec** (même logique de déblocage sur le tas
    que §9.3).

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

Trains, véhicules et logistique avancée suivent exactement le même modèle que
le reste : ce sont simplement des **catégories d'objets** — comme les balles —
avec quelques dépendances propres (rails nécessitent des plaques, locomotives
des composants…), calées sur les besoins au moment de leur tirage. Aucun
traitement spécial.

## 13. L'arbre technologique

- **État actuel assumé** : l'arbre est **linéaire**, mais **valide** — sans
  boucle, tout y est déblocable et tout y est géré automatiquement. Chaque
  maillon généré par les phases précédentes y trouve sa place.
- **Branchement** : un arbre en branches pourra être envisagé **à la fin de
  l'implémentation** ; ce point est explicitement mis de côté d'ici là.
- **Coûts de recherche** : le coût d'une recherche peut être un **matériau**
  arbitraire et pas seulement des packs de science (le jeu de base le permet,
  c'est juste rare). Point à ne surtout pas oublier : ce matériau doit être
  **à obtenir** dans la progression courante **et utile pour la suite** —
  jamais un cul-de-sac.
- Les **science packs** eux-mêmes suivent les pourcentages d'obtention, comme
  les bâtiments et tout le reste (§9.1).

## 14. Fin de partie

Classique et inchangée :

- **victoire = lancement de la fusée** ;
- ensuite, le joueur peut continuer vers les **technologies infinies**, qui ne
  changent pas dans leur principe.

Le randomizer doit garantir l'atteignabilité de la fusée pour toute seed
acceptée (§15).

## 15. Règles de solvabilité

Trois invariants, vérifiés par le tool externe avant validation d'une seed :

1. **Anti-cycle** : aucun maillon ne peut dépendre de sa propre production.
   Toute entrée auxiliaire d'un bâtiment provient d'une branche déjà valide ;
   les tuyaux d'un fluide requis peuvent être faits de ce fluide ou d'une
   autre ressource, jamais de la ressource qui en a besoin (règle des tuyaux,
   §8).
2. **Progressivité** : chaque nouveau maillon (recette, bâtiment, combustible,
   ressource) n'est ajouté que si ses prérequis sont satisfaits par le pool
   atteignable — ou rendus satisfaits immédiatement par déblocage sur le tas
   (§9.3), lui-même soumis à la règle 1.
3. **Complétude** : la chaîne générée mène nécessairement à tous les
   composants requis par le lancement de fusée ; les coûts de recherche en
   matériaux sont couverts par la progression.

Une seed qui viole l'un de ces invariants est rejetée et régénérée par le tool,
jamais livrée au joueur.

## 16. Seed et configuration

- Pour l'instant, la seed est fixe et renseignée dans **le fichier des
  settings**.
- Ultérieurement, une génération automatique pourra être ajoutée (probablement
  dérivée de la date et de l'heure) — mais on démarre volontairement avec une
  seed fixe pour maîtriser le développement et le débogage.

## 17. Pipeline technique

Chaîne complète, de l'écriture d'une seed à une partie jouable :

1. `config.yaml` — paramètres généraux (fourchettes, pondérations, pools).
2. Tool Python :
   1. parse les prototypes vanilla 2.0 (items beltables, fluides pipables,
      bâtiments avec leurs slots/directives par tier) ;
   2. tire le graphe complet depuis la seed (phases §6 → §13) ;
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
2. lance Factorio une partie quelques secondes — à l'init, il écrit
   `script-output/randputF/vanilla_dump.json` dans le dossier user-data ;
3. copie ce fichier dans `data/vanilla_dump.json` du projet ;
4. désactive `randputf-exporter` (il ne doit jamais coexister avec randputF).

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
| `tool/generator/map_patches.py` | Phase 1 implémentée (3–8 patchs, types aléatoires, richesse variable) |
| `tool/generator/starter_chain.py` | Kit de départ (arme + munitions calées) implémenté ; chaîne extraction→transformation→transport **à écrire** (contrat en docstring) |
| `tool/generator/recursive_phase.py` | Phase récursive pondérée **à écrire** (contrat en docstring) |
| `tool/generator/electricity.py` | Générateur + combustible à la demande **à écrire** (contrat en docstring) |
| `tool/generator/tech_tree.py` | Arbre linéaire assemblé génériquement depuis les étapes |
| `tool/validator/solver.py` | Invariants §15 : anti-cycle (Kahn), progressivité, complétude |
| `mod/data.lua` | Lit la seed : entités ressources cachées, recettes, technologies ; option désactivation arbre vanilla |
| `mod/control.lua` | Runtime : destruction ressources vanilles, placement patchs déterministe, kit départ, recherches gratuites |

La seed générée en mode demo est volontairement partielle (patchs + kit) :
les phases restantes sont les points d'entrée documentés du développement à
deux.


---

*randputF — chaque partie est un jeu que personne n'a jamais vu.*
