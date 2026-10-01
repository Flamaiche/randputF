# Documentation randputF

Cette documentation est la **référence de conception** du randomizer. Elle
décrit l'ensemble des mécanismes du système, leur justification et les règles
qu'ils respectent. Pour installer et jouer, voir le [README](../README.md).

## 1. Concept général

Un run classique de Factorio est appris par cœur : fer, cuivre, charbon, pétrole ;
les mêmes fours, les mêmes assembleurs, le même arbre de technologie. randputF
supprime toute connaissance préalable : **rien de ce que le joueur connaît n'est
garanti**.

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

## Ordre de lecture conseillé

1. [3. Terminologie](model.md#3-terminologie) — le vocabulaire du projet.
2. [5. Le modèle randput : classification des bâtiments](model.md#5-le-modèle-randput--classification-des-bâtiments) —
   la fondation du moteur (types, slots, directives).
3. [6. Les ressources au sol](ressources.md#6-les-ressources-au-sol) — patches,
   lacs, pose runtime.
4. [7. La phase de démarrage](starter.md#7-la-phase-de-démarrage) et
   [8. La chaîne initiale](starter.md#8-la-chaîne-initiale-starter).
5. [9. La phase récursive](recettes.md#9-la-phase-récursive) — tirages pondérés,
   recettes, déblocage sur le tas, relais.
6. [10. L'électricité](energie.md#10-lélectricité) et
   [10bis. La chaleur](energie.md#10bis-la-chaleur).
7. [11. Combat et armement](combat.md#11-combat-et-armement) et
   [12. Transports avancés](combat.md#12-transports-avancés).
8. [13. L'arbre technologique](tech.md#13-larbre-technologique) et
   [14. Fin de partie](tech.md#14-fin-de-partie).
9. [15. Règles de solvabilité](solvabilite.md#15-règles-de-solvabilité) — les
   invariants garantis pour toute seed acceptée.

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
| [solvabilite.md](solvabilite.md) | §10ter, §15 | Bootstrap sûr (graphe initial correct par construction), vérificateur de bootstrap, invariants de solvabilité |
| [seed.md](seed.md) | §16 | Seed, déterminisme, configuration consommée |
| [architecture.md](architecture.md) | §4, §17, §18 | Architecture générale, pipeline technique, structure du projet |

### Références

| Document | Contenu |
|---|---|
| [tags.md](tags.md) | Référence complète des tags de bâtiments et d'items |
| [nondeterminism.md](nondeterminism.md) | Inventaire des sources potentielles de non-déterminisme et leur résolution |
| [nomenclature-rejoueur.md](nomenclature-rejoueur.md) | Vocabulaire seed ↔ rejoueur : table de correspondance exacte des champs consommés |
| [config.md](config.md) | Les deux fichiers de configuration, chaque clé et section, et les règles de validation |
| [witness.md](witness.md) | Le témoin de déterminisme : ce qu'il couvre, ses exclusions assumées, sa mise à jour au bump de version |
| [graphe-interactif.md](graphe-interactif.md) | Construction de `seed.graph.html` : nœuds, arêtes, icônes fidèles au jeu, autonomie du fichier |

### Notes de chantier

| Document | Contenu |
|---|---|
| [IDEES.md](../IDEES.md) | Idées / corrections en attente (à développer) |
| [DEVIANCES.md](DEVIANCES.md) | Dérives de gameplay assumées, bugs corrigés, avertissements résiduels |
| [roadmap-redressement.md](roadmap-redressement.md) | Plan d'action issu de la revue documentaire du 30 septembre 2026 (lots A à K) |
| [RELEASE.md](../RELEASE.md) | Notes de release (source unique) et procédure de publication |
| [CHANGELOG.md](../CHANGELOG.md) | Historique des versions, garanties mesurées et corrections seed par seed |
| [PLAN_bootstrap_inline.md](../PLAN_bootstrap_inline.md) | Plan du redesign du bootstrap sûr |
| [plan-extracteurs-dispatche.md](plan-extracteurs-dispatche.md) | Plan v2 : jalons de ressources (« late raws ») — principe, mesure, mise en œuvre (§6.3) |
| [developpement.md](developpement.md) | §19, §20 : roadmap, environnement de dev, génération et installation |