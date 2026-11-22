# Nomenclature : le modèle de la seed et le rejoueur

Retour : [docs/README.md](README.md).

Le rejoueur lit une seed finale et simule la progression sans modifier le mod.
Cette page fixe le vocabulaire commun. Les garanties, l'implémentation, les
faits historiques et les corrections attendues sont séparés.

## État de la page

- Garantie actuelle : le rejoueur réutilise les identifiants de la seed.
- Implémentation actuelle : il lit recettes, technologies, carte, kit, épave et
  jalons tardifs sans écrire dans la seed.
- Fait historique : des écarts de vocabulaire ont déjà été corrigés sans
  changer les noms exportés.
- Spécification historique : elle demande de relier ce vocabulaire aux
  autres pages et de vérifier les liens.

## Ce que ça change pour le joueur

- Le rejeu vérifie qu'une seed déjà créée reste jouable.
- Le premier objet d'un patch d'item est ramassé à la main au spawn, avant tout
  contrôle d'extracteur.
- Une foreuse opérationnelle rend ensuite ce patch infini ; les lacs gardent
  leur pompe offshore.

## Mots à connaître

- [Rejeu](glossaire.md) — simulation de la progression sans Factorio.
- [Fake player](glossaire.md) — rejoueur Python qui tente les actions du joueur.
- [Slot](glossaire.md) — emplacement d'entrée ou de sortie.
- [Recette](glossaire.md) — règle de fabrication d'un objet.
- [Invariant](glossaire.md) — propriété attendue à chaque génération.

## Règles de vérification

- Une recette se lit avec ses ingrédients, ses résultats, son atelier et sa
  catégorie ; l'absence d'atelier indique un craft manuel.
- Le résultat d'une recette est appelé sortie côté rejoueur.
- Une tech apporte ses effets ; son déclencheur de prologue est fabriqué avant
  la chaîne des packs.
- La maîtrise est atteinte à dix fois la sortie de la recette ; elle reste
  propre au rejeu.
- `extractor_timing` fixe le déblocage des extracteurs pendant la génération ;
  le rejoueur ne lit pas ce champ.
- La victoire se déduit de la chaîne fusée du dump, sans nom d'item figé.
- Un nom de recette `randputf-*` ne désigne pas directement l'item produit : la
  correspondance passe par les résultats de la recette.
- Le rapport indique les items maîtrisés, jamais maîtrisables et la première
  technologie bloquée.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les identifiants de la seed sont réutilisés tels quels. | Le rejoueur ajoute un champ à la seed. |
| Le rejeu est une validation séparée de `generate`. | La commande `generate` lance le rejeu. |
| La victoire se déduit du dump. | Un nom d'item imposé côté rejoueur. |

## Aller plus loin

- [solvabilite.md](solvabilite.md) — à lire pour le rôle du rejeu face aux
  validateurs.
- [pipeline.md](pipeline.md) — à lire pour la construction de la seed.
- [vanilladb.md](vanilladb.md) — à lire pour les faits dérivés du dump.
- [seed.md](seed.md#seed-et-configuration-1) — à lire pour la graine active.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [glossaire.md](glossaire.md) — définitions courtes.
- [DEVIANCES.md](DEVIANCES.md) — écarts corrigés lors des audits.
