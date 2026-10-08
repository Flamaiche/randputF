# Modèle randput : terminologie et classification des bâtiments

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 3. Terminologie

- **Randput** : contraction de *randomize input/output*. C'est le cœur du mod : chaque slot d'item ou de fluide d'une recette reçoit un élément aléatoire parmi tous ceux disponibles dans le jeu.
- **Item beltable** : tout objet transportable sur un tapis roulant. Il rejoint le pool des ressources brutes de type item.
- **Fluide pipable** : tout fluide capable de circuler dans un tuyau. Il rejoint le pool des ressources brutes de type fluide.
- **Ressource brute (raw)** : ressource extraite directement du milieu (gisement fini au sol ou fluide d'extraction infini ou non). Elle alimente le départ de la production. Règle absolue : **un science pack ne se fabrique jamais directement à partir d'une ressource brute** (§13). Sa recette exige des intermédiaires déjà craftés. Cet invariant est validé à la génération par `raw_resources` (§16).
- **Ressource non automatisable** : objet récolté uniquement à la main ou par interaction directe (arbres, poissons, ...). Elle est exclue des ressources durables (§9.5), mais peut servir d'ingrédient pour des crafts avancés. Comme toute ressource brute, elle reste bannie des recettes de science packs (§13).
- **Recette relais** : alternative de craft pour un produit dont la recette principale exige une ressource non automatisable. Elle n'utilise que des ressources durables et se débloque parmi les 3 premières technologies (§9.5).
- **Ressource durable** : ressource disponible à l'infini durant la partie (gisement, objet fabriqué, fluide produit), contrairement aux ressources non automatisables qui finissent par s'épuiser.
- **Slot** : point d'entrée ou de sortie d'un bâtiment ou d'une recette. Il possède un type précis : item, fluide, combustible ou énergie.
- **Milieu** : environnement d'extraction d'une ressource brute. Les trois valeurs exactes du code sont `ground`, `fluid` et `water`. Deux extracteurs opérant dans des milieux différents partagent le même type fonctionnel : une pompe et une pompe offshore sont toutes deux des extracteurs.
- **Directive** : capacité optionnelle déclarée d'un bâtiment. Elle permet de différencier deux machines de même type (§5).
- **Pool atteignable** : ensemble des éléments accessibles par le joueur à une étape précise de la génération (ressources placées, bâtiments débloqués, recettes validées).
- **Déblocage sur le tas** : processus où le randomizer génère à la volée les éléments requis pour valider une recette (méthode d'extraction, craft intermédiaire, combustible, ...).
- **Graine / seed** : valeur déterministe qui régit tous les tirages du randomizer. Unique et basée par défaut sur le temps système (en millisecondes), elle peut être fixée avec l'option `--seed` (§16).
- **Gaté / gating** (sans accent circonflexe) : ressource volontairement écartée du pool d'une seed pour retarder son apparition dans la partie. Ce terme technique provient de l'anglais *gating*. Il figure dans `seed.md`, `DEVIANCES.md` et `nondeterminism.md`, et est explicitement documenté dans le `CHANGELOG.md`.

## 5. Le modèle randput : classification des bâtiments

Ce modèle est le pilier du moteur de génération. **Aucun bâtiment n'est lié à ses recettes vanilla.** Chaque entité se définit par :

1. un **type** fonctionnel ;
2. des **slots** d'entrée et de sortie typés ;
3. des **directives** décrivant ses capacités optionnelles.

Cette classification rigoureuse permet au randomizer de créer des combinaisons surprenantes tout en garantissant la cohérence logique du monde.

### 5.1 Types fonctionnels

| Type | Rôle | Exemples vanilla |
|---|---|---|
| `extractor` | Extrait une ressource brute d'un milieu | foreuse, pompe offshore, pompe à pétrole |
| `transformer` | Convertit des entrées en sorties | fours, machines d'assemblage, usine chimique, raffinerie, chaudière |
| `research` | Convertit des science packs en technologies | laboratoire |
| `generator` | Produit de l'énergie | turbine, panneau solaire, réacteur |
| `distribution` | Distribue l'électricité | poteaux électriques |
| `other` | Autres comportements | coffres, bras robotisés, tapis roulants |

Notez que le transport, la logistique et la consommation d'énergie ne sont pas des types fonctionnels, mais des tags (§2 : `is_belt`, `is_logistics_chest`, `consumes_electricity`).

- **Pas de chaîne de production figée** : une pompe et une pompe offshore appartiennent toutes deux au type `extractor`, mais opèrent dans des milieux différents. Le moteur de génération raisonne par types et par milieux, jamais par objets spécifiques.
- Une **chaudière** est classée comme `transformer` (au même titre que les fours) : elle consomme des entrées (fluide, combustible) pour générer une sortie (autre fluide).
- Une **turbine** (type `generator`) requiert un fluide en entrée, déterminé uniquement **lors de sa création** par le randomizer.
- Un **laboratoire** (type `research`) n'est jamais un `transformer`. Identifié par sa consommation de science packs, il est garanti dès le kit de départ (§8) et n'apparaît jamais dans le pool des ateliers de craft.

### 5.2 Slots typés

Chaque slot est associé à l'un des types suivants :

- **item** : tout élément transportable sur tapis ;
- **fluide** : tout élément transportable par tuyau ;
- **combustible** : item ou fluide possédant une valeur énergétique ;
- **énergie** : cas particulier (§10).

### 5.3 Directives : les possibilités par tier

Les directives décrivent les capacités d'action d'un bâtiment, indépendamment de ses recettes vanilla. Elles introduisent des variations de puissance entre les différents tiers d'un même type. Exemples types :

- Un **assembleur de tier 1** n'accepte que des slots d'items. Un **assembleur de tier 2** peut recevoir une entrée fluide supplémentaire : une recette avec fluide peut donc lui être assignée si la ressource d'entrée requise est un fluide.
- Une **foreuse électrique** peut exiger un fluide dès le début de la partie (directive d'entrée auxiliaire). Le moteur garantit l'accessibilité de ce fluide : les tuyaux de transport peuvent être fabriqués **avec ce fluide lui-même** ou via une **autre ressource**, mais **jamais à partir de la ressource extraite par cette foreuse** (règle anti-cycle, §8 et §15).
