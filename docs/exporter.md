# Exporter Factorio —.dump des prototypes

L'exporter est le **mod compagnon** qui photographie l'état réel des prototypes Factorio et le livre au tool Python sous forme de JSON. Il est volontairement minuscule : un `info.json`, un `control.lua`, aucune dépendance autre que `base >= 2.0`, et aucune logique de randomisation.

Il ne génère **ni seed, ni mod, ni HTML**. Il produit uniquement la matière première consommée ensuite par `tool/parsers/vanilla.py`, `tool/generator/pipeline.py`, `randputf dump`, `randputf report` et `randputf test`.

Version installée et contractuelle : **0.1.8**. Le schéma JSON associé est **schema_version = 2**. Il n'existe pas de version 0.1.9 prévue : 0.1.8 est la version de référence.

---

## 1. Rôle et périmètre

Factorio ne donne pas directement un dump lisible de tous ses prototypes au tool Python. L'exporter comble ce trou en s'exécutant **dans le jeu**, où les prototypes Lua existent réellement, puis en écrivant un JSON dans `script-output`.

Deux usages :

1. **Dump vanilla de référence** — Factorio lancé avec `base` seul. C'est le cas nominal ; le dump est copié dans `data/vanilla_dump.json` et devient la base du générateur.
2. **Dump moddé / diagnostic** — Factorio lancé avec `randputF` actif. Le dump contient alors les prototypes mutés par le mod (recettes `randputf-*`, technologies neutralisées, entités modifiées, `mod_data` des lacs). Le tool sait le canoniser à la lecture, mais ce n'est pas le dump de référence pour une baseline vanilla.

L'exporter est un outil de transition : il peut être intégré au mod principal ou retiré plus tard. Tant qu'il existe, il est versionné indépendamment du mod `randputF`.

---

## 2. Installation et exécution

### 2.1 Installation

Le dossier source est `exporter/` à la racine du dépôt. Il contient :

- `info.json` — identité du mod ;
- `control.lua` — toute la logique d'export ;
- les archives historiques `randputf-exporter_0.1.4.zip` et `randputf-exporter_0.1.5.zip`.

Copier le dossier (ou son contenu) dans le dossier mods Factorio sous le nom versionné exact :

```text
~/.factorio/mods/randputf-exporter_0.1.8/
```

Sous Flatpak/Steam, le dossier utilisateur Factorio est typiquement :

```text
/var/home/<user>/.var/app/com.valvesoftware.Steam/.factorio/mods/
```

Utiliser une **copie réelle** plutôt qu'un lien symbolique si Flatpak refuse de suivre le lien hors sandbox.

Le nom du dossier doit rester `randputf-exporter_0.1.8` : l'exporter lit sa propre version dans `script.active_mods["randputf-exporter"]` et écrit cette valeur dans `meta.exporter_version`. Un dossier mal nommé dégrade donc l'identité du dump.

### 2.2 Déclenchement

Aucune commande chat, aucun bouton et aucune interface ne sont nécessaires. L'export est déclenché par `script.on_init`, c'est-à-dire à la **création d'une nouvelle partie** avec l'exporter actif.

Il suffit donc de :

1. installer l'exporter ;
2. lancer une nouvelle partie Factorio ;
3. attendre le message de log `randputF exporter: ... écrits` ;
4. récupérer le JSON dans `script-output`.

Le mod n'écrit rien pendant une partie déjà chargée : il faut bien une initialisation neuve. Il n'y a pas de timeout, pas de fichier partiel surveillé et pas de rejeu automatique.

### 2.3 Sorties

Deux fichiers identiques sont écrits :

| Fichier | Rôle |
|---|---|
| `script-output/dump_mods_<label>_exporter_0.1.8.json` | nom qualifié, conserve l'identité des mods actifs |
| `script-output/randputF/vanilla_dump.json` | alias stable, compatible avec les anciens scripts |

Le nom qualifié est la source de vérité. L'alias est pratique pour les comparaisons rapides, mais il écrase l'alias précédent.

Exemple pour un dump vanilla :

```json
{
  "game_version": "2.1.24",
  "game_version_numeric": 20124,
  "schema_version": 2,
  "exporter_version": "0.1.8",
  "active_mods": [{"name": "base", "version": "2.1.24"}],
  "mod_label": "vanilla",
  "mod_label_full": "vanilla",
  "dump_file": "dump_mods_vanilla_exporter_0.1.8.json"
}
```

