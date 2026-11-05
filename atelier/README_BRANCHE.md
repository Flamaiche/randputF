# Description des branches (randputF)

Ce fichier explique à quoi sert chaque branche du dépôt. Il est mis à jour
sur chaque branche pour refléter son objectif propre.

## Branche actuelle : `feature/craft-moyens`

**Objectif : nombre de craft et moyens (ressources, bâtiments, flux), plus
les outils d'analyse associés.**

### Fait

- **Rapport de complexité** (`tool/exporters/complexity_graph.py`) :
  `seed.complexity.html` autonome (SVG généré en Python, aucun CDN) écrit à
  côté de `seed.json` par `randputf generate --out`.
  - courbes par tech : temps de recherche, ressources brutes, ateliers
    distincts, ratio ressources / atelier ;
  - modèle joueur : packs de science de chaque tech dépliés jusqu'aux
    `pools.raw_resources`, crafts comptés par `crafted_in` ;
  - résumé : score de complexité, temps de craft total, temps de recherche,
    fabricateur le plus utilisé, ressource la plus consommée.
- **Vitesses de craft** : `BuildingDef.crafting_speed` / `productivity`
  (lues dans le dump). Repli vanilla dans le rapport tant que le dump ne les
  contient pas.
- **Exporteur** (`exporter/`) remis dans son état fonctionnel :
  `category` sondé sans erreur (2.1), `crafting_speed` et `productivity`
  ajoutés au JSON, code mort supprimé, `factorio_version` = 2.1.

### À faire

- Régénérer `data/vanilla_dump.json` avec le nouvel exporteur pour que les
  vitesses réelles remplacent le repli vanilla.
- Comparer les courbes seed du mod / vanilla / modpack lent (Pyanodons).
- Poursuivre le travail craft/moyens (poids des recettes, équilibrage).

## Autres branches

| Branche | Objectif |
|---------|----------|
| `dev` | Travail en cours du code (générateur, pipeline, Lua, tests). |
| `master` | Historique intégré, releases taguées (`v0.0.0`, `v0.0.1`). |
| `doc` | Relecture et correction de la documentation. |
| `feature/exporter-auto-select` | Correction de l'auto-sélection des fours (déjà résolu). |
| `feature/0.1.0` | Préparation de la version 0.1.0 (craft, moyens, etc.). |

## Convention

Chaque branche possède sa propre copie de ce fichier (ou le met à jour)
pour indiquer clairement à quoi elle sert, afin d'éviter les écarts entre
ce qui est annoncé et ce qui est réellement fait sur la branche.
