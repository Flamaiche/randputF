# Notes de release (source unique)

Fichier de travail de la release randputF. C'est **la** source de vérité pour
la note de release et pour la procédure de publication ; les brouillons
éparpillés (`/tmp/opencode/RELEASE_*.md`, notes de la revue) sont périmés.

Retour : [README.md](README.md).

---

## 1. Release v1.0.0 : PUBLIÉE, gelée

- Tag `v1.0.0`, branche `master` (commit unique `f94f471`).
- Note publiée sur GitHub (texte dans la release, non dans le dépôt).
- Zip attaché : `randputF_1.0.0.zip` (53 007 octets, sha256 `519437ba…`).
- Témoin de déterminisme : `12ac143e06174df126537b978ff928d3`.

**La note v1.0.0 est exacte pour son tag** : elle parle de
`config/settings.yaml`, fichier qui existe bien dans `v1.0.0` (`master`).
`master` et `dev` sont deux branches divergentes (master n'est pas un ancêtre de
dev). **Ne pas éditer la note v1.0.0** : elle décrit l'état du tag.

## 2. Release v1.1.0 : EN PRÉPARATION (non publiée)

C'est la release qui porte le système de configuration à deux YAML. Version
proposée **1.1.0** (changement visible par l'utilisateur, avec note de
migration ; à confirmer par le mainteneur).

### 2.1 Titre

```
v1.1.0 — Randomizer total déterministe pour Factorio 2.0
```

### 2.2 Note de release (structure « highlights », 3-5 puces)

