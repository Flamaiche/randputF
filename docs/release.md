# Release : procédure et état

Ce document décrit la procédure de publication et l'état d'avancement des versions.

La note publiée réside dans [`notes/v<version>.md`](../notes/) : c'est ce fichier que `release.yml` publie (titre = première ligne). Cette page ne contient pas la note, elle expose sa production et son emplacement.

Les brouillons de travail (plans, idées, notes de révision) se trouvent dans `atelier/`. Ce dossier est versionné — sauvegardé, historisé et partagé — mais exclu de tout livrable : `.gitattributes` le marque `export-ignore`, le rendant absent de `git archive`, des zip « Source code » de GitHub, du wheel (`pyproject.toml` énumère ses paquets explicitement) et du zip de release. Règle : `atelier/` vit dans le dépôt, jamais dans le produit. La documentation, elle, se place ici, dans `docs/`.

Retour : [README.md](../README.md).

---

## 1. État des versions

Publiée — accessible publiquement, tag sur `master` :

| Version | Tag | Contenu | Témoin seed 5 |
|---|---|---|---|
| v1.0.0 | `v1.0.0` → `f94f471` | Première release publique. Config `settings.yaml`. | `12ac143e06174df126537b978ff928d3` |

En préparation — sur `dev`, non publiée :

| Version | Note | Contenu | Témoin seed 5 |
|---|---|---|---|
| v1.0.1 | [`notes/v1.0.1.md`](../notes/v1.0.1.md) | Config à deux YAML + refonte documentaire. | `ce428c2140ec7031f9604637ecf70cbc` |

Le mécanisme des notes apparaît avec la v1.0.1 : `release.yml` lit `notes/v<version>.md` (titre = première ligne, reste = note « highlights »). Il n'existe **pas** de note v1.0.0 — cette release a été publiée sans le mécanisme de notes, et le dossier `notes/` n'existait pas à son tag. Une note posée est ensuite gelée : elle décrit l'état de son tag, ne la modifie pas.

Réutilisation du numéro 1.0.1 : une première v1.0.1 a été préparée le 2026-10-01, sans être publiée — elle est restée en *draft* sur GitHub, et son tag a été supprimé lors du reset de `master`. Aucune donnée n'ayant été publique sous ce numéro, son réemploi ne trompe personne, ce qui a été fait. Le brouillon résiduel a été supprimé : la release v1.0.1 sera créée de zéro par le workflow (chemin `create`), et non reprise d'un brouillon obsolète en date et en corps. Un `draft` réapparu pour cette version signale un reliquat : supprime-le avant le tag (cf. checklist §3).

Écart assumé sur la numérotation : la configuration à deux YAML constitue un changement visible par l'utilisateur (un fichier supprimé, des surcharges à recopier), relevant de `1.1.0` au sens semver. La version sort en v1.0.1, sur décision du mainteneur. Convention retenue pour la suite : le semver reprend ses droits — un changement visible par l'utilisateur prend un chiffre mineur (1.1.0), un correctif de documentation ou de test un numéro de patch.

## 2. Release v1.0.1 : EN PRÉPARATION

