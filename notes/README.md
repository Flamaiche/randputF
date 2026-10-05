# Notes de release

Rédige une note par version. Nomme le fichier `vX.Y.Z.md`, avec le `v` initial comme pour le tag.

Ce fichier est la source unique de la note publiée sur GitHub. Au moment du tag, `release.yml` lit `notes/v<version>.md` et publie exactement ce contenu, en utilisant la première ligne comme titre. Si le fichier manque, le workflow échoue de manière bloquante plutôt que de publier une release sans note.

## Écriture

- **Première ligne** : le titre de la release, au format `# <version> — <ce que la release apporte>`. N'ajoute pas le nom du dépôt dans le titre : GitHub l'affiche déjà, écrire « randputF 1.0.2 » ferait doublon.
- **Ensuite** : la note, au format « highlights » (3-5 puces). Reprends la structure de la v1.0.1 : présentation du projet, changement notable et migration, déterminisme vérifiable, installation, documentation, garanties mesurées.
- **Contenu** : base-toi uniquement sur les faits documentés, sans rien inventer. Le témoin affiché correspond à la version publiée et change à chaque bump de version.

## Portée de ce dossier

Ce dossier est présent dans les tags. Le workflow de release fait son checkout sur le tag et doit pouvoir y lire la note. Comme `atelier/`, ce dossier voyage dans les tags sans faire partie du produit distribué : il est nécessaire au déploiement, et ne fait pas partie de ce qu'un joueur installe.

À l'inverse, `atelier/` sert de journal de bord. Il n'est pas distribué : il n'entre ni dans le wheel (`pyproject.toml` liste ses packages explicitement) ni dans le zip du mod, qui contient uniquement le mod généré.

## Liens

- Gabarit et procédure : [`docs/release.md`](../docs/release.md).
- Historique des versions : [`CHANGELOG.md`](../CHANGELOG.md).
