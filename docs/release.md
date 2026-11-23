# Release : procédure et état

Retour : [docs/README.md](README.md).

La publication part de la branche `dev` et se déclenche sur `master`. Le workflow lit la version, vérifie la note, teste le projet, construit le mod puis crée le tag. Le titre et le corps de la release viennent de `notes/v<version>.md`.

## Ce que ça change pour l'utilisateur

- Une release publiée porte un tag `v<version>` et une note dédiée.
- Le workflow vise un zip contenant le mod, sans les trois vues HTML ; sa source doit encore être alignée.
- Le mod peut aussi être produit localement avec `generate`.

## Mots à connaître

- [témoin](glossaire.md) — empreinte de reproductibilité de la seed 5.
- [artefact](glossaire.md) — fichier généré, jamais suivi dans git.
- [promotion](glossaire.md) — passage de `dev` vers `master`.
- [note de release](glossaire.md) — fichier qui porte le titre et les points saillants.

## Fonctionnement

### État des versions

| Version | État | Témoin de la seed 5 |
|---|---|---|
| v0.0.0 | publiée, Factorio 2.0 | `f41e065e606ce24c8855d458c661988f` |
| v0.0.1 | publiée, Factorio 2.0 | `c9566134864507d900f65806ade277d9` |
| v0.0.2 | en préparation, Factorio 2.1 | `e61667692c486e5b9c30efa9f4fbc891` |

La suite courante compte 873 tests. Les valeurs des versions publiées restent des faits historiques. Elles ne décrivent pas l'état courant.

### Ce que fait le workflow

1. Il lit la version dans `mod/info.json` et exige `notes/v<version>.md`.
2. Il refuse la publication si le tag `v<version>` existe déjà sur l'origine.
3. Il installe le paquet avec ses extras de développement.
4. Il lance `pytest -q`. Une suite rouge bloque la release.
5. Il lance `randputf witness --seed 5`.
6. Il lance `randputf generate --seed 5 --out /tmp/modrel`.
7. Il construit `/tmp/randputF_${VERSION}.zip` en excluant les trois fichiers HTML.
8. Il crée le tag sur le commit promu et le pousse.
9. Il téléverse le zip avec `gh release upload`, ou le crée avec `gh release create`.

Le titre est la première ligne de la note, sans le préfixe de titre Markdown. Le reste du fichier sert de corps. Le workflow met aussi à jour un brouillon résiduel avec `--draft=false`.

### Checklist avant promotion

1. Bumper `mod/info.json` et `pyproject.toml` en même temps.
2. Recalculer le témoin avec `randputf witness --seed 5`, puis le reporter dans `.github/workflows/ci.yml` et dans [witness.md](witness.md).
3. Créer `notes/v<version>.md` avec un titre puis trois à cinq puces.
4. Ajouter la section `## v<version>` dans `CHANGELOG.md` dans le même commit.
5. Supprimer un brouillon GitHub résiduel pour cette version.
6. Relancer les tests depuis un arbre propre, sans `output/`, `randputF_*` ni `mod-list.json` résiduels.
7. Pousser `dev` vers `master` seulement sur décision du mainteneur.

`.gitattributes` exclut `atelier/` des archives. `pyproject.toml` énumère explicitement les paquets du wheel. Aucun artefact généré n'est suivi dans git.

### Numérotation

Le semver reprend ses droits après la v0.0.1. Un changement visible prend un numéro mineur. Une correction de documentation ou de test prend un numéro de patch. Le réemploi du numéro v0.0.1 vient d'un brouillon jamais publié, puis supprimé.

### Chemin du zip

Le workflow génère le mod dans `/tmp/modrel/randputF_${VERSION}`. La commande zip lit exactement ce dossier et produit `/tmp/randputF_${VERSION}.zip`, sans les trois vues HTML. Le contenu de l'artefact doit rester conforme au témoin de la seed générée.

D'anciens documents affirmaient qu'aucun zip n'était attaché à la release ou décrivaient une source de zip différente du dossier généré. Ces deux formulations sont obsolètes.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| La note de release est obligatoire pour publier. | Un brouillon résiduel peut porter une date périmée. |
| La suite de tests bloque une publication rouge. | Le zip publié dépend du chemin exact utilisé par le script. |
| Les vues HTML sont exclues de l'archive de release. | Les documents historiques décrivent parfois l'ancien comportement. |

## Aller plus loin

- [witness.md](witness.md) — à lire quand le témoin doit être recalculé.
- [CHANGELOG.md](../CHANGELOG.md) — à lire quand l'historique des versions est consulté.
- [notes/README.md](../notes/README.md) — à lire quand la note publiée est recherchée.
- [graphe-interactif.md](graphe-interactif.md) — à lire quand le sort des vues HTML est vérifié.
- [config.md](config.md) — à lire quand un changement de défaut est préparé.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [modules.md](modules.md) — commandes et outils disponibles.
- [developpement.md](developpement.md) — préparation de l'environnement.
- [etat-code.md](etat-code.md) — état courant des composants.
