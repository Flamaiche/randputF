# Description des branches (randputF)

Ce fichier explique à quoi sert chaque branche du dépôt. Il est mis à jour
sur chaque branche pour refléter son objectif propre.

## Branche actuelle : `doc`

**Objectif : revoir et refaire toute la documentation.**

- Mettre à jour tous les fichiers de `docs/` pour les rendre précis,
  lisibles et actionnables (pas de généralités, pas de gros pavés).
- Corriger les divergences entre le code et la documentation
  (`nondeterminism.md`, `config.md`, `architecture.md`, etc.).
- Compléter les contrats de module (`VanillaDB`, `EarlyOracle`,
  `ProgressionState`, phases du pipeline, runtime Lua, etc.).
- Garantir que le témoin de déterminisme reste cohérent.

## Autres branches

| Branche | Objectif |
|---------|----------|
| `dev` | Travail en cours du code (générateur, pipeline, Lua, tests). |
| `master` | Historique intégré, releases taguées (`v1.0.0`, `v1.0.1`). |
| `doc-restructure` | Restructuration de l'arbre de lecture des docs. |
| `feature/exporter-auto-select` | Correction de l'auto-sélection des fours (déjà résolu). |
| `feature/1.1.0` | Préparation de la version 1.1.0 (craft, moyens, etc.). |

## Convention

Chaque branche possède sa propre copie de ce fichier (ou le met à jour)
pour indiquer clairement à quoi elle sert, afin d'éviter les écarts entre
ce qui est annoncé et ce qui est réellement fait sur la branche.