> **Ce que c'est** : un randomizer total pour Factorio 2.0. Il vide le
> tech-tree et les recettes vanilla et régénère tout : ressources au sol,
> lacs de fluides, recettes (entrées et sorties), coûts, catégories de
> bâtiments, ordre de déblocage, kit de départ — en garantissant à chaque
> graine un parcours valide jusqu'à la fusée. Aucune graine « en boîte noire » :
> chaque tirage est nommé, isolé et rejouable.
>
> **🔒 Déterminisme vérifiable**
> ```
> randputf witness --seed 5 --expect <md5 de la v1.1.0>
> ```
> Le contenu du mod pour la seed 5 est inchangé depuis la v1.0.0, mais le
> témoin **change** au bump de version (le préfixe racine du zip contient
> `randputF_<version>`) : le md5 attendu sera celui de la v1.1.0, pas celui de
> la v1.0.0. Le détail de la canonisation est dans `docs/witness.md`.
>
> **📦 Installation** : `pip install .` (embarque mod/, data/ et config/) puis
> `randputf generate --seed <S>`, ou télécharger le zip attaché. Config dans
> `config/defaults.yaml` (source unique, non modifiable) ; surcharges
> facultatives dans `config/user.yaml`.
>
> **Changements de cette version**
> - **Configuration à deux YAML** : `config/settings.yaml` est remplacé par
>   `config/defaults.yaml` (tous les réglages par défaut, source unique,
>   non modifiable) + `config/user.yaml` (surcharges, facultatives). La
>   génération lit la config fusionnée et la **valide** (type, plage,
>   `min <= max`, contraintes croisées) ; une clé inconnue ou une valeur
>   impossible est une erreur explicite, jamais un défaut muet.
> - **Migration** : si vous aviez modifié `settings.yaml`, recopiez vos
>   surcharges dans `user.yaml` (mêmes clés, mêmes sections). Le format est
>   identique ; `settings.yaml` n'est plus lu.
> - **Plus aucune valeur de réglage en dur dans le moteur** : prototypes,
>   générateurs, CLI et pipeline lisent tous leurs valeurs depuis le YAML.
> - **Documentation** : référence de configuration complète dans
>   `docs/config.md`, doc du témoin dans `docs/witness.md`, doc de conception du
>   graphe dans `docs/graphe-interactif.md`, `CHANGELOG.md` (hautes lumières par
>   version), `README_EN.md` pour les joueurs anglophones.
>
> **Chemin parcouru** (le `master` ne contient qu'un commit de release ; tout
> l'historique de travail est sur la branche `dev`) : la v1.0.0 est le fruit
> d'un travail de fond, pas d'un coup d'état. Un bootstrap qui rendait
> certaines seeds injouables (seed 13 : l'électricité exigeait déjà
> l'électricité), des cycles d'hébergement qui rendaient l'ordre d'usage
> impossible (seeds 255 et 1043), un ordre de déblocage non déterministe
> (seed 1299, un `set` non trié) et une dépendance à l'ordre de génération des
> seeds (seed 1269) ont été trouvés par un **rejoueur « fake player »** qui
> simule une partie : **1501/1501 parties** rejouées victorieuses sur le
> balayage 0-1500. Les 722 tests verrouillent ces corrections en régression.
>
> **Garanties mesurées** : 722 tests, invariants de solvabilité (§15),
> rejoueur « fake player » 1501/1501 victoires, témoin de déterminisme
> vérifié octet-pour-octet en CI.

### 2.3 Faits vérifiés (pour ne rien inventer dans la note)

- Témoin seed 5 sur `dev` **avant bump** : `12ac143e06174df126537b978ff928d3`
  — **identique** à v1.0.0 (vérifié : suite complète 722 tests verte sur `dev`).
  Après le bump en 1.1.0 le md5 **change** (préfixe racine du zip) : le
  nouveau témoin sera calculé et écrit dans `.github/workflows/ci.yml` au
  moment du bump (cf. checklist §3). Ne pas reprendre l'ancien md5 tel quel.
- Tests : 722.
- Fichiers de config remplacés : `config/settings.yaml` (supprimé) ->
  `config/defaults.yaml` + `config/user.yaml`.
- Sources pour le détail : `docs/DEVIANCES.md` (bugs/bilan seed par seed),
  `docs/solvabilite.md` (preuves 1501/1501, invariants §15),
  `docs/nondeterminism.md` (déterminisme), `config/user.yaml` (surcharges).

## 3. Checklist de publication (procédure)

Le bump de version se fait **au moment de la release**, pas avant sur `dev` :
tant que `dev` est en 1.0.0, le témoin de `ci.yml` est celui de la 1.0.0.

- [ ] **Version** : bump `mod/info.json` `"version"` vers `1.1.0` (source de
      vérité de la version : `tool/common/version.py`). `pyproject.toml` porte
      aussi la version du paquet : le vérifier au même moment.
- [ ] **Témoin** : le md5 du témoin dépend de la version (préfixe racine
      `randputF_<version>` dans le zip, cf. `tool/common/witness.py`) -> le
      bump de version **change le témoin**. Recalculer le nouveau md5
      (`randputf witness --seed 5`) et le mettre à jour dans
      `.github/workflows/ci.yml` (ligne « Témoin de déterminisme »).
- [x] **`release.yml` restauré sur `dev`** (fichier rapatrié de `master`, voir
      §4) — le tag pourra construire le zip et publier la release.
- [ ] **Dépôt propre dans le tag** : ne pas embarquer les notes de chantier
      (`IDEES.md`, `PLAN_bootstrap_inline.md`, `docs/roadmap-redressement.md`,
      `docs/plan-extracteurs-dispatche.md`, ce fichier). Le tag ne contient que
      le produit + sa documentation (discipline v1.0.0).
- [ ] **fusionner** `dev` -> `master` (en commit unique « 1.1.0 : … » pour
      garder l'historique de travail sur `dev`).
- [ ] **Pousser le tag** `v1.1.0` (déclenche `release.yml` : build du wheel,
      témoin, zip attaché).
- [ ] **Publier la note** (§2.2) sur la release GitHub.
- [ ] Aucun push sans décision explicite du mainteneur.

## 4. Point bloquant avant v1.1.0 : RÉSOLU

**Constat** : le workflow `release.yml` n'existait QUE sur `master` (commit
`f94f471`, `blob ea84054`) et était **absent de `dev`** (la branche a été créée
avant, et `master` n'est pas un ancêtre de `dev`). Une fusion `dev` -> `master`
en l'état aurait supprimé le fichier : le tag `v1.1.0` n'aurait construit ni
zip ni publication automatique.

**Résolution** : `.github/workflows/release.yml` a été rapatrié de `master`
vers `dev` (fichier identique, blob `ea84054`). Il n'est donc plus à toucher au
moment du tag.

Pour mémoire, `release.yml` exécute : `pip install .` ->
`randputf witness --seed 5` (sans `--expect`, il vérifie juste la génération)
-> `randputf generate --seed 5 --out` -> zip `randputF_<version>.zip` ->
`gh release upload` (ou `create`).

## 5. Suite des releases

Format « highlights », 3-5 puces par version, et le détail technique qui a été
écarté de la v1.0.0 part dans les docs :
- témoin / canonisation binaire -> `docs/witness.md` ;
- parcours / corrections seed par seed -> `CHANGELOG.md` ;
- référence de configuration -> `docs/config.md` ;
- construction du graphe interactif -> `docs/graphe-interactif.md`.