Elle intègre le système de configuration à deux YAML et la refonte documentaire. Sa sortie interviendra au tag `v1.0.1`, créé par le workflow au moment où `master` reçoit le travail de `dev` (cf. §3 — il ne s'agit pas d'un merge, voir l'encadré).

### 2.1 Titre et note

Le titre et la note figurent dans [`notes/v1.0.1.md`](../notes/v1.0.1.md) — première ligne = titre, reste = note « highlights ». `release.yml` les publie tels quels ; ne les recopie pas ici.

```
1.0.1 — Le mod ne change pas. Tout ce qui l'entoure, oui.
```

### 2.2 Faits vérifiés (pour ne rien inventer dans la note)

- Témoin seed 5 de la v1.0.1 : `ce428c2140ec7031f9604637ecf70cbc`. Il change au bump de version (préfixe racine du zip `randputF_<version>`) alors que le contenu du mod pour la seed 5 reste inchangé depuis la v1.0.0. Ne reprends jamais l'ancien md5 tel quel.
- Tests : 722.
- Fichiers de config : `config/settings.yaml` (supprimé) -> `config/defaults.yaml` + `config/user.yaml`.
- Sources pour le détail : `docs/DEVIANCES.md` (bugs/bilan seed par seed), `docs/solvabilite.md` (preuves 1501/1501, invariants §15), `docs/nondeterminism.md` (déterminisme), `config/user.yaml` (surcharges).

## 3. Checklist de publication (procédure)

Le bump de version s'effectue dans `dev` (seule branche de travail) : `mod/info.json` (source de vérité) et `pyproject.toml` simultanément — `tool/common/version.py` lit `mod/info.json`, il ne se bump pas.
La release correspond à la promotion `dev` → `master`, décidée par le mainteneur.

> La release est la promotion `dev` → `master`. Le workflow se déclenche quand `master` reçoit le travail de `dev` ; il lit la version dans `mod/info.json`, construit le mod, crée le tag `v<version>` sur le commit promu et publie. Aucun tag manuel n'est requis. Le tag v1.0.0 (`f94f471`) constitue un commit racine sans parent, de sorte que `master` et `dev` n'ont actuellement aucun ancêtre commun et `master` se replace sur `dev` via `git push origin dev:master --force`. Dès cette première promotion, les deux branches redeviennent parent-enfant : les promotions suivantes s'exécutent en *fast-forward*, sans `--force`. Conséquence à retenir : le commit v1.0.0 reste accessible par son tag, mais sort de l'ascendance de `master`.

- [ ] Tout passer par `dev` : corrections, docs, bump de version sur `dev`.
- [ ] Version : bump de `mod/info.json` `"version"` — source de vérité lue par `tool/common/version.py` — et de `pyproject.toml`, au même moment.
- [ ] Témoin : le md5 du témoin dépend de la version (préfixe racine `randputF_<version>` dans le zip, cf. `tool/common/witness.py`) -> le bump de version change le témoin. Recalcule le nouveau md5 (`randputf witness --seed 5`) et mets-le à jour dans `.github/workflows/ci.yml` et `docs/witness.md`.
- [ ] Note de release : crée `notes/v<version>.md` (format : première ligne `# <version> — <ce qu'elle apporte>`, puis 3-5 puces highlights). Sans ce fichier, `release.yml` échoue explicitement.
- [ ] CHANGELOG : ajoute la section `## v<version>` dans [`CHANGELOG.md`](../CHANGELOG.md) dans le commit du bump de version, et non après. L'entrée est ainsi publiée en même temps que la promotion : rien à réécrire une fois le tag posé, et l'arbre promu est auto-cohérent. Le titre reprend celui de `notes/v<version>.md`.
- [ ] Supprimer le brouillon résiduel : si un `gh release list` affiche un *draft* pour cette version, supprime-le avant le tag — sinon le workflow le reprend et le publie avec une date et un corps périmés.
- [ ] Vérifier l'arbre propre avant de committer : un `output/`, un `randputF_*` ou un `mod-list.json` issu d'un run antérieur peut faire passer un test en local alors qu'il échoue en CI. Cela s'est produit réellement et a masqué le bug décrit en §4. Relance la suite depuis un arbre propre : `rm -rf output randputF_* mod-list.json && python -m pytest`.
- [ ] Promouvoir `master` — réservé au mainteneur, seul moment où la branche bouge : `git push origin dev:master --force` (le `--force` n'est requis que pour cette première promotion, cf. l'encadré §3 ; ensuite un simple `git push origin dev:master` suffit). Ce push déclenche la release : build du wheel, témoin, zip attaché, tag `v<version>` créé sur le commit promu, publication automatique du titre et de la note depuis `notes/v<version>.md`.
- [ ] Vérifier la CI avant de conclure : la promotion est rejetée si la version est déjà taguée, si la note est absente, ou si un test casse (le bump casse les versions codées en dur).
- [ ] Aucun push sans décision explicite du mainteneur.

## 4. Ce que la v1.0.1 a appris (tentative du 2026-10-01, jamais publiée)

La première v1.0.1 est restée en brouillon, mais les quatre problèmes rencontrés ont été corrigés dans le code — ils motivent l'état actuel.

- `release.yml` n'existait que sur `master` (`blob ea84054`) et manquait sur `dev`. Il a été rapatrié sur `dev`, faute de quoi le tag n'aurait construit ni zip ni publication.
- Le titre et la note produits par le workflow n'étaient pas utilisables : titre automatique (« randputF <version> ») et simple lien « Full Changelog ». Corrigé : `release.yml` lit `notes/v<version>.md`, prend le titre sur sa première ligne et publie la note telle quelle.
- `master` et `dev` avaient été créées séparément, sans ancêtre commun, et `master` a dû être reconstruit depuis `dev`. Aujourd'hui `master` repars de zéro sur le tag `v1.0.0` : il contient uniquement ce qui a été publié.
- Le bump a cassé deux tests qui présentaient `randputF_1.0.0` codé en dur dans une attente (`tests/test_witness.py`, `tests/test_cli_install.py`). Ils lisent désormais `MOD_NAME_VERSIONED`. Le second passait en local en raison d'un artefact résiduel (`output/randputF_1.0.0` d'un run antérieur) — d'où la règle « relancer depuis un arbre propre » au §3.

