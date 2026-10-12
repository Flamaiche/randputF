# Documentation randputF

Cette documentation est la **référence de conception** du randomizer. Elle
décrit l'ensemble des mécanismes du système, leur justification et les règles
qu'ils respectent. Pour installer et jouer, voir le [README](../README.md).

## Concept général

Dans Factorio classique, bien des éléments sont toujours les mêmes. randputF
supprime ce réflexe : **à chaque partie, rien de ce que le joueur connaît n'est
garanti**.

À chaque génération :

- **Ressources au sol** : un nombre et des types aléatoires, choisis parmi
  tout ce que le jeu peut transporter (items sur tapis, fluides dans les tuyaux).
- **Bâtiments** : extraction, transformation et transport sont choisis pour
  s'adapter à ces ressources.
- **Recettes** : elles relient les éléments entre eux, générées aléatoirement.
- **Arbre technologique** : lui aussi est généré pour ce monde.
- **Kit de départ** : fourni aléatoirement.

**Principe : le randput** (randomisation des entrées/sorties). Un slot d'entrée
ou de sortie d'un type donné (item ou fluide) peut recevoir n'importe quel
élément de ce type. Un bâtiment capable de produire/sortir un item peut donc
sortir n'importe quel item ; un bâtiment manipulant des fluides peut manipuler
n'importe quel fluide. Le contenu change, la structure reste : c'est ce qui
garantit un monde cohérent et jouable.

## Périmètre et cible

| Élément | Décision |
|---|---|
| Version du jeu | **Factorio 2.0** |
| Contenu | **Base uniquement, sans Space Age** (pas de qualité, pas de planètes, pas de fonderies/recycleurs) |
| Mods tiers | **Hors scope v1.** Le randomizer cible le jeu vanilla seul. Le support de contenu de mods tiers (Krastorio, Py, etc.) fera l'objet d'un projet séparé, bien plus tardif |
| Fin de partie | Classique : **lancement de la fusée** = victoire. Les technologies infinies restent disponibles ensuite, inchangées dans leur principe |

Ces choix sont volontairement conservateurs pour garder un moteur robuste.

## Arbre de lecture

Racine : ce README. Chaque **parent** expose un concept large ; ses **enfants**
(indentés) n'ajoutent que du détail — un mécanisme, une valeur, une définition. Lire
l'arbre de haut en bas donne d'abord le concept de bout en bout, puis le niveau de détail
du code. Pour installer et jouer : [README racine](../README.md).

- [model.md](model.md) — le modèle randput : terminologie et classification des bâtiments
  - [tags.md](tags.md) — (détail) les tags de `BuildingDef`/`ItemDef`
  - [vanilladb.md](vanilladb.md) — (détail) le dump vanilla et les prédicats de détection
- [ressources.md](ressources.md) — les ressources au sol
  - [ressources-brutes.md](ressources-brutes.md) — (partagé avec `starter`) les formes d'une raw et leur extraction
- [starter.md](starter.md) — la phase de démarrage
  - [amorcage.md](amorcage.md) — (partagé avec `recettes`/`energie`/`tech`) les règles d'amorçage
- [recettes.md](recettes.md) — la phase récursive
  - [aiguillage.md](aiguillage.md) — (partagé avec `tech`/`combat`) pourcentages, groupement, dispatch
- [energie.md](energie.md) — électricité
  - [chaleur.md](chaleur.md) — (partagé avec `tags`) le milieu chaleur
- [combat.md](combat.md) — combat et transports avancés
- [tech.md](tech.md) — arbre technologique et fin de partie
- [solvabilite.md](solvabilite.md) — vérifications de solvabilité
  - [invariants.md](invariants.md) — (partagé avec `recettes`/`tech`/`ressources`) les 7 invariants
  - [nomenclature-rejoueur.md](nomenclature-rejoueur.md) — (détail) vocabulaire seed ↔ rejoueur
- [seed.md](seed.md) — seed, déterminisme, configuration
  - [config.md](config.md) — (détail) clés de configuration
  - [nondeterminism.md](nondeterminism.md) — (détail) sources de non-déterminisme
    - [witness.md](witness.md) — (détail) le témoin de déterminisme
