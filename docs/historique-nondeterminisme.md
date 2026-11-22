# Historique du non-déterminisme

Retour : [docs/README.md](README.md).

Cette page garde les diagnostics anciens du générateur. Elle ne décrit pas le
code actuel, qui est détaillé dans [nondeterminism.md](nondeterminism.md).
Garanties, implémentation, faits historiques et corrections attendues sont
séparés.

## État de la page

- Garantie actuelle : le déterminisme courant est décrit dans
  `nondeterminism.md`.
- Implémentation actuelle : les correctifs cités plus bas sont appliqués.
- Fait historique : les relevés de pools et les options A et B appartiennent au
  diagnostic.
- Spécification historique : elle demande de garder les archives
  distinctes de l'état courant et de vérifier les liens entre pages.

## Ce que ça change pour le joueur

- Les incidents décrits ici ne se produisent plus dans la version courante.
- Une même graine redonne aujourd'hui le même monde.
- Cette page explique pourquoi certains contrôles existent.

## Mots à connaître

- [RNG](glossaire.md) — générateur aléatoire piloté par la graine.
- [Pool](glossaire.md) — ensemble fini de candidats au tirage.
- [Seed](glossaire.md) — graine qui fixe les tirages.
- [Témoin](glossaire.md) — empreinte du mod assemblé.

## Règles de vérification

- Les archives relatent des comparaisons de `seed.json` entre processus.
- Elles identifient l'ordre d'itération des ensembles non triés comme cause.
- Elles ne fixent pas le nombre de tests de la suite courante.
- Le diagnostic lié à la graine 1269 n'est pas présenté comme un test actif.
- Le test courant de la graine 1757 appartient à `test_late_raws.py`.

## Faits historiques

- Deux exécutions avec la même graine pouvaient produire des `seed.lua`
  différents.
- La cause racine venait d'un `frozenset` de la chaîne fusée converti en liste.
- Les fluides de générateur et les effets de tech étaient tirés depuis des
  ensembles non triés.
- Une copie superficielle de la configuration laissait fuir `deferred` d'une
  graine vers la suivante.
- Les tailles de pools relevées à l'époque et l'option d'index dans la seed
  n'ont pas été retenues.
- Les totaux de 71 puis 722 tests appartiennent aux jalons anciens.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les archives conservent la chronologie des correctifs. | Leur état reflète le code courant. |
| Les causes identifiées expliquent les contrôles actuels. | Les chiffres anciens sont des garanties. |
| Les liens renvoient vers l'état courant. | Le test d'ordre 1269 est dans la suite. |

## Aller plus loin

- [nondeterminism.md](nondeterminism.md) — à lire pour l'état courant.
- [witness.md](witness.md) — à lire pour le md5 du mod assemblé.
- [seed.md](seed.md#seed-et-configuration-1) — à lire pour la graine active.
- [pipeline.md](pipeline.md) — à lire pour les flux RNG.

## Lectures associées

- **Parent** : [nondeterminism.md](nondeterminism.md) — état courant du
  déterminisme.
- [docs/README.md](README.md) — index de la documentation.
- [release.md](release.md) — à lire pour l'état des versions.
