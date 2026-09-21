# Modèle randput : terminologie et classification des bâtiments

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

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
  randomizer. Par défaut tirée de l'instant présent (millisecondes) à chaque
  génération, donc unique ; on peut imposer une valeur via `--seed` (§16).

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
