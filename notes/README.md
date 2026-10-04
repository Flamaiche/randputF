# Notes de release

Une note par version, nommée `vX.Y.Z.md` (le `v` compris, comme le tag).

Le fichier est **la** source de la note publiée sur GitHub. Au moment du tag,
`release.yml` lit `notes/v<version>.md` et publie exactement ce contenu, avec
le titre lu sur sa première ligne. Un fichier manquant fait échouer le
workflow bruyamment plutôt que de publier une release sans note.

## Écriture

- **Première ligne** : le titre de la release, au format
  `# <version> — <ce que la release apporte>`. Pas de nom de dépôt dans le
  titre : GitHub affiche déjà le dépôt, « randputF 1.0.2 » fait doublon.
- **Ensuite** : la note, format « highlights » (3-5 puces). Structure qui a
  servi pour la v1.0.1 : ce que c'est, changement notable + migration,
  déterminisme vérifiable, installation, documentation, garanties mesurées.
- Les faits viennent des docs, jamais inventés. Le témoin affiché est celui de
  la version publiée — il change à chaque bump de version.

## Portée de ce dossier

Il est **présent dans les tags** : le workflow de release fait son checkout sur
le tag et doit donc pouvoir lire la note. C'est le seul dossier du dépôt qui
voyage dans les tags sans être du produit.

`atelier/`, à l'inverse, est un journal de bord : il est versionné sur `dev`,
donc présent dans l'arbre de tout tag, sauf si on l'a retiré avant de taguer
(étape explicite de la checklist).

Il n'entre ni dans le wheel (`pyproject.toml` liste ses packages
explicitement) ni dans le zip du mod (qui ne contient que le mod généré).

## liens

- Gabarit et procedure : [`atelier/RELEASE.md`](../atelier/RELEASE.md).
- Historique des versions publiees : [`CHANGELOG.md`](../CHANGELOG.md).