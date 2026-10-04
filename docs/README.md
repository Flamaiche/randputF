# Documentation randputF

Cette documentation est la **référence de conception** du randomizer. Elle
décrit l'ensemble des mécanismes du système, leur justification et les règles
qu'ils respectent. Pour installer et jouer, voir le [README](../README.md).

## 1. Concept général

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

## 2. Périmètre et cible

| Élément | Décision |
|---|---|
| Version du jeu | **Factorio 2.0** |
| Contenu | **Base uniquement, sans Space Age** (pas de qualité, pas de planètes, pas de fondries/recycleurs) |
| Mods tiers | **Hors scope v1.** Le randomizer cible le jeu vanilla seul. Le support de contenu de mods tiers (Krastorio, Py, etc.) fera l'objet d'un projet séparé, bien plus tardif |
| Fin de partie | Classique : **lancement de la fusée** = victoire. Les technologies infinies restent disponibles ensuite, inchangées dans leur principe |

Ces choix sont volontairement conservateurs pour garder un moteur robuste.

## Ordre de lecture conseillé

1. [Terminologie](model.md#3-terminologie)
2. [Modèle randput (bâtiments)](model.md#5-le-modèle-randput--classification-des-bâtiments) — fondation du moteur
3. [Ressources au sol](ressources.md#6-les-ressources-au-sol) — patches, lacs
4. [Phase de démarrage](starter.md#7-la-phase-de-démarrage) et [chaîne initiale](starter.md#8-la-chaîne-initiale-starter)
5. [Phase récursive](recettes.md#9-la-phase-récursive) — tirages, recettes, relais
6. [Électricité](energie.md#10-lélectricité) et [Chaleur](energie.md#10bis-la-chaleur)
7. [Combat/armement](combat.md#11-combat-et-armement) et [Transports avancés](combat.md#12-transports-avancés)
8. [Arbre technologique](tech.md#13-larbre-technologique) et [Fin de partie](tech.md#14-fin-de-partie)
9. [Règles de solvabilité](solvabilite.md#15-règles-de-solvabilité) — invariants
10. [Rejoueur (vérification par simulation)](solvabilite.md#15ter-rejoueur-fake-player-vérification-par-simulation) — preuve (1501/1501 victoires)

## Index des documents

### Conception

| Document | Sections | Contenu |
|---|---|---|
| [model.md](model.md) | §3, §5 | Terminologie ; classification des bâtiments (types fonctionnels, slots typés, directives) |
| [ressources.md](ressources.md) | §6 | Patches posés au sol, lacs de fluide, pose runtime déterministe |
| [starter.md](starter.md) | §7, §8 | Kit de départ, techs gratuites, site de crash, lacs ; chaîne initiale (extraction → transformation → transport) |
| [recettes.md](recettes.md) | §9 | Phase récursive : tirages pondérés, recettes, déblocage sur le tas, relais, balayage de couverture |
| [energie.md](energie.md) | §10, §10bis | Électricité (déclenchement, générateurs, ruptures) et chaleur (triade source/transport/sink) |
| [combat.md](combat.md) | §11, §12 | Armes, munitions, transports avancés, armes montées randomisées |
| [tech.md](tech.md) | §13, §14 | Arbre technologique linéaire, fin de partie (fusée) |
| [solvabilite.md](solvabilite.md) | §10ter, §15, §15ter | Bootstrap sûr (graphe initial correct par construction), invariants de solvabilité, rejoueur « fake player » (1501/1501) |
| [seed.md](seed.md) | §16 | Seed, déterminisme, configuration consommée |
| [architecture.md](architecture.md) | §4, §17, §18 | Architecture générale, pipeline technique, structure du projet |

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