# Travail sur cette branche : `feature/craft-moyens`

Quand vous arrivez sur cette branche, lisez ce fichier en priorité pour savoir quoi faire.

## Objectif

Travailler sur **le nombre de craft et les moyens** (ressources, bâtiments, flux, équilibrage).

## À faire (ordre indicatif)

1. **Inventaire actuel** : lister tous les crafts existants (recettes, bâtiments, inputs/outputs) dans `tool/generator/recipes.py`, `tool/generator/recursive_phase.py`, `mod/data.lua`.
2. **Nombre de craft** : définir / ajuster le nombre de crafts par ressource, par bâtiment, par phase (starter, récursif, endgame).
3. **Moyens** : vérifier que chaque craft a un bâtiment capable (atelier, extracteur, générateur, etc.) et que les moyens de production sont cohérents avec la demande.
4. **Équilibrage** : s'assurer qu'aucun craft n'est bloquant ou surpuissant ; ajuster les poids, les coûts, les déblocages.
5. **Tests** : ajouter / mettre à jour les tests de pipeline pour valider les nouveaux crafts et moyens.
6. **Doc** : mettre à jour `docs/recettes.md`, `docs/ressources.md`, `docs/tech.md` si le comportement change.

## Règles

- Ne pas toucher au témoin de déterminisme (`v1.0.0`, `v1.0.1`) sauf si un test dédié le valide.
- Tout changement de recette ou de bâtiment doit passer par la CI (tests + rejoueur).
- Si une divergence avec `docs/` apparaît, la corriger sur cette branche ou ouvrir une issue sur `doc`.
