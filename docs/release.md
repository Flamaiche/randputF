# Release : procédure et état

Ce document tient **la procédure** de publication et l'état d'avancement des
versions.

**La note publiée, elle, vit dans [`notes/v<version>.md`](../notes/)** : c'est ce
fichier que `release.yml` publie (titre = première ligne). Cette page ne
contient donc pas la note — elle décrit comment la produire et où elle est.

Les brouillons de travail (plans, idées, notes de révision) vivaient dans
`atelier/`. Ce dossier est désormais **ignoré par git** : il reste sur le disque
du mainteneur, mais n'entre dans aucun commit, donc dans aucun tag. Ce qui doit
être versionné est ici, dans `docs/`.

Retour : [README.md](../README.md).

---

## 1. État des versions

**Publiée** — accessible publiquement, tag sur `master` :

| Version | Tag | Contenu | Témoin seed 5 |
|---|---|---|---|
| v1.0.0 | `v1.0.0` → `f94f471` | Première release publique. Config `settings.yaml`. | `12ac143e06174df126537b978ff928d3` |

**En préparation** — sur `dev`, non publiée :

| Version | Note | Contenu | Témoin seed 5 |
|---|---|---|---|
| v1.0.1 | [`notes/v1.0.1.md`](../notes/v1.0.1.md) | Config à deux YAML + refonte documentaire. | `ce428c2140ec7031f9604637ecf70cbc` |

**Les notes publiées sont gelées** : elles décrivent l'état de leur tag. La note
v1.0.0 parle de `config/settings.yaml`, qui existe bien dans `v1.0.0`. Ne pas
éditer une note publiée.

**Réutilisation du numéro 1.0.1** : une première v1.0.1 a été préparée le
2026-10-01, mais **jamais publiée** — elle est restée en *draft* sur GitHub, et
son tag a été supprimé au reset de `master`. Rien n'a donc jamais été public
sous ce numéro : le réemployer ne trompe personne, et c'est ce qui a été fait.
Le brouillon residuel est supprimé avant le tag (sinon le workflow le
reprendrait et le publierait avec une date et un corps périmés).

**Écart assumé sur la numérotation** : la configuration à deux YAML est un
changement visible par l'utilisateur (un fichier supprimé, des surcharges à
recopier), ce qui relevait de `1.1.0` au sens semver. La version sort en
**1.0.1**, sur décision du mainteneur. **Convention retenue pour la suite** : le
semver reprend ses droits — un changement visible par l'utilisateur prend un
chiffre mineur (1.1.0), un correctif de documentation ou de test un numéro de
patch.

## 2. Release v1.0.1 : EN PRÉPARATION

Porte le système de configuration à deux YAML et la refonte documentaire. Elle
sortira au tag `v1.0.1`, en même temps que le merge de `dev` dans `master`.

### 2.1 Titre et note

Le titre et la note sont **dans [`notes/v1.0.1.md`](../notes/v1.0.1.md)** —
première ligne = titre, reste = note « highlights ». `release.yml` les publie
tels quels ; ne pas les recopier ici.

```
1.0.1 — Documentation mise à jour et configuration en deux YAML
```

### 2.2 Faits vérifiés (pour ne rien inventer dans la note)

- Témoin seed 5 de la v1.0.1 : `ce428c2140ec7031f9604637ecf70cbc`. Il **change**
  au bump de version (préfixe racine du zip `randputF_<version>`) alors que le
  contenu du mod pour la seed 5 est inchangé depuis la v1.0.0. Ne jamais
  reprendre l'ancien md5 tel quel.
- Tests : 722.
- Fichiers de config : `config/settings.yaml` (supprimé) ->
  `config/defaults.yaml` + `config/user.yaml`.
- Sources pour le détail : `docs/DEVIANCES.md` (bugs/bilan seed par seed),
  `docs/solvabilite.md` (preuves 1501/1501, invariants §15),
  `docs/nondeterminism.md` (déterminisme), `config/user.yaml` (surcharges).

## 3. Checklist de publication (procédure)

Le bump de version se fait **dans `dev`** (seule branche de travail) :
`mod/info.json` (source de vérité) et `pyproject.toml` au même moment —
`tool/common/version.py` lit `mod/info.json`, il ne se bump pas.
La release est la **promotion `dev` → `master`**, décidée par le mainteneur.

> **La release est la promotion `dev` → `master`.** Le workflow se déclenche
> quand `master` reçoit le travail de `dev` ; il lit la version dans
> `mod/info.json`, construit le mod, crée le tag `v<version>` sur le commit
> promu et publie. Il n'y a plus à créer de tag à la main. Le tag v1.0.0
> (`f94f471`) est un commit racine sans parent, donc `master` et `dev` n'ont
> aujourd'hui aucun ancêtre commun et `master` se replace sur `dev` par
> `git push origin dev:master --force`. Dès cette première promotion, les deux
> branches redeviennent parent-enfant : les promotions suivantes sont des
> *fast-forward*, sans `--force`. Conséquence à garder en tête : le commit
> v1.0.0 reste accessible par son tag, mais sort de l'ascendance de `master`.

- [ ] **Tout passer par `dev`** : corrections, docs, bump de version sur `dev`.
- [ ] **Version** : bump de `mod/info.json` `"version"` — c'est la **source de
      vérité**, lue par `tool/common/version.py` — et de `pyproject.toml`, au
      même moment.
