# Notes de release (source unique)

Fichier de travail de la release randputF. C'est **la** source de vérité pour
la note de release et pour la procédure de publication ; les brouillons
éparpillés (`/tmp/opencode/RELEASE_*.md`, notes de la revue) sont périmés.

Retour : [README.md](../README.md).

---

## 1. Releases publiées

| Version | Tag | Contenu | Témoin seed 5 |
|---|---|---|---|
| v1.0.0 | `v1.0.0` → `f94f471` | Première release publique. Config `settings.yaml`. | `12ac143e06174df126537b978ff928d3` |
| v1.0.1 | `v1.0.1` → `3a187fb` | Config à deux YAML + refonte documentaire. | `ce428c2140ec7031f9604637ecf70cbc` |

**Les notes publiées sont gelées** : elles décrivent l'état de leur tag. La note
v1.0.0 parle de `config/settings.yaml`, qui existe bien dans `v1.0.0`. Ne pas
éditer une note publiée.

**Écart assumé sur la numérotation** : la configuration à deux YAML est un
changement visible par l'utilisateur (un fichier supprimé, des surcharges à
recopier), ce qui relevait de `1.1.0` au sens semver. La version publiée est
`1.0.1`, sur décision du mainteneur. **Convention retenue pour la suite** : le
semver reprend ses droits — un changement visible par l'utilisateur prend un
chiffre mineur (1.1.0), un correctif de documentation ou de test un numéro de
patch. Le 1.0.1 ne sera pas renuméroté : il est publié, avec sa note.

## 2. Release v1.0.1 : PUBLIÉE

Porte le système de configuration à deux YAML et la refonte documentaire.
Note publiée sur GitHub (texte dans la release, non dans le dépôt).

### 2.1 Titre

```
1.0.1 — Documentation mise à jour et configuration en deux YAML
```

### 2.2 Note de release

Publiée sur la release GitHub `v1.0.1`. Structure « highlights » : ce que c'est,
déterminisme vérifiable, installation, changements, chemin parcouru, garanties
mesurées. Les faits vérifiés sont en §2.3.

### 2.3 Faits vérifiés (pour ne rien inventer dans la note)

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

Le bump de version se fait **au moment de la release**, sur `master`, jamais
avant sur `dev` : tant que `dev` est en 1.0.1, le témoin de `ci.yml` est celui
de la 1.0.1.

- [ ] **Tout passer par `dev`** : corrections et docs sur `dev`, jamais de push
      direct sur `master` (§5). On ne bumpe la version que dans le commit de
      release, une fois `dev` mergé dans `master`.
- [ ] **Version** : bump `mod/info.json` `"version"` (source de vérité :
      `tool/common/version.py`), et `pyproject.toml` au même moment.
- [ ] **Témoin** : le md5 du témoin dépend de la version (préfixe racine
      `randputF_<version>` dans le zip, cf. `tool/common/witness.py`) -> le
      bump de version **change le témoin**. Recalculer le nouveau md5
      (`randputf witness --seed 5`) et le mettre à jour dans
      `.github/workflows/ci.yml` **et** `docs/witness.md`.
- [ ] **Vérifier l'arbre propre avant de committer** : un `output/` ou un
      `randputF_*` laissé par un run antérieur peut faire passer un test en
      local alors qu'il échoue en CI (`tests/test_cli_install.py` s'en est
     .heurté). Relancer la suite depuis un arbre propre :
      `rm -rf output && python -m pytest`.
- [ ] **Dépôt propre dans le tag** : le dossier `atelier/` n'est jamais
      embarqué (il reste sur `dev`). Le tag ne contient que le produit + sa
      documentation.
- [ ] **Fusionner** `dev` -> `master`.
- [ ] **Pousser le tag** (déclenche `release.yml` : build du wheel, témoin, zip
      attaché).
- [ ] **Publier la note ET corriger le titre** : note « highlights » (§2.2 pour
      le gabarit) et titre `<version> — <ce qu'elle apporte>`, sans le nom du
      dépôt (§5). Le workflow publie un titre automatique et un « Full
      Changelog » seul : **il faut éditer la release après coup**.
- [ ] **Vérifier la CI du tag** avant de conclure : un tag peut être poussé
      alors qu'un test casse (le bump casse les versions codées en dur).
- [ ] Aucun push sans décision explicite du mainteneur.

## 4. Historique de publication : ce qui a été fait pour la v1.0.1

Pour mémoire, quatre opérations manuelles ont été nécessaires, toutes dues au
fait que le workflow ne fait que le strict minimum.

- **`release.yml` n'existait que sur `master`** (`blob ea84054`) et était absent
  de `dev`. Il a été rapatrié sur `dev` avant le tag, sinon le tag n'aurait
  construit ni zip ni publication.
- **Le titre et la note publiés par le workflow ne sont pas utilisables** :
  `release.yml` crée la release avec un titre automatique (« randputF
  <version> ») et un simple lien « Full Changelog ». La note et le titre ont dû
  être édités à la main sur GitHub après publication.
- **`master` a dû être reconstruit depuis `dev`** : les deux branches avaient
  été créées séparément, sans ancêtre commun. `master` est désormais l'historique
  linéaire de `dev` + le commit de release.
- **Le bump a cassé deux tests** qui avaient `randputF_1.0.0` codé en dur dans
  une attente (`tests/test_witness.py`, `tests/test_cli_install.py`). Ils lisent
  maintenant `MOD_NAME_VERSIONED`. Le second passait en local par un artefact
  résiduel (`output/randputF_1.0.0` d'un run antérieur) — d'où la règle
  « relancer depuis un arbre propre » en §3.

Pour mémoire, `release.yml` exécute : `pip install .` ->
`randputf witness --seed 5` (sans `--expect`, il vérifie juste la génération)
-> `randputf generate --seed 5 --out` -> zip `randputF_<version>.zip` ->
`gh release upload` (ou `create`).

## 5. Suite des releases

**Modèle de branches** : `dev` porte le travail en cours, `master` porte
l'historique intégré. **Ne jamais pousser directement sur `master`** : tout
passe par `dev`, puis fusion — ainsi `master` reste « ce qui a été vu au moins
une fois ».

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