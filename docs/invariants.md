# Les invariants de solvabilité

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

> **Cas partagé** : ces règles sont invoquées par [recettes.md](recettes.md) (génération),
> [tech.md](tech.md) (arbre), [starter.md](starter.md) (départ) et
> [ressources.md](ressources.md) (patches). Elles sont **énoncées ici une seule fois** ;
> la **vérification** (oracle early, rejoueur) vit dans [solvabilite.md](solvabilite.md).

## Règles de solvabilité

Cinq invariants majeurs, plus deux vérifications complémentaires, tous vérifiés par le
tool externe avant validation d'une seed (`pipeline_validator.py`) :

1. **Anti-cycle** : aucun maillon ne peut dépendre de sa propre production.

   Toute entrée auxiliaire d'un bâtiment provient d'une branche déjà valide ; les tuyaux
   d'un fluide requis peuvent être faits de ce fluide ou d'une autre ressource, jamais de
   la ressource qui en a besoin (règle des tuyaux, [starter.md](starter.md#la-chaîne-initiale-starter)).

   La vérification se fait au niveau **item** par point fixe (`_detect_unreachable_products`) :
   un item est solvable dès que **l'une** de ses recettes l'est. Les recettes relais
   ([recettes.md](recettes.md#relais-des-ressources-non-infinies)) sont des routes alternatives, pas des doubles-arêtes
   cycliques : un aller-retour `relais-A → bootstrap-B → relais-A` n'est pas une boucle
   bloquante tant que chaque item de la paire reste solvable par une autre route.
2. **Progressivité** : chaque nouveau maillon (recette, bâtiment, combustible, ressource)
   n'est ajouté que si ses prérequis sont satisfaits par le pool atteignable — ou rendus
   satisfaits immédiatement par déblocage sur le tas ([amorcage.md](amorcage.md#les-règles-damorçage)),
   lui-même soumis à la règle 1.
3. **Complétude** : la chaîne générée mène nécessairement à tous les composants requis par
   le lancement de fusée (les 3 ingrédients de `rocket-part` ET le rocket-silo générés et
   unlockés, [tech.md](tech.md#fin-de-partie)) ; les coûts de recherche en matériaux sont couverts
   par la progression (chaque pack de coût possède une recette unlockée avant la tech qui
   le consomme, [tech.md](tech.md#larbre-technologique)).
4. **Unlock unique** : toute recette de la seed est déblocable par **au moins une** tech et
   **une seule**. Les phases peuvent réclamer plusieurs fois la même `randputf-<item>` :
   au montage de l'arbre, seule la **première** tech qui la revendique compte — l'invariant
   est garanti par construction, pas par chance ([tech.md](tech.md#larbre-technologique)).
5. **Packs sans ressource brute** : aucune recette de science pack ne consomme une
   ressource brute (patch au sol, item environnemental récolté à la main, fluide
   d'extraction — infinis ou non, [ressources.md](ressources.md#les-ressources-au-sol) et
   [tech.md](tech.md#larbre-technologique)). Vérifié en fin de pipeline sur les recettes de la graine
   (`_check_packs_no_raw`), en plus de l'exclusion appliquée au tirage par la génération.
6. **Cohérence tech-recettes** (warning) : chaque recette créée par le pipeline apparaît
   dans les effects d'exactement UNE tech — pas de recette orpheline (jamais débloquée) et
   pas de double déblocage. Les orphelins émettent un warning plutôt qu'une erreur
   (certaines recettes créées « sur le tas » sont disponibles dès le début sans unlock
   explicite).
7. **Coûts obtainables** : les matériaux de recherche de chaque tech payante doivent être
   produibles par le joueur au moment de sa place dans l'arbre. Simulation de la
   progression : on parcourt les techs dans l'ordre, on ajoute les produits débloqués au
   pool, et on vérifie que chaque coût est couvert.

Une seed qui viole l'un de ces invariants est rejetée et régénérée par le tool, jamais
livrée au joueur. La **vérification** de ces invariants (oracle early, diagnostic
`bootstrap_guard`, rejoueur « fake player ») est décrite dans
[solvabilite.md](solvabilite.md).

---

## Lectures associées

- **Parent** : [solvabilite.md](solvabilite.md) — vérifications de solvabilité.
- **Concepts liés** : [recettes.md](recettes.md) — la phase récursive ; [tech.md](tech.md) — arbre technologique et fin de partie ; [starter.md](starter.md) — la phase de démarrage ; [ressources.md](ressources.md) — les ressources au sol.
