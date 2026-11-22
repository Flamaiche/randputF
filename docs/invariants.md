# Les invariants de solvabilité

Retour : [docs/README.md](README.md).

Cette page donne la liste courte des propriétés de solvabilité. Le détail des
contrôles reste dans [solvabilite.md](solvabilite.md). Les faits anciens et les
corrections demandées sont séparés des garanties actuelles.

## État de la page

- Garantie actuelle : seuls les contrôles de `validate_seed` bloquent une seed.
- Implémentation actuelle : `validate_pipeline` journalise ses constats sans
  rejeter la seed.
- Fait historique : cette page portait autrefois le détail complet des règles.
- Spécification historique : elle suggère de la fusionner dans
  `solvabilite.md` ; l'ancre `Règles de solvabilité` reste disponible.

## Ce que ça change pour le joueur

- Le départ reste possible avant le réseau électrique.
- La voie vers la fusée reste complète pour une seed acceptée.
- Un avertissement du pipeline n'empêche pas le lancement d'une partie.

## Mots à connaître

- [Invariant](glossaire.md) — propriété attendue à chaque génération.
- [Validateur](glossaire.md) — contrôle qui vérifie cette propriété.
- [Bootstrap](glossaire.md) — phase initiale du monde généré.
- [Rejeu](glossaire.md) — vérification séparée de la progression.

## Règles de solvabilité

- Anti-cycle : `_check_anti_cycle` refuse les boucles de production.
- Progressivité : chaque élément attend ses prérequis.
- Complétude : `_check_completeness` couvre toutes les exigences de victoire.
- Victoire du pipeline : `_check_victory_requirements` ne vérifie que la
  présence de `randputf-rocket-silo`.
- Science packs : `_check_packs_no_raw` interdit les ressources brutes.
- Tuyaux : `_detect_unreachable_products` produit des avertissements non
  bloquants.
- Triade chaleur : tentative déterministe de `_ensure_heat_prereq`, sans
  garantie absolue.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Une seed acceptée passe `validate_seed`. | Un avertissement de `validate_pipeline` bloque la seed. |
| Les cycles de production sont signalés comme bloquants. | La triade chaleur est toujours présente. |
| Le vocabulaire est décrit dans [nomenclature-rejoueur.md](nomenclature-rejoueur.md). | Le rejeu fait partie de `generate`. |

## Aller plus loin

- [solvabilite.md](solvabilite.md) — à lire pour les contrôles détaillés.
- [amorcage.md](amorcage.md) — à lire pour les premières recettes jouables.
- [chaleur.md](chaleur.md) — à lire pour la tentative thermique.
- [testeur.md](testeur.md) — à lire pour lancer un contrôle sur une seed.

## Lectures associées

- **Parent** : [solvabilite.md](solvabilite.md) — règles et vérification.
- [docs/README.md](README.md) — index de la documentation.
- [ressources.md](ressources.md) — ressources au sol.