### Ce que `release.yml` fait, dans l'ordre

Il s'agit du script réel du job, et non d'un résumé — s'en écarter brise la publication :

1. Vérifier la version (`mod/info.json`) et l'existence de `notes/v<version>.md` ; refuser si le tag existe déjà sur l'origin. Échec explicite, sans état partiel.
2. Installer le paquet avec ses extras de dev (`pip install ".[dev]"`, comme `ci.yml`) — le job lance `pytest` immédiatement après.
3. `pytest -q` — les tests sont bloquants : une release ne peut sortir sur une suite rouge. Cela garantit qu'un bump de version ne brise rien en silence.
4. `randputf witness --seed 5` — vérifie que la génération aboutit (sans `--expect` : la CI porte la valeur figée, cf. `docs/witness.md`).
5. `randputf generate --seed 5 --out /tmp/modrel` puis zip du dossier `randputF_<version>/` uniquement. `seed.graph.html` est exclu du zip (vue de debug de 5 Mo, déjà écartée du témoin) : 5,2 Mo -> 52 Ko.
6. Créer le tag explicitement : `git tag "$TAG" "$GITHUB_SHA"` puis `git push origin "$TAG"`. Le tag est ainsi créé après les tests et le build, et pointe exactement sur le commit promu.
7. Publier : si la release existe déjà (brouillon), `gh release upload --clobber` puis `gh release edit --draft=false` — `gh release edit` ne publie pas de lui-même. Sinon `gh release create` avec le zip en asset.

Le titre et le corps proviennent de `notes/v<version>.md` et ne sont jamais recopiés.

## 5. Suite des releases

Modèle de branches : `dev` porte le travail en cours et la vérité ; `master` porte le dernier état publié. Le passage de l'un à l'autre constitue la release elle-même : pousser `dev` sur `master` déclenche le build et la publication (§3). Conséquence à garder en tête : le tag v1.0.0 reste accessible par son nom mais ne figure pas dans l'ascendance de `master` — le tag demeure la référence pour cette version.

Numérotation : semver. Tout changement visible par l'utilisateur (fichier de config supprimé, valeur par défaut modifiée, migration requise) -> numéro mineur (1.1.0). Correctif de documentation, de test ou de typos -> numéro de patch (1.0.2).

Titre de release : pas de doublon avec le nom du dépôt. Format `<version> — <ce que la release apporte>`, par exemple `1.0.1 — Le mod ne change pas. Tout ce qui l'entoure, oui.`. La liste des releases de GitHub affiche ce titre ; y réinsérer « randputF » est inutile.

Format de note « highlights », 3-5 puces par version, le détail technique écarté rejoignant les documentations dédiées :
- témoin / canonisation binaire -> `docs/witness.md` ;
- parcours / corrections seed par seed -> `CHANGELOG.md` ;
- référence de configuration -> `docs/config.md` ;
- construction du graphe interactif -> `docs/graphe-interactif.md`.
