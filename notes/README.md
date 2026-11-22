# Notes de release

Une note est rédigée par version dans un fichier `vX.Y.Z.md`, avec le `v`
initial comme pour le tag. Ce dossier contient les notes de release préparées
ou publiées : `v0.0.1.md` est la note historique de la v0.0.1 (Factorio 2.0,
722 tests, témoin `c9566134864507d900f65806ade277d9`) ; `v0.0.2.md` prépare la
version courante, dont le témoin doit être recalculé au bump de version.
L'état courant et la procédure de publication sont décrits dans
[`docs/release.md`](../docs/release.md).

Chaque `vX.Y.Z.md` est la source de la note publiée sur GitHub. Au moment du tag,
`release.yml` lit `notes/v<version>.md` et publie exactement ce contenu, en
utilisant la première ligne comme titre. Si le fichier manque, le workflow échoue
de manière bloquante plutôt que de publier une release sans note.

## Règles de rédaction

- **Première ligne** : le titre de la release, au format
  `# <version> — <ce que la release apporte>`. Le nom du dépôt est omis : GitHub
  l'affiche déjà.
- **Ensuite** : la note au format « faits saillants » (3 à 5 puces). La structure de
  la v0.0.1 sert de référence : présentation du projet, changement notable et
  migration, déterminisme vérifiable, installation, documentation, garanties
  mesurées.
- **Contenu** : seuls les faits documentés de la version publiée sont repris.
  Le témoin affiché correspond à cette version et change à chaque bump.

## Portée du dossier

Ce dossier est présent dans les tags. Le workflow fait son checkout sur le
commit `master` promu (le tag est créé ensuite) et lit la note depuis ce
checkout. Comme `atelier/`, ce dossier voyage
dans les tags sans faire partie du produit distribué : il est nécessaire au
déploiement, et ne fait pas partie de ce qu'un joueur installe.

`atelier/` contient les plans et les idées non livrés. Il n'est pas distribué :
il n'entre ni dans le wheel (`pyproject.toml` liste ses paquets explicitement)
ni dans le mod assemblé. Aucun artefact généré n'est suivi dans git.

## Liens

- Gabarit et procédure : [`docs/release.md`](../docs/release.md).
- Historique des versions : [`CHANGELOG.md`](../CHANGELOG.md).
- Note publiée : [`v0.0.1.md`](v0.0.1.md).
- Note en préparation : [`v0.0.2.md`](v0.0.2.md).