- [ ] **Témoin** : le md5 du témoin dépend de la version (préfixe racine
      `randputF_<version>` dans le zip, cf. `tool/common/witness.py`) -> le
      bump de version **change le témoin**. Recalculer le nouveau md5
      (`randputf witness --seed 5`) et le mettre à jour dans
      `.github/workflows/ci.yml` **et** `docs/witness.md`.
- [ ] **Note de release** : créer `notes/v<version>.md` (format : première ligne
      `# <version> — <ce qu'elle apporte>`, puis 3-5 puces highlights).
      Sans ce fichier, `release.yml` échoue explicitement.
- [ ] **CHANGELOG** : ajouter la section `## v<version>` dans
      [`CHANGELOG.md`](../CHANGELOG.md) au moment de la publication. Il ne
      documente que les versions **publiées** — tant que la v1.0.1 est en
      préparation sur `dev`, il s'arrête à v1.0.0.
- [ ] **Supprimer le brouillon résiduel** : si un `gh release list` affiche un
      *draft* pour cette version, le supprimer avant le tag — sinon le workflow
      le reprend et le publie avec une date et un corps périmés.
- [ ] **Vérifier l'arbre propre avant de committer** : un `output/` ou un
      `randputF_*` laissé par un run antérieur peut faire passer un test en
      local alors qu'il échoue en CI. Relancer la suite depuis un arbre propre :
      `rm -rf output && python -m pytest`.
- [ ] **Promouvoir `master`** — *réservé au mainteneur, seul moment où la
      branche bouge* : `git push origin dev:master --force` (le `--force` n'est
      nécessaire que pour cette première promotion, cf. l'encadré §3 ; ensuite
      un simple `git push origin dev:master` suffit). Ce push **déclenche la
      release** : build du wheel, témoin, zip attaché, tag `v<version>` créé sur
      le commit promu, **publication automatique** du titre et de la note depuis
      `notes/v<version>.md`.
- [ ] **Vérifier la CI** avant de conclure : la promotion est rejetée si la
      version est déjà taguée, si la note est absente, ou si un test casse (le
      bump casse les versions codées en dur).
- [ ] Aucun push sans décision explicite du mainteneur.

## 4. Ce que la v1.0.1 a appris (tentative du 2026-10-01, jamais publiée)

La première v1.0.1 est restée en brouillon, mais les quatre problems rencontrés
ont été corrigés dans le code — ils sont la raison de l'état actuel.

- **`release.yml` n'existait que sur `master`** (`blob ea84054`) et était absent
  de `dev`. Il a été rapatrié sur `dev`, sinon le tag n'aurait construit ni zip
  ni publication.
- **Le titre et la note produits par le workflow n'étaient pas utilisables** :
  titre automatique (« randputF <version> ») et simple lien « Full Changelog ».
  Corrigé : `release.yml` lit `notes/v<version>.md`, prend le titre sur sa
  première ligne et publie la note telle quelle.
- **`master` et `dev` avaient été créées séparément**, sans ancêtre commun, et
  `master` a dû être reconstruit depuis `dev`. Aujourd'hui `master` est reparti
  de zéro sur le tag `v1.0.0` : il ne contient que ce qui a été publié.
- **Le bump a cassé deux tests** qui avaient `randputF_1.0.0` codé en dur dans
  une attente (`tests/test_witness.py`, `tests/test_cli_install.py`). Ils lisent
  maintenant `MOD_NAME_VERSIONED`. Le second passait en local par un artefact
  résiduel (`output/randputF_1.0.0` d'un run antérieur) — d'où la règle
  « relancer depuis un arbre propre » en §3.

`release.yml` exécute : `pip install .` ->
`randputf witness --seed 5` (sans `--expect`, il vérifie juste la génération)
-> `randputf generate --seed 5 --out` -> zip `randputF_<version>.zip` ->
`gh release create --target <commit promu>` (ou `upload --clobber` + `edit`
si une release existe déjà, avec `--draft=false` pour republier un brouillon).

## 5. Suite des releases

**Modèle de branches** : `dev` porte le travail en cours et **la vérité** ;
`master` porte le **dernier état publié**. Le passage de l'un à l'autre est la
release elle-même : pousser `dev` sur `master` déclenche le build et la
publication (§3). Conséquence à avoir en tête : le tag v1.0.0 reste accessible
par son nom mais n'est pas dans l'ascendance de `master` — le tag reste la
référence pour cette version.

**Numérotation** : semver. Changement visible par l'utilisateur (fichier de
config supprimé, valeur par défaut modifiée, migration à faire) -> numéro
mineur (1.1.0). Correctif de documentation, de test ou de typos -> numéro de
patch (1.0.2).

**Titre de release** : pas de doublon avec le nom du dépôt. Format
`<version> — <ce que la release apporte>`, par exemple
`1.0.1 — Documentation mise à jour et configuration en deux YAML`. La liste des
releases de GitHub affiche ce titre ; y remettre « randputF » est inutile.

Format de note « highlights », 3-5 puces par version, et le détail technique
qui a été écarté part dans les docs :
- témoin / canonisation binaire -> `docs/witness.md` ;
- parcours / corrections seed par seed -> `CHANGELOG.md` ;
- référence de configuration -> `docs/config.md` ;
- construction du graphe interactif -> `docs/graphe-interactif.md`.