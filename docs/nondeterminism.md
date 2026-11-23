# Non-déterminisme — état courant

Retour : [docs/README.md](README.md).

Le générateur est déterministe pour un même dump, une même configuration et une
même graine. Cette page décrit l'état courant ; les incidents anciens sont dans
les archives. Garanties, implémentation, faits historiques et corrections
attendues sont séparés.

## État de la page

- Garantie actuelle : deux exécutions avec la même entrée produisent la même
  seed.
- Implémentation actuelle : les flux RNG sont préfixés et les ensembles sont
  triés.
- Fait historique : l'ordre d'un `frozenset` de la chaîne fusée décalait les
  tirages.
- Spécification historique : elle demande une refonte d'ensemble ; les
  affirmations sans test présent sont retirées.

## Ce que ça change pour le joueur

- Une même graine redonne le même monde, quel que soit `PYTHONHASHSEED`.
- Deux graines générées dans un même processus ne dépendent pas de leur ordre.
- Le mod assemblé est vérifié par le témoin, pas par le test de seed.

## Mots à connaître

- [RNG](glossaire.md) — générateur aléatoire contrôlé par la graine.
- [Seed](glossaire.md) — graine qui fixe tous les tirages.
- [Pool](glossaire.md) — ensemble fini de candidats.
- [Témoin](glossaire.md) — empreinte du mod assemblé.
- [Canonisation](glossaire.md) — normalisation avant hachage.

## Règles de génération

- `make_seeded_rng` dérive chaque flux d'une chaîne qui contient la graine.
- Les phases utilisent des préfixes distincts et constants.
- Les cibles de la chaîne fusée sont triées avant tirage.
- Les fluides de lacs et les effets de tech sont triés avant d'alimenter un
  tirage.
- La configuration de la passe B est copiée avant son emploi.
- Les planifications late raws exportées sont triées.

## Contrôles courants

- `tests/test_determinism.py` paramétrise les graines 1337 et 1299.
- Le test compare `seed.json` octet par octet sous deux valeurs de
  `PYTHONHASHSEED`.
- Le test de la graine 1757 est dans `test_late_raws.py`.
- Aucun test d'ordre dédié à la graine 1269 n'est conservé dans la suite
  courante.
- La suite compte 873 tests.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Deux générations identiques produisent la même seed. | Le mod assemblé est couvert par ce test. |
| Les flux préfixés et les ensembles triés stabilisent les tirages. | Un test d'ordre 1269 dans la suite courante. |
| Les tests couvrent 1337, 1299 et 1757. | Une preuve exhaustive sur toutes les graines. |

## Aller plus loin

- [historique-nondeterminisme.md](historique-nondeterminisme.md) — à lire pour
  les diagnostics anciens.
- [witness.md](witness.md) — à lire pour le déterminisme de l'assemblage.
- [seed.md](seed.md#seed-et-configuration-1) — à lire pour la valeur de la
  graine.
- [pipeline.md](pipeline.md) — à lire pour l'ordre des flux RNG.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [glossaire.md](glossaire.md) — à lire dès qu'un terme est inconnu.
- [etat-code.md](etat-code.md) — à lire pour l'état des composants.