### 2.4 Règles de nommage

`meta.dump_file`, `meta.mod_label` et `meta.mod_label_full` sont construits par `dump_identity()`.

1. Les mods actifs sont triés par nom.
2. `randputf-exporter` est exclu de `active_mods` : l'outil qui exporte ne fait pas partie du contenu exporté.
3. `base` reste dans `active_mods`, mais est exclu du libellé : c'est la baseline implicite.
4. Chaque fragment est assaini : les caractères non alphanumériques, `.` et `-` deviennent `-`, les tirets répétés sont réduits, les tirets de début/fin sont supprimés.
5. Les fragments sont joints par `__` sous la forme `<name>-<version>`.
6. Sans autre mod que `base`, le libellé complet vaut `vanilla`.
7. Si le libellé complet dépasse 120 caractères, le libellé court devient :

```text
<premiers 120 caractères>__n<nombre de mods>-<hash8>
```

Le hash est un djb2 modulo `2147483647`, formaté sur 8 hexadécimales. `mod_label_full` garde toujours le libellé complet non tronqué.

Le fichier principal vaut alors :

```text
dump_mods_<mod_label>_exporter_<exporter_version>.json
```

---

## 3. Structure du JSON

Le dump est un objet JSON avec une clé `meta` et sept ou huit sections de données.

```text
meta
inventory
tiles
items
fluids
entities
recipes
technologies
mod_data   (optionnel, exporter 0.1.7+, Factorio 2.1.20+)
```

### 3.1 `meta`

| Clé | Type | Sens |
|---|---|---|
| `game_version` | string | Version de `base`, par exemple `2.1.24`. |
| `game_version_numeric` | number | `major * 10000 + minor * 100 + patch` ; `20124` pour `2.1.24`. Vaut `0` si la version est illisible. |
| `schema_version` | number | `2` pour l'exporter 0.1.8. |
| `exporter_version` | string | Version lue sur `randputf-exporter`, avec repli `0.1.8`. |
| `active_mods` | array | Paires `{name, version}` triées par nom, hors exporter, `base` inclus. |
| `mod_label` | string | Libellé court éventuellement tronqué, utilisé comme préfixe des HTML. |
| `mod_label_full` | string | Libellé complet non tronqué. |
| `dump_file` | string | Nom du fichier qualifié écrit dans `script-output`. |

Le dump **ne contient pas** `science_packs`, `science_pack_order` ni `rocket`. Ces faits dérivés sont calculés côté Python et écrits dans `seed.meta` par le générateur. Les confondre est une erreur fréquente lors de la lecture de `data/vanilla_dump.json`.

### 3.2 `inventory`

Dictionnaire `nom de table de prototypes → liste triée de noms`. La liste des tables est structurelle et suit l'API LuaPrototypes : `entity`, `item`, `fluid`, `tile`, `equipment`, `recipe`, `technology`, `quality`, `space-location`, etc. Une table absente d'une version du jeu est simplement omise, sans erreur.

Cette section sert à l'inventaire A→Z du navigateur HTML et aux contrôles d'exhaustivité.

### 3.3 `tiles`

Dictionnaire `nom de tuile → {collision_layers, fluid?}`.

- `collision_layers` : couches de `collision_mask.layers`, triées.
- `fluid` : nom du fluide que la pompe offshore produit sur cette tuile, quand Factorio le déclare.

C'est une donnée brute : le tool déduit ensuite les fluides pompables, avec repli sur `mod_data` puis sur les règles de buildabilité.

### 3.4 `items`

Dictionnaire `nom d'item → fiche prototype`. Champs notables :

- `type`, `display_type` (`"item"` toujours, même pour les packs de science classés `tool` par Factorio) ;
- `subgroup`, `order` ;
- `place_result` ;
- `fuel_value`, `fuel_category` / `fuel_categories`, `burnt_result` ;
- `stack_size` ;
- `ammo_category` ;
- `rocket_launch_products` — source de vérité des produits de lancement en orbite ;
- `main_product`, `used_by_labs`, `science_capacity`.

Les prototypes `gun`, `ammo`, `tool`, `capsule`, `module` et `armor` sont ajoutés s'ils ne sont pas déjà dans `prototypes.item`, afin que le générateur voie aussi les armes et objets spéciaux.

### 3.5 `fluids`