- [architecture.md](architecture.md) — architecture et outillage
  - [pipeline.md](pipeline.md) — (détail) chronologie de génération
  - [modules.md](modules.md) — (détail) outillage Python
  - [runtime.md](runtime.md) — (détail) le mod Lua
  - [graphe-interactif.md](graphe-interactif.md) — (détail) génération de `seed.graph.html`

Un doc peut **mentionner** d'autres concepts sans en être un enfant : le starter, par
exemple, touche aux ressources, aux recettes, à l'énergie et aux techs. Chaque page liste
donc en fin de document son **parent**, ses **enfants** et ses **concepts liés**.

Notes de chantier (hors arbre) : [DEVIANCES.md](DEVIANCES.md),
[developpement.md](developpement.md), [release.md](release.md),
[CHANGELOG.md](../CHANGELOG.md).

## Index des documents

### Conception

| Document | Contenu |
|---|---|
| [model.md](model.md) | Terminologie ; classification des bâtiments (types fonctionnels, slots typés, directives) |
| [ressources.md](ressources.md) | Patches posés au sol, lacs de fluide, pose runtime déterministe |
| [ressources-brutes.md](ressources-brutes.md) | Formes d'une raw (patch item, patch fluide, lac), support, extraction, milieu |
| [starter.md](starter.md) | Kit de départ, techs gratuites, site de crash, lacs ; chaîne initiale (extraction → transformation → transport) |
| [amorcage.md](amorcage.md) | Règles d'amorçage : ce qui doit être fabricable dès le kit, jalons, prologue |
| [recettes.md](recettes.md) | Phase récursive : tirages pondérés, recettes, déblocage sur le tas, relais, balayage de couverture |
| [aiguillage.md](aiguillage.md) | Aiguillage partagé : pourcentages de tirage, groupement de techs, dispatch des munitions |
| [energie.md](energie.md) | Électricité : déclenchement, générateurs, ruptures |
| [chaleur.md](chaleur.md) | Milieu chaleur : triade source/transport/sink |
| [combat.md](combat.md) | Armes, munitions, transports avancés, armes montées randomisées |
| [tech.md](tech.md) | Arbre technologique linéaire, fin de partie (fusée) |
| [solvabilite.md](solvabilite.md) | Bootstrap sûr (graphe initial correct par construction), rejoueur « fake player » (1501/1501) |
| [invariants.md](invariants.md) | Les sept invariants de solvabilité que le générateur doit respecter |
| [seed.md](seed.md) | Seed, déterminisme, configuration consommée |
| [architecture.md](architecture.md) | Architecture générale, pipeline technique, structure du projet |

### Références

| Document | Contenu |
|---|---|
| [tags.md](tags.md) | Référence complète des tags de bâtiments et d'items |
| [nondeterminism.md](nondeterminism.md) | Sources de non-déterminisme et leur résolution |
| [nomenclature-rejoueur.md](nomenclature-rejoueur.md) | Correspondance exacte seed ↔ rejoueur |
| [config.md](config.md) | Configuration (defaults + user) : clés, sections, validation |
| [witness.md](witness.md) | Témoin de déterminisme : périmètre, exclusions, mise à jour au bump |
| [release.md](release.md) | Procédure de publication et état des versions (ce qui est publié, ce qui est en préparation) |
| [graphe-interactif.md](graphe-interactif.md) | Génération de `seed.graph.html` (nœuds, arêtes, icônes) |
| [modules.md](modules.md) | Le outillage Python : une passe par module et son statut de branchement (branché / testé non branché / diagnostic) |
| [pipeline.md](pipeline.md) | Chronologie de génération : fonctions d'orchestration, jalons, flux RNG, invariants, chemin d'échec |
| [vanilladb.md](vanilladb.md) | `VanillaDB` : format du dump vanilla, schéma des données, prédicats de détection, inférences |
| [runtime.md](runtime.md) | Le mod Lua : les cinq fichiers, le contrat `seed` → Lua, les clés consommées, le câblé-inactif |

### Notes de chantier

| Document | Contenu |
|---|---|
| [DEVIANCES.md](DEVIANCES.md) | Dérives assumées, bugs corrigés, avertissements résiduels |
| [CHANGELOG.md](../CHANGELOG.md) | Historique des versions, garanties mesurées, corrections seed par seed |
| [developpement.md](developpement.md) | Roadmap, dev, génération et installation |