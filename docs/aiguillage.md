# L'aiguillage : mise en technologies

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

> **Cas partagé** entre [recettes.md](recettes.md) (tirages et groupement de contenu),
> [tech.md](tech.md) (construction de l'arbre) et [combat.md](combat.md) (armes et
> munitions). L'aiguillage décrit **comment un élément atterrit dans une tech** :
> combien de chances il a d'être tiré, avec quoi il est groupé, et quand il doit rester
> isolé.

## Comment les éléments rejoignent l'arbre

### Pourcentages d'obtention (tirages pondérés)

Chaque catégorie (bâtiments, armes, science packs, transports avancés…) dispose d'un
**pourcentage d'obtention** qui dépend du **type du bâtiment** et du **nombre total de
bâtiments** déjà présents dans la partie. Plus la progression avance, plus le pool
s'élargit. Les science packs suivent ces mêmes pourcentages
([recettes.md](recettes.md#tirages-pondérés), [tech.md](tech.md#larbre-technologique)).

### Groupement en une tech

Une technologie « groupable » débloque **1 objet de base**, puis s'étend selon une
chaîne probabiliste : **75 %** pour un 2e objet, **65 %** pour un 3e, **35 %** pour un
4e, **15 %** pour un 5e — le premier tirage échoué arrête le groupe (plafond 5 via
`tree.max_per_tech`, probabilités via `tree.group_chances`, [seed.md](seed.md#seed-et-configuration)). Les nœuds **dédiés** (sciences, munitions, techs de
prologue, endgame) restent isolés, et un nœud monolithe existe pour la 2e recherche
gratuite du starter ([tech.md](tech.md#larbre-technologique)).

### Nœuds isolés et dispatch

Certains contenus **ne fusionnent jamais** et sont distribués dans des **techs isolées
juste après** leur déclencheur, par un patron commun (le « dispatch ») :

- **Munitions d'arme de poing** : chaque arme est liée à un type de munitions. Si une
  arme débloquée n'a **aucune** munition compatible disponible, une munition est générée
  et débloquée dans la **même tech** — une arme n'est jamais inutile. Si une munition
  compatible existe déjà, rien n'est ajouté ([combat.md](combat.md#combat-et-armement)).
- **Munitions de véhicule** : lors de la création de la tech d'un véhicule, le générateur
  vérifie les munitions de ses armes (via `ammo_category`) ; celles qui n'ont pas encore
  de recette sont créées et **dispatchées dans jusqu'à 3 techs isolées qui suivent** celle
  du véhicule (`randputf-ammo-<véhicule>-<munition>`), payées par des packs déjà
  débloqués. Les munitions déjà présentes ne sont pas recalculées
  ([combat.md](combat.md#armes-montées-randomisées)).
- **Compagnons** : les produits liés (roboport + robots, panneau solaire + accumulateur)
  reçoivent des **techs isolées juste APRÈS la tech du produit**, à ±3 techs
  ([recettes.md](recettes.md#garantie-de-compagnons)).
- **Prologue** : les recettes relais sont regroupées en techs de prologue isolées juste
  après les free techs du starter ([starter.md](starter.md#la-phase-de-démarrage), [recettes.md](recettes.md#relais-des-ressources-non-infinies)).
- **Cadence des pylônes** : 3 pôles verrouillés sont forcés dans la phase récursive et
  **ne fusionnent jamais** deux de leurs steps ([recettes.md](recettes.md#cadence-garantie-des-pylônes)) — même
  règle pour les armes ([combat.md](combat.md#combat-et-armement)).

L'assignation des armes montées (copie d'arme par véhicule, portée scalée, pool cachée)
est, elle, décrite dans [combat.md](combat.md#armes-montées-randomisées).

---

## Lectures associées

- **Parent** : [recettes.md](recettes.md) — la phase récursive.
- **Concepts liés** : [tech.md](tech.md) — arbre technologique et fin de partie ; [combat.md](combat.md) — combat et transports avancés ; [starter.md](starter.md) — la phase de démarrage.