Dictionnaire `nom de fluide → fiche prototype` : `type` et `display_type` valant `"fluid"`, `subgroup`, `order`, `fuel_value`, températures et propriétés thermiques (`default_temperature`, `max_temperature`, `heat_capacity`, `gas_temperature`, `emissions_multiplier`) et couleurs (`base_color`, `flow_color`, `visualization_color`).

Les champs indisponibles sont omis plutôt que remplis avec des valeurs inventées.

### 3.6 `entities`

Dictionnaire `nom d'entité → fiche prototype`. C'est la section la plus riche :

- identification : `type`, `order`, `selection_box`, `flags` (tableau trié des flags du prototype, par exemple `placeable-water`) ;
- armement : `guns` (tableau), avec repli sur `gun` ;
- craft : `crafting_categories`, `ingredient_count`, `auto_select`, `crafting_speed` (via `get_crafting_speed()` en 2.1) ;
- extraction : `resource_categories`, `mining_speed` ;
- ressources et arbres : `mineable_properties` (produits, temps, fluide requis, quantité) ;
- fluides : nombre d'entrées/sorties et détails des fluidboxes (`production_type`, `filter`) ;
- énergie : sources, consommation, buffers ;
- recettes fixes, choisies automatiquement ou assignées au bâtiment.

Ces champs sont lus tels quels par `tool/parsers/vanilla.py` et servent aux tags, au modèle randput et à la résolution des recettes fixes.

### 3.7 `recipes`

Dictionnaire `nom de recette → {category, order, energy, ingredients, products, enabled?, hidden?, main_product?}`.

`category` retombe sur `categories[1]`, puis sur `"crafting"` si le runtime n'expose pas le champ attendu. `enabled` et `hidden` sont des états runtime : dans un dump moddé, une recette vanilla neutralisée reste présente avec ses liens mais porte `enabled = false` et `hidden = true`.

### 3.8 `technologies`

Dictionnaire `nom de techno → fiche recherche` :

- `order`, `research_unit_count_formula` ;
- `unit` avec `count`, `ingredients` et `time` (mappé sur `research_unit_energy`, seule notion de coût unitaire disponible au runtime) ;
- `prerequisites` (les clés du dictionnaire runtime sont les identifiants) ;
- `effects` (`type`, `recipe`, `technology`, `item`) ;
- `research_trigger` quand il existe ;
- `enabled`, `hidden`.

Cette section sert de baseline de difficulté : elle est comparée à `seed["technologies"]` par les outils d'audit.

### 3.9 `mod_data`

Section optionnelle ajoutée en 0.1.7 et présente seulement si le jeu expose `prototypes.mod_data` (Factorio 2.1.20+) et si au moins une entrée possède un champ `data`.

Chaque entrée est `{name, data_type, data}` et est copiée **sans interprétation**. randputF y publie notamment :

- `randputf-lake-tiles` — mapping canonique tuile fantôme → tuiles de lac → fluides ;
- `randputf-water-tiles` — tuiles d'eau vanilla hors lacs générés.

Le navigateur HTML affiche cette section repliable dans « Données de mods ». Le runtime du mod lit aussi `mod_data` en priorité et garde des replis pour les dumps anciens.

---

## 4. Comportement et garanties

### 4.1 Brut, pas d'inférence

L'exporter ne devise pas : il copie ce que le runtime Factorio expose. Les inférences (tags, pools, fluides pompés, packs de science, chaîne de fusée, difficulté) appartiennent au tool Python.

Les helpers `probe`, `pcall` et `prototypes_dict` tolèrent les versions de jeu qui n'ont pas telle propriété ou telle table : un champ absent est omis, jamais remplacé par une valeur par défaut hasardeuse.

### 4.2 Déterminisme et lisibilité

- Les noms de l'inventaire sont triés.
- Les couches de collision des tuiles sont triées.
- `active_mods` est trié par nom.
- Les listes construites depuis des dictionnaires Lua peuvent suivre l'ordre du runtime ; les consommateurs Python les lisent par clé et ne dépendent pas de l'ordre du fichier pour les dictionnaires.

Le JSON est produit par `helpers.table_to_json` puis écrit avec `helpers.write_file`. Le contenu est identique dans les deux fichiers.

### 4.3 Dump moddé

Depuis 0.1.8, l'exporter **accepte** les parties où randputF est actif. Le dump est alors une photographie complète :

- les prototypes vanilla neutralisés restent avec leurs liens, mais `enabled = false` et `hidden = true` ;
- les recettes `randputf-X` actives remplacent la recette vanilla `X` lors de la canonisation côté Python ;
- les artefacts `randputf-randputf-…` sont ignorés ;
- les items, fluides et entités déjà préfixés vont dans des buckets `modded_*`, hors des pools de génération.

Un dump moddé peut donc produire une seed différente du dump vanilla historique : c'est attendu et documenté dans `docs/runtime.md`.

Les versions 0.1.4 et 0.1.5 refusaient l'export quand un artefact `randputf-*` était détecté (`EXPORT REFUSE`). Ce garde-fou a été retiré : la canonisation à la lecture l'a remplacé.

---

## 5. Chaîne de consommation côté Python

| Étape | Commande / module | Rôle |
|---|---|---|
| Acquisition | `exporter/control.lua` | écrit le JSON dans `script-output` |
| Copie | utilisateur | `dump_mods_*.json` → `data/vanilla_dump.json` |
| Lecture | `tool/parsers/vanilla.py` | `load_db_from_dump`, canonisation, `mod_data`, science packs, fusée |
| Génération | `tool/generator/pipeline.py` | `generate_seed(db, ...)` |
| Assemblage | `tool/exporters/mod_seed.py` | `seed.json`, `seed.lua`, `locale/*/seed.cfg` |
| Navigation | `tool/exporters/dump_html.py` | `randputf dump` → `<mod_label>.dump.html` |
| Rapport | `tool/exporters/report.py` | `randputf report` → `<mod_label>.report.html` |
| Testeur | `tool/tester.py` | `randputf test` → `<mod_label>/<mod_label>.dump.html`, `<mod_label>.graph.html`, `<mod_label>.report.html`, contrôle + rejeu |

`generate --install` copie le mod dans `paths.factorio_mods` et met à jour `mod-list.json` sans modifier l'état de `randputf-exporter` ; l'exporter reste exclu de `active_mods` dans les dumps.

---

## 6. Dépannage

| Symptôme | Cause probable | Action |
|---|---|---|
| Aucun fichier créé | partie déjà existante au chargement du mod | créer une **nouvelle** partie avec l'exporter actif |
| Fichier dans un dossier inattendu | Flatpak/Steam | regarder sous `.var/app/com.valvesoftware.Steam/.factorio/script-output/` |
| `exporter_version` erroné | dossier du mod mal nommé | renommer exactement en `randputf-exporter_0.1.8` |
| `game_version_numeric = 0` | version de `base` illisible | vérifier `info.json` et `meta.game_version` dans le dump |
| `mod_label = vanilla` avec des mods actifs | seuls `base` et l'exporter étaient actifs | c'est normal : `base` et l'exporter sont exclus du libellé |
| Dump moddé non reconnu | dump ancien avec garde-fou `EXPORT REFUSE` | régénérer avec 0.1.8 |
| `mod_data` absent | jeu < 2.1.20 ou aucun prototype `mod-data` | c'est normal ; le tool a des replis |
| Erreur d'écriture dans la log | permissions sur `script-output` | vérifier les droits du dossier utilisateur Factorio |

Le log Factorio porte les messages `randputF exporter: ... écrits` ou `randputF exporter: échec d'écriture: ...`. Il n'existe pas d'autre canal de diagnostic dans le mod.

---

## 7. Historique court

| Version | Changement |
|---|---|
| 0.1.4 / 0.1.5 | Dump simple ; refus explicite si randputF est actif. |
| 0.1.7 | Ajout de `mod_data` pour les prototypes `mod-data` (lacs). |
| 0.1.8 | Schéma 2 : `active_mods`, `mod_label`, `mod_label_full`, `dump_file`, `game_version_numeric`, `order`, `flags` des entités, armes montées, buffers d'énergie, températures/couleurs de fluides, `research_unit_count_formula` ; nom qualifié + alias stable ; dumps moddés canonisisés. |

0.1.8 est la version à documenter, installer et comparer. Ne pas annoncer de 0.1.9.

---

## 8. Documents liés

- [developpement.md](developpement.md) — procédure courte d'installation et de récupération.
- [vanilladb.md](vanilladb.md) — schéma consommé par `VanillaDB`, prédicats de détection et inférences.
- [runtime.md](runtime.md) — ce que randputF fait des prototypes et pourquoi le dump moddé est modifié.
- [modules.md](modules.md) — place de l'exporter dans l'outillage.
- [testeur.md](testeur.md) — utilisation du dump par le testeur et les rapports HTML.
