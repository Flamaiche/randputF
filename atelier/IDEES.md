# Idées et chantiers à développer (randputF)

> **Document de travail, non revu depuis son écriture.** Ses chemins,
> ses chiffres et le code qu'il cite peuvent avoir changé depuis. L'état
> courant est dans [`docs/`](../docs/) et
> [`CHANGELOG.md`](../CHANGELOG.md).

## Exécutable Windows pour les joueurs (avec l'interface graphique)

**Pourquoi.** La voie rapide du README livre le mod de la seed 5, déjà
généré. Mais **toute autre seed** impose aujourd'hui d'installer Python
(`pip install .`). Un joueur Windows sans Python ne peut donc pas générer sa
propre seed : c'est la dernière barrière à un parcours joueur complet, et la
seule qui reste.

**Dépend de l'interface graphique.** L'exécutable n'est pas un but en soi, il
est le véhicule de l'IG. Le produire avant l'IG donnerait un double-clic sans
écran — donc à traiter dans le même chantier que l'IG, pas avant.

**Livrable attendu.** Un `.exe` qui embarque `mod/`, `data/` et `config/`,
c'est-à-dire exactement les assets que le wheel embarque déjà (liste de
paquets explicite dans `pyproject.toml`). Le point de départ est donc le paquet
installé, pas le checkout.

**Invariant à protéger — le point non négociable.** Le témoin de
déterminisme ne vaut que si le mod produit par l'exe est identique à celui
produit par la CLI. L'exe figé est un environnement d'exécution différent :
pas de checkout, ressources embarquées, pas de `pip install .`. Sans test, il
peut diverger du CLI sans que rien ne le voie — et le témoin ne garantirait
plus rien pour le joueur qui l'utilise. Il faut donc un test qui génère une
seed via l'exe et compare le md5 à celui du CLI, exactement comme la
vérification déjà faite en local lors du bump 0.0.1.

### Ce que fait le projet de référence

`vaibhavvikas/factorio-mod-downloader` (le plus cité pour les outils mod
Factorio) **n'est plus en Python** : sa v0.4.0 est en Rust + Tauri v2, avec
binaires natifs Windows `.exe` / macOS `.app` / Linux. L'argument de vente de
la réécriture est explicite dans sa note de version : « no browser drivers, no
python scripts ».

Ses versions Python antérieures sont conservées dans des forks
(`Sebastianpolska/factorio-mod-downloader_fork`) et montrent le cahier des
charges d'origine : `customtkinter` + `pillow` + `requests` + `selenium` +
`chromedriver-autoinstaller`, distribuées en `.exe` PyInstaller `--onedir
--windowed`. Le README expliquait qu'au premier lancement l'app **téléchargeait
30 à 35 Mo de chromium-drivers**.

**Ce qu'il faut en retenir : le poids ne venait pas de Python.** Il venait de
`selenium` — le projet scrapait le portail de mods avec un navigateur
automatisé. Passer à Rust a supprimé le navigateur, pas le langage. Un autre
gestionnaire de mods, `Musyoka2020-eng/FactorioManager`, est en Python +
tkinter + PyInstaller (fichier `.spec`) et fonctionne ; il se limite au
Windows pour le `.exe`.

### Pourquoi randputF est un cas plus favorable

Le problème résolu par ces projets est le **réseau** : portail de mods à
interroger, jeton d'authentification, téléchargement HTTP. randputF n'a
**aucune dépendance réseau** — `tool/` ne fait aucun appel HTTP, et les
prototypes vanilla viennent d'un dump JSON embarqué (`data/vanilla_dump.json`).
Il n'y a ni portail à scraper, ni pilote à télécharger, ni jeton à gérer.

Et générer un mod est **plus simple** que télécharger un mod : pas de client
HTTP, pas d'API de portail. Le `.exe` embarque exactement les mêmes assets que
le wheel (`--add-data "mod;mod"`, `"data;data"`, `"config;config"`) et se
contente d'appeler le générateur. Le produit est le mod en local, pas un
téléchargement.

Voie retenue : **tkinter pour l'IG v1** (inclus dans Python, zéro dépendance),
**PyInstaller pour l'exe**. Le passage à l'IG suffit à ouvrir ce chantier ;
l'exe n'est pas un chantier séparé.

## Four : deux recettes au même ingrédient (auto-sélection) — RÉSOLU

**Observé en test.** Un four peut héberger plusieurs recettes randomisées à
**un seul ingrédient**. Cas réel sur la seed courante : `steel-furnace`
porte 5 recettes (`randputf-coal` puisé dans `steel-furnace`, etc.). Si deux
d'entre elles consomment le **même** ingrédient, Factorio prend toujours la
première venue : la seconde est inatteignable — le joueur insère l'item et
obtient systématiquement l'autre produit.

