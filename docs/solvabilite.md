# Solvabilité : règles et vérification

Retour : [docs/README.md](README.md).

Une seed est retenue seulement quand le parcours reste possible jusqu'à la
fusée. Cette page sépare les contrôles bloquants, les diagnostics journalisés
et l'audit externe. Les faits anciens et les corrections demandées sont
indiqués à part.

## État de la page

- Garantie actuelle : `validate_seed` refuse les cycles, l'absence de
  progression et les exigences de victoire manquantes.
- Implémentation actuelle : `validate_pipeline` journalise son résultat ;
  `generate_with_retry` décide de la reprise.
- Fait historique : l'ancien `bootstrap_guard` réécrivait des recettes ; la
  génération ne l'utilise plus.
- Spécification historique : elle demande une page plus claire et plus
  courte ; cette réécriture suit cette demande.

## Ce que ça change pour le joueur

- Une seed acceptée offre une voie jusqu'au lancement de la fusée.
- Les cycles qui bloqueraient le départ sont refusés avant l'assemblage du mod.
- Les avertissements affichés pendant la génération ne changent pas la seed jouée.

## Mots à connaître

- [Validateur](glossaire.md) — contrôle appliqué à la seed ou au pipeline.
- [Invariant](glossaire.md) — propriété attendue à chaque génération.
- [Bootstrap](glossaire.md) — phase initiale qui rend le départ possible.
- [Rejeu](glossaire.md) — simulation de la progression sans Factorio.

## Vérificateur en profondeur (bootstrap sûr)

- L'oracle early définit ce qui est obtenable avant le réseau électrique.
- Le kit de crash reste un stock fini, pas une matière première fabriquable.
- Une recette early n'élargit ce périmètre que si son atelier est manuel ou à
  combustible.
- `find_cycles` sert aux tests ; il ne fait plus partie de la génération.

## Règles de solvabilité

Les règles ci-dessous s'appliquent à toute seed acceptée par le générateur.

- `_check_anti_cycle` est le contrôle anti-cycle bloquant : il refuse une
  chaîne de production qui dépend d'elle-même.
- La progressivité impose les prérequis avant chaque nouvel élément.
- `_check_completeness` vérifie toutes les exigences de victoire de la seed.
- `_check_victory_requirements` ne fait que repérer la recette
  `randputf-rocket-silo` dans le validateur de pipeline.
- `_check_packs_no_raw` écarte les ressources brutes des recettes de science
  pack.
- `_detect_unreachable_products` alimente les avertissements non bloquants de
  la règle des tuyaux.
- La triade chaleur est une tentative déterministe de `_ensure_heat_prereq`,
  pas un invariant absolu.

## Journalisation et reprise

- `validate_pipeline` journalise ses anomalies et ses avertissements ; il ne rejette
  aucune seed.
- `generate_with_retry` essaie la graine demandée, puis les valeurs suivantes,
  jusqu'à dix tentatives.
- Une seed retenue est ensuite assemblée ; les rapports HTML sont écrits après
  cette décision.
- Un épuisement des tentatives lève `SeedUnplayableError` et termine la
  commande avec le code 2.

## Rejoueur « fake player » (vérification par simulation)

- Le rejoueur lit la seed finale et simule la progression sans la modifier.
- Le premier objet d'un patch d'item est ramassé à la main au spawn, avant
  tout contrôle d'extracteur.
- Une foreuse opérationnelle rend ensuite ce patch infini ; les patchs fluides
  et les lacs gardent leurs contraintes d'extracteur.
- `extractor_timing` fixe le déblocage des extracteurs pendant la génération ;
  le rejoueur ne lit pas ce champ.
- Un audit externe a relevé 1501 victoires sur les graines 0 à 1500. Ce
  résultat n'est pas une garantie de `generate`.

## Complexité et profil de difficulté

- Le graphe, la complexité et la difficulté sont trois vues régénérables.
- Le profil agrège cinq axes ; le temps écoulé est exclu.
- Ces vues sont exclues du témoin de déterminisme.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| `validate_seed` bloque les seeds insolvables. | `validate_pipeline` rejette une seed. |
| La reprise essaie au plus dix graines. | Un audit externe réussi pour chaque graine. |
| La victoire complète est vérifiée par `_check_completeness`. | La triade chaleur comme invariant absolu. |

## Aller plus loin

- [invariants.md](invariants.md) — à lire pour la liste courte des invariants.
- [amorcage.md](amorcage.md) — à lire pour le départ avant le réseau électrique.
- [nomenclature-rejoueur.md](nomenclature-rejoueur.md) — à lire pour le vocabulaire du rejeu.
- [witness.md](witness.md) — à lire pour la reproductibilité de l'assemblage.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [glossaire.md](glossaire.md) — à lire dès qu'un terme est inconnu.
- [chaleur.md](chaleur.md) — à lire pour la tentative thermique déterministe.
