# Notes de release (source unique)

Fichier de travail de la release randputF. C'est **la** source de vérité pour
la note de release et pour la procédure de publication ; les brouillons
éparpillés (`/tmp/opencode/RELEASE_*.md`, notes de la revue) sont périmés.

Retour : [README.md](README.md).

---

## 1. Release v1.0.0 : PUBLIEE, gelee

- Tag `v1.0.0`, branche `master` (commit unique `f94f471`).
- Note publiee sur GitHub (texte dans la release, non dans le depot).
- Zip attache : `randputF_1.0.0.zip` (53 007 octets, sha256 `519437ba…`).
- Temon de determinisme : `12ac143e06174df126537b978ff928d3`.

**La note v1.0.0 est exacte pour son tag** : elle parle de
`config/settings.yaml`, fichier qui existe bien dans `v1.0.0` (`master`).
`master` et `dev` sont deux branches divergentes (master n'est pas un ancetre de
dev). **Ne pas editer la note v1.0.0** : elle decrit l'etat du tag.

## 2. Release v1.1.0 : EN PREPARATION (non publiee)

C'est la release qui porte le systeme de configuration a deux YAML. Version
proposee **1.1.0** (changement visible par l'utilisateur, avec note de
migration ; a confirmer par le mainteneur).

### 2.1 Titre

```
v1.1.0 — Randomizer total deterministe pour Factorio 2.0
```

### 2.2 Note de release (structure « highlights », 3-5 puces)

> **Ce que c'est** : un randomizer total pour Factorio 2.0. Il vide le
> tech-tree et les recettes vanilla et regenere tout : ressources au sol,
> lacs de fluides, recettes (entrees et sorties), couts, categories de
> batiments, ordre de deblocage, kit de depart — en garantissant a chaque
> graine un parcours valide jusqu'a la fusee. Aucune graine « en boite noire » :
> chaque tirage est nomme, isole et rejouable.
>
> **🔒 Determinisme verifiable**
> ```
> randputf witness --seed 5 --expect 12ac143e06174df126537b978ff928d3
> ```
> Le meme temoin qu'en v1.0.0 (le contenu du mod pour la seed 5 n'a pas
> change).
>
> **📦 Installation** : `pip install .` (embarque mod/, data/ et config/) puis
> `randputf generate --seed <S>`, ou telecharger le zip attache. Config dans
> `config/defaults.yaml` (source unique, non modifiable) ; surcharges
> facultatives dans `config/user.yaml`.
>
> **Changements de cette version**
> - **Configuration a deux YAML** : `config/settings.yaml` est remplace par
>   `config/defaults.yaml` (tous les reglages par defaut, source unique,
>   non modifiable) + `config/user.yaml` (surcharges, facultatives). La
>   generation lit la config fusionnee et la **valide** (type, plage,
>   `min <= max`, contraintes croisees) ; une cle inconnue ou une valeur
>   impossible est une erreur explicite, jamais un defaut muet.
> - **Migration** : si vous aviez modifie `settings.yaml`, recopiez vos
>   surcharges dans `user.yaml` (memes cles, memes sections). Le format est
>   identique ; `settings.yaml` n'est plus lu.
> - **Plus aucune valeur de reglage en dur dans le moteur** : prototypes,
>   generateurs, CLI et pipeline lisent tous leurs valeurs depuis le YAML.
> - **Documentation** : config deux YAML et feuille de route de
>   redressement ; README et docs a jour.
>
> **Garanties mesurees** : 722 tests, invariants de solvabilite (§15),
> rejoueur « fake player » 1501/1501 victoires, temoin de determinisme
> verifie octet-pour-octet en CI.

### 2.3 Faits verifies (pour ne rien inventer dans la note)

- Temoin seed 5 : `12ac143e06174df126537b978ff928d3` — **identique** a v1.0.0
  (verifie : suite complete 722 tests verte sur `dev`).
- Tests : 722.
- Fichiers de config remplaces : `config/settings.yaml` (supprime) ->
  `config/defaults.yaml` + `config/user.yaml`.
- Sources pour le detail : `docs/DEVIANCES.md` (bugs/bilan seed par seed),
  `docs/solvabilite.md` (preuves 1501/1501, invariants §15),
  `docs/nondeterminism.md` (determinisme), `config/user.yaml` (surcharges).

## 3. Checklist de publication (procedure)

- [ ] **Version** : bump `mod/info.json` `"version"` vers `1.1.0` (source de
      verite de la version : `tool/common/version.py`).
- [ ] **Temoign** : le md5 du temoin depend de la version (prefixe racine
      `randputF_<version>` dans le zip, cf. `tool/common/witness.py`) -> le
      bump de version **change le temoin**. Recalculer le nouveau md5 et le
      mettre a jour dans `.github/workflows/ci.yml` (ligne « Temoin de
      determinisme »).
- [ ] **`release.yml` a restaurer sur `dev`** (voir §4) — sinon pas de zip
      attache ni de publication automatique au tag.
- [ ] **Depot propre dans le tag** : ne pas embarquer les notes de chantier
      (`IDEES.md`, `PLAN_bootstrap_inline.md`, `docs/roadmap-redressement.md`,
      `docs/plan-extracteurs-dispatche.md`, ce fichier). Le tag ne contient que
      le produit + sa documentation (discipline v1.0.0).
- [ ] **fusionner** `dev` -> `master` (en commit unique « 1.1.0 : … » pour
      garder l'historique de travail sur `dev`).
- [ ] **Pousser le tag** `v1.1.0` (declenche `release.yml` : build du wheel,
      temoin, zip attache).
- [ ] **Publier la note** (§2.2) sur la release GitHub.
- [ ] Aucun push sans decision explicite du mainteneur.

## 4. Point bloquant a traiter avant v1.1.0

**Le workflow `release.yml` n'existe QUE sur `master`** (commit `f94f471`,
`blob ea84054`). Il est **absent de `dev`** (la branche a ete creee avant, et
master n'est pas un ancetre de dev). Consequence : si `dev` est fusionne dans
`master` en l'etat, le fichier disparait et le tag `v1.1.0` **ne construira
pas le zip et ne publiera pas la release automatiquement**.

Action : rapatrier `.github/workflows/release.yml` de `master` vers `dev`
(cherry-pick du fichier / copie) **avant** la fusion. `release.yml` execute :
`pip install .` -> `randputf witness --seed 5` (sans `--expect`, il verifie
juste la generation) -> `randputf generate --seed 5 --out` -> zip
`randputF_<version>.zip` -> `gh release upload` (ou `create`).

## 5. Suite des releases

Format « highlights », 3-5 puces par version, et le detail technique qui a ete
ecart de la v1.0.0 part dans les docs :
- temoin / canonisation binaire -> `docs/witness.md` (a creer, lot E de la
  feuille de route `docs/roadmap-redressement.md`) ;
- parcours / corrections seed par seed -> `CHANGELOG.md` (a creer, lot B).