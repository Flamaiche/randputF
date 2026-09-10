# PLAN — Bootstrap « vérifié à la création » (redesign de la passe de rattrapage)

## Objectif

Supprimer la passe de rattrapage post-hoc `bootstrap_guard` (REPLACE/ADD par
point fixe) au profit d'une vérification **à la création** (correct-by-construction) :
chaque recette de produit **promis** par les techs gratuites est contrainte au
moment du bake (atelier non-élec + ingrédients ⊆ watershed pré-élec courant).
Le validateur §15 reste en assertion finale.

Directive utilisateur permanente : **ne plus modifier la génération en dur**
(`force_early_heat_source` reste totalement absent).

## Décisions validées par l'utilisateur (mode plan)

1. **Contraindre le tirage** : quand une phase profonde veut re-baker un produit
   promis en recette électrique, re-tirer la recette avec atelier non-élec +
   ingrédients du watershed courant ; si pool insatisfaisable → conserver la
   recette safe existante.
2. **NET≤0 / SCC → diagnostics uniquement** : l'atteignabilité pré-élec suffit
   pour la finissabilité (chaque promis craftable isolément) ; le critère
   rendement net ≤ 0 n'est plus un gate de correction.
3. Fichier plan : `PLAN_bootstrap_inline.md` à la racine du dépôt.

## Faits d'architecture établis

- Les `starter.tech_steps` (donc les produits promises) sont **gelés** après
  `pipeline.py:95` (`build_tech_steps`, après électricité, avant la phase
  récursive).
- Dédup (`ensure_obtainable`/`make_recipe`, recipes.py:157-164/198-204)
  empêche la plupart des re-bakes.
- Seul re-bake « inconscient » identifié : `_make_fixed_fluid_recipe`
  (recursive_phase.py:1005-1061) — sortie fluide de lac/patch promis, entrée
  patch fluide électrique (cas seed 13 « fluide de patch »).
- `max_iterations=8`, `ingredient_min/max` 1-4, préfixe `randputf-bootsafe-`.

## Contradiction à lever (étape 1, spike de provenance)

Les primaires *items* promises (landfill, pipe, turbine…) sont actuellement
profondes dans les seeds finales, alors qu'aucun site item ne devrait les
re-baker — d'où le traçage empirique prévu (lequel appels produisent
`randputf-<promis>`).

## Étapes

1. **Spike de provenance** : instrumenter `_bake_recipe` pour tracer quels
   appels produisent `randputf-<promis>` (landfill, pipe, turbine…) ; lever la
   contradiction dédup/empirique.
2. **Gel des promesses** : snapshot des produits des techs gratuites au moment
   du bake (`pipeline.py:95`).
3. **EarlyOracle** : oracle verticalisé — watershed pré-élec courant
   (ingrédients + ateliers non-élec). (Réutiliser/verticaliser
   `build_early_sources`/`compute_early_reachable`.)
4. **Contrainte au bake** : si une phase profonde veut re-baker un produit
   promis en recette électrique → re-tirage non-élec ingrédients ⊆ watershed ;
   pool insatisfaisable → conserver la recette safe existante (1 seule).
5. **Suppression du réparateur** : retirer `run_bootstrap_guard`,
   `find_cycles`, `find_bootstrap_gaps`, `_make_safe_recipe`…
   (garder les diagnostics si utile), `replace_first` dans settings.yaml,
   prototypes `bootstrap_guard`.
6. **Tests** : adapter `tests/test_bootstrap_guard.py` — asserter 0 recette
   `randputf-bootsafe-*` et 0 tech `randputf-starter-bootsafe` sur 20 seeds ;
   suite complète verte.
7. **Seed 13 & docs** : régénérer/resync `mod/` = `output/` = installé ; réécrire
   §10ter du README (« vérifié à la création ») ; validateur §15 conservé tel
   quel en assertion finale.

## Risque à acter

Le redesign change le contenu des primaires promises (seed 13 modifiée de
nouveau, sauvegardes avancées impactées).