**Mécanique Factorio (confirmée).** Un four n'a pas d'écran de choix de
recette : il **auto-sélectionne** d'après l'item inséré, et à ingrédients
égaux c'est la première recette du prototype qui gagne. Ce n'est donc pas un
bug du mod mais un comportement du four. Les ateliers (assembling) ne sont
pas touchés : le joueur y choisit la recette (`crafted_in` ne fait que
restreindre la liste).

**Discriminant retenu : le tag `auto_select`.** Ce n'est pas « 1 slot » ni la
seule catégorie `smelting`. L'exporter (`exporter/control.lua`,
`auto_selects_recipe()`) renseigne ce tag dans `data/vanilla_dump.json`, lu par
`tool/parsers/vanilla.py` et exposé sur `BuildingDef.auto_select`
(`tool/common/db.py`). Bâtiments concernés : `stone-furnace`,
`steel-furnace`, `electric-furnace`, **et `rocket-silo`** (qui héberge
beaucoup de recettes, plusieurs slots).

**Garde en deux temps.**

1. **Garde à la création** (`tool/generator/recipes.py`). Le bâtiment est
   choisi *après* l'échantillonnage des ingrédients : `_pick_building`
   **préfère** un candidat sans conflit. Sinon `_make_recipe` re-tire la
   recette en ne bannissant que les ingrédients **effectivement en conflit**
   (`ban |= occupied & {...}` — bannir tout l'occupé épuisait le pool des
   relais, cf. pool singleton), borné par
   `_AUTO_SELECT_RESAMPLE_ATTEMPTS = 4`. Une recette n'est jamais perdue.
2. **Passe aval `_correct_auto_select`** (`tool/generator/usage_pass.py`,
   appelée dans `enforce_usage` **avant** U2/U1). Elle déplace une recette en
   conflit vers un atelier alternatif **sans conflit** (`_auto_select_target` :
   `_fits`, pas d'auto-hébergement, pas d'électricité pour une recette starter
   gratuite, pas de cycle d'hébergement — ce dernier étant **relaxé** pour une
   recette à recette jumelle), puis recale son claim d'unlock. Replis quand
   aucun atelier alternatif sans conflit n'existe :
   - **retirer l'ingrédient en conflit** (recette multi-ingrédients), même
     esprit que le repli « suppression des fluides » de `_make_recipe` ; on
     garde ≥ 1 ingrédient par recette ;
   - **renvoyer une recette starter gratuite au craft manuel** (retrait de
     `crafted_in`/`category`). C'est le cas des fours 1-slot
     (`stone-furnace`/`steel-furnace`) saturés : deux recettes starter
     gratuites mono-ingrédient n'ont ni atelier alternatif (bâtiments
     électriques interdits avant l'électricité) ni ingrédient à retirer ; le
     craft à la main est une voie valide, la recette reste produisible.


**Validation.** Balayage **2000 seeds** (`tool/service.py` via
`generate_seed` + rejoueur toutes les 200) : **0 collision four, 0 échec de
génération, 0 échec de rejeu**. Tests dédiés :
`test_pipeline_invariants.py::test_auto_select_ingredients_disjoints`
(seeds 0/5/36/43/57) et `test_auto_select_repli_four_1slot` (seeds
455/847/1240, repli craft manuel).

**Multi-ingrédients.** Avec `item_input_slots ≥ 2`, l'ambiguïté devient un
recouvrement partiel (deux recettes satisfiables à la fois) que « entrées
disjointes » couvre aussi, au prix d'un pool plus contraint ; traité par le
même re-tirage au niveau de l'ingrédient.

## Taxonomie `medium` : nommer les milieux « lake » et « deposit »

**Statut (2026-11-16) : fait.** Renommage appliqué dans le parseur, `BuildingDef`, la démo, l'audit, les tests et les docs. Le pumpjack de la démo est désormais `medium="deposit"` ; le silo est retrouvé par `is_rocket_parts_crafter`.

**Pourquoi.** Le champ `medium` des extracteurs (docs/tags.md §6) décrit le
**milieu** d'où l'on tire : `water` = un plan d'eau (offshore-pump),
`fluid` = un gisement de fluide (pumpjack), `ground` = le sol (drill).
Ce sont des labels de taxonomie modpack, mais `water` entre en collision
avec le **nom de fluide** vanilla : « medium = water » se lit « pompe le
fluide water » alors que le sens est « tire d'un lac » — lac qui, dans
randputF, peut contenir n'importe quel fluide pipable (docs/starter.md :
un fluide par lac tiré, l'eau vanilla est effacée de la carte). `fluid`
est tout aussi ambigu (quel fluide ?).

**Correction retenue.** Vocabulaire anglais, cohérent avec le reste de la
taxonomie : `water` → `lake`, `fluid` → `deposit`, `ground` inchangé.
Renommer aussi les **booléens dérivés** — `is_water_extractor` →
`is_lake_extractor`, `is_fluid_extractor` → `is_deposit_extractor`
(`is_ground_extractor` inchangé) : « water extractor » est doublement faux,
le lac ne contient pas forcément de l'eau. Le champ et les booléens ne
sortent jamais du Python (aucune occurrence dans `mod/`, `config/` ni les
JSON générés) : renommage interne, sans compatibilité disque.

**Étendue appliquée.** Parseur, `BuildingDef`, démo, audit, tests et docs.


## Canonisation des recettes préfixées d’un dump moddé

**Statut (2026-11-16) : fait.** Deux compléments indissociables.

1. **L’exporter expose l’état réel.** `dump_recipes()` et
   `dump_technologies()` ajoutent `enabled` et `hidden`. Les prototypes
   neutralisés par `data-final-fixes.lua` restent donc dans le dump avec
   tous leurs liens, mais portent `enabled = false` et `hidden = true`.
   On ne supprime plus les recettes vanilla du JSON : le dump reste une
   photographie complète et on sait laquelle est active.
2. **La DB canonise par produit.** Pour un produit `X`, si une recette
   `randputf-X` existe et n’est pas `hidden`, elle devient la recette
   canonique ; la recette vanilla `X` est ignorée par la génération. La
   normalisation retire le préfixe pour la **clé logique** (`X`) mais
   conserve le nom réel `randputf-X` dans `VanillaDB.recipes`, sinon les
   effets de technologies et les liens du dump seraient cassés.
   `VanillaDB.canonical_recipes` porte le mapping `X -> randputf-X`.
   Les autres recettes préfixées (`randputf-ease-X`, `randputf-relay-X`,
   recettes de fluides…) restent des alternatives, pas des remplacements.
   `build_vanilla_seed()` filtre aussi les entrées `hidden` et applique le
   même repli de préfixe pour les anciens dumps sans ces champs.
   Les items, fluides et entités déjà préfixés (armes de véhicules,
   `randputf-neutre`, ressources `randputf-oil-*`) sont conservés dans
   `VanillaDB.modded_items` / `modded_fluids` / `modded_buildings`, hors des
   pools de génération : les re-randomiser produirait des recettes
   `randputf-randputf-…`.

**Garde conservée.** Les artefacts à double préfixe
(`randputf-randputf-…`) sont ignorés : un dump déjà randomisé deux fois ne
doit pas empiler les couches. Le dump vanilla historique reste la
référence de déterminisme ; un dump moddé décrit désormais l’état réel du
mod et peut donc produire une seed différente, ce qui est attendu.

## Câbler le rejoueur dans `generate` (garde de sortie)

**Pourquoi.** Le rejoueur prouve la solvabilité par simulation mais n'est
branché nulle part dans la génération : `generate_with_retry`
(`tool/service.py`) s'arrête au validateur statique
(`validate_seed`/`validate_pipeline`). La preuve vit seulement dans les
sweeps et la suite de tests (1501/1501 victoires mesurées).

**Recommandation (non approuvée).** Dernier garde après la validation
statique : `FakePlayer(db, seed).play()` sur la seed retenue ; défaite →
essai suivant, comme les autres rejets. Coût : une rejouée par seed
acceptée (~1 s mesuré). Bénéfice : plus AUCUNE seed injouable ne peut
sortir, même si un invariant statique vient à manquer une dérive. À
décider : budget max d'essais (aujourd'hui 10) suffisant si le rejoueur
ajoute des rejets ?

**État.** Refusé implicitement jusqu'ici (le rejoueur est un audit
externe, volontairement hors du chemin de génération). À rouvrir le jour
où l'interface graphique expose `generate` directement.

## Noms vanilla en dur côté outil — état du chantier

Principe : l'outil ne doit porter **aucun nom d'item vanilla** ; tout se
dérive des faits du dump. Avancement (2026-11-16) :

- **Nettoyé** — `tool/replay/player.py` : `VICTORY_ITEMS` et le littéral
  `"satellite"` supprimés (victoire = `db.rocket_chain` dérivée :
  `rocket_parts_required` → recettes de fusée → ingrédients, produits de
  lancement par `rocket_launch_products`) ; garde-fou lab par tag
  `is_research` ; fallbacks `"offshore-pump"`/`"pumpjack"` de
  `_infer_extractors` retirés (candidats par tags uniquement, une base
  sans pompe ne pompe plus rien). `tool/generator/endgame_phase.py`,
  `map_patches.py` et `recursive_phase.py` retrouvent le silo par
  `items_for_building_tag("is_rocket_parts_crafter")` ; `tool/__main__.py`
  le retrouve par son type.
- **Restants, par design** — `tool/common/tagsets.py` (`ROCKET_CHAIN`,
  `ENVIRONMENTAL_ITEMS`, `VEHICLE_GUNS` : choix de conception consignés
  docs/tags.md §14).
- **Restants, à reprendre** — `tool/audit/difficulty.py`,
  `tool/common/demo.py` (base synthétique de test : tolérable mais à
  aligner sur les faits si le dump change), `tool/exporters/seed_graph.py`.
