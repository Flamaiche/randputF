# Dérives vs Factorio vanilla, oublis et bugs rencontrés

Catalogue des écarts de gameplay du mod par rapport à « Factorio normal », des choses oubliées et des bugs détectés — pour les corriger ou les assumer. Chaque entrée précise graine de départ (seed), symptôme, cause racine et état.

Retour : [docs/README.md](README.md).

---

## 1. Dérives de gameplay assumées (design du mod)

Ces écarts sont volontaires : le graphe est entièrement généré, aléatoire contrôlé, et ne ressemble pas au vanilla.

- **Recettes de fabrication des ateliers randomisées** : un `chemical-plant`, un `assembling-machine-2` ou un `oil-refinery` se fabriquent via une recette `randputf-<bâtiment>` dont les ingrédients sont tirés aléatoirement. C'est le principe du « tout-aléatoire », mais cela implique que l'ordre de fabrication des ateliers compte (voir le bug §2.1 qui découle de là).
- **Bâtiments à recette FIXE** (`is_fixed_crafter`) : boiler/heat-exchanger (et équivalents) n'ont pas une recette de craft classique mais une recette unique « fluide → fluide » (ou « item → item ») randomisée, portée par le bâtiment lui-même (assignation input/output stockée dans `building_fluid_assignments`). C'est le moteur de progression des fluides.
- **Science packs à base d'intermédiaires, pas de matières premières** : les packs de recherche exigent des items issus du graphe (intermédiaires), les matières premières environnementales sont exclues (§13).
- **Techs gratuites starter + prologue hand-craft** : le palier « bootstrap → sciences » se débloque par HAND-CRAFT d'un item (way vanilla automation/logistics), sans packs en labo.
- **Épaves et patchs item au sol** : un patch ITEM est ramassable à la main au startup (ressource finie, façon épave) et devient infini une fois une foreuse posée ; un patch FLUIDE exige un pumpjack (électricité) ; un lac une pompe offshore. Il n'y a pas de « remplaçant » : le graphe est entièrement le nôtre.
- **Extracteur requis au spawn** : la tech gratuite `starter-extraction` ne garde que les extracteurs utiles dès le spawn ; les autres partent au premier consommateur ou sur une tech payée (§9.6). Voir l'averto §3.2.
- **Lacs : pose runtime déterministe** (§7.5) : chaque lac est creusé par le jeu à l'init (`on_chunk_generated`), pas posé par le mapgen. Le mapgen ne pose 0 tuile de lac (override `property_expression_names["tile:<lac>:probability"]` = `randputf-no-water`, comme l'eau vanilla) ; la tuile reste créée/inscrite pour `set_tiles`, la palette et la liste du menu de génération. Une nappe discrète de rayon fixe par fluide choisi est positionnée sur un anneau équiréparti autour du spawn → aucune superposition, surface maîtrisée, tous les liquides pompables. Pourquoi (vécu) : le scatter `resource-autoplace` sur des tuiles faisait chevaucher les nappes de départ et laissait un seul liquide (le dernier, d'ordre le plus élevé) dominer ; un rework `autoplace tile` seul ne garantissait pas non plus un équilibre (vérifié headless). D'où le creusage `control.lua`. On conserve du système antérieur : couleur/copie de tuile, berge (redessinée au runtime par `set_tiles(..., correct_tiles = true)`), compatibilité pompe offshore.

## 2. Bugs corrigés

### 2.1. Fabrication d'atelier avec des ingrédients FLUIDES → ordre d'usage impossible

- **Seed** : 426 (sélectrique : balayage 301-499, `198/199`).
- **Symptôme** : le rejoueur bloque à la tech 12 (`military-science-pack`) : il exige `utility-science-pack`, fabriqué dans un `chemical-plant` ; or la recette `randputf-chemical-plant` (fabrication de l'item chemical-plant) exigeait 2 ingrédients fluides (`sulfuric-acid` + `petroleum-gas`) et était donc posée dans `oil-refinery` — unlocké à la tech 45 seulement. Toute la branche science (steps 11-12) était injouable tant que l'oil-refinery n'était pas débloqué ; U2 ne pouvait ni basculer (aucun atelier à ≥ 2 slots fluides unlocké avant 10) ni reorder (consommateur `nuclear-reactor` verrouille l'item).
- **Cause racine** : une recette de fabrication d'un BÂTIMENT-ATELIER peut consommer des fluides → l'item bâtiment doit être posé dans un atelier fluide (oil-refinery/chemical-plant), unlocké tard. Alors que le bâtiment est requis comme atelier tôt. §8 ne posait l'interdiction des fluides que pour les EXTRACTEURS (`_is_extractor_item`).
- **Fix** : `tool/generator/recipes.py` — la garde `_is_building_item_recipe` (remplace l'antérieure `_is_extractor_item`) couvre désormais tout bâtiment atelier OU extracteur : un bâtiment se fabrique uniquement avec des items (véritable anti-cycle + ordre d'usage des ateliers).
- **État** : ✓ corrigé (seed 426 → victory, researched 92).

### 2.2. Cycle d'hébergement MUTUEL créé par le ré-hébergement U2

- **Seed** : 255 (balayage 201-300, échec unique).
- **Symptôme** : le rejoueur bloque — `randputf-assembling-machine-2` est ré-hébergé (`REHOME … -> steel-furnace`) alors que `randputf-steel-furnace` est lui-même fabriqué dans `assembling-machine-2` : A se fabrique dans B qui se fabrique dans A. Le garde `_self_hosted` ne couvrait que les cycles directs (recette hébergée dans le bâtiment dont elle EST le produit).
- **Fix** : `tool/generator/usage_pass.py` — nouveau garde `_hosting_cycle` (fermeture transitive « B dépend de P via ingrédients + crafted_in ») branché dans les boucles de candidats de U1 et U2. Repli « précéder B » exclu.
- **État** : ✓ corrigé (255 → victory, researched 92).

### 2.4. Cycle d'hébergement LONG refermé par le ré-hébergement U1

- **Seed** : 1043 (balayage 1001-1500, échec unique).
- **Symptôme** : le rejoueur bloque — tech 18 coûte `utility-science-pack` (pistol → water), et `randputf-pistol` exige l'atelier `assembling-machine-2` intraçable. La chaîne de fabrication des ateliers tourne en rond : `AM2 in AM3 → AM3 in rocket-silo → rocket-silo in oil-refinery → oil-refinery in AM2` — aucun point d'entrée.
- **Cause racine** : le garde `_hosting_cycle` (2.2) parcourait le graphe dans le sens des consommateurs (P →* B : « qui exige déjà l'item de l'atelier cible ») et laissait passer le chemin forward (B →* P : « ce que l'atelier cible exige, up to le produit P »). Le rehome U1 (`REHOME randputf-assembling-machine-3 -> rocket-silo`) refermait ainsi une boucle à 4 maillons sans être détecté.
- **Fix** : `tool/generator/usage_pass.py` — `_hosting_cycle` construit le graphe « X require Y » (ingrédients + `crafted_in`) et marche depuis l'item de l'atelier cible vers P ; cycle ssi B →* P.
- **État** : ✓ corrigé (1043 → victory, researched 89).

### 2.3. Patch ITEM requérant une foreuse (modèle de mine erroné)

- **Seeds** : 249 (balayage 0-200) — et erreur de modèle globale.
- **Symptôme** : le rejoueur exigeait une foreuse pour chaque patch item (`_ensure_prepower_item_miner`), donc l'électricité → softlock fantôme.
- **Cause racine** : modèle utilisateur corrigé — un patch ITEM est hand-pickable au startup (ressource finie) ; il ne faut une foreuse que pour du volume infini ; un patch FLUIDE exige un pumpjack.
- **Fix** : `tool/replay/player.py` — `item_patch_resources` ajoutés aux buckets initial `_closure_items_buckets` ; `_infer_extractors` ne mappe plus les patchs item sur des foreuses.
- **État** : ✓ corrigé.

### 2.5. Jalon d'une raw gatée au 1er INGRÉDIENT alors qu'elle est requise comme ATELIER

- **Seed** : 1299 (balayage gaté 1200-1600, échec unique).
- **Symptôme** : en gaté, défaite au rejoueur (88/88 en baseline) — la tech 5 (`combat-combat-shotgun`) coûte `production-science-pack`, fabriqué du `lab` (craft main) + `electric-mining-drill` (craft main, 3×), chacun exigeant `stone-furnace`, une recette `crafted_in='steel-furnace'`. Or `steel-furnace` était jalonnée au tier 4 (son 1er ingrédient dans la chaîne fusée), donc introuvable au tier 0 pour fabriquer la machine → packs infondsables → dead-lock (la tech est prérequis du reste de l'arbre).
- **Cause racine** : le plancher d'une raw gatée n'était calculé que sur le 1er consommateur ingrédient ; il ignorait les usages comme machine (`crafted_in`) et la fermeture des coûts/déclencheurs des techs (packs de science → bâtiments → ateliers machines, etc.).
- **Fix** : `tool/generator/late_raws.py` — `_usage_floors` scanne désormais sur la partie refaite les consommations ingrédient + atelier + la fermeture transitive coût/déclencheur de chaque tech (préfixe des recettes débloquées ≤ index), avec défaut `max_tier` si jamais requis. `steel-furnace` est rétrogradée au tier 0.
- **État** : ✓ corrigé (1299 → victory, researched 84).

### 2.6. Ordre des effets `unlock-recipe` d'une tech non déterministe (set non trié)

- **Seed** : 1299 — révélé par le contrôle `PYTHONHASHSEED` 0/1 (pré-existant, baseline comme gaté).
- **Symptôme** : le `seed.json` diffère au byte près entre processus — les recettes `chemical-plant`/`oil-refinery`/`assembling-machine-1`/`assembling-machine-3` de la tech `randputf-combat-submachine-gun` tournaient selon l'ordre de hachage.
- **Cause racine** : `tool/generator/recursive_phase.py:854` construisait `step["unlocks_buildings"]` en itérant `state.unlocked_buildings - buildings_before` (set, ordre hash).
- **Fix** : `sorted(state.unlocked_buildings - buildings_before)`.
- **État** : ✓ corrigé — vérifié byte-à-byte sous hashseeds 0/1/2 sur seeds 37/412/1299 baseline + gatées ; garde élargi dans `tests/test_determinism.py` (seeds 1337 et 1299).

### 2.7. Gating « inerte » (jalons tous ≤ 0) rendant la passe B auto-cassante

- **Seed** : 1757 (balayage gaté 1600-2000, échec unique).
- **Symptôme** : en gaté, défaite au rejoueur à la tech 21 (`randputf-combat-submachine-gun` — `military-science-pack` exigeant `assembling-machine-2`, unlock plus loin dans l'arbre) alors que la disponibilité était identique au baseline (toutes les raws gatées au tier 0 : jelly/petroleum/steel-chest…). Victoire 89/89 en baseline.
- **Cause racine** : un gating au jalon 0 ne retient rien de terroir — rejouer la passe B ne produisait qu'un ARBRE différent sans changer la dispo.
- **Fix** : `tool/generator/pipeline.py` — quand tous les jalons du plan sont ≤ 0, rendre la passe A telle quelle (byte-identique à l'historique, pas d'export `late_raws`).
- **État** : ✓ corrigé (1757 → victory 101/101, seed byte-identique à la baseline ; garde `test_seed_1757_gating_inerte_victoire_comme_baseline`).

### 2.8. Dépendance à l'ordre des seeds d'un même processus (mutation config)

- **Seed** : 1269 — perte en gaté selon la position dans le processus (victoire 101/101 en process vierge). Pré-existant, amplifié par la déviance 2.7.
- **Symptôme** : le balayage (toutes seeds dans un même process) montrait une défaite qui ne se reproduisait pas isolément.
- **Cause racine** : `cfg.setdefault("starter", {})["deferred"]` de la passe B mutait le sous-dict `starter` partagé du config du caller (copie superficielle entre seeds) — jamais réinitialisé par les seeds inertes (2.7) qui ne repassent pas par là → une seed inerte héritait du `deferred` de la seed non-inerte précédente.
- **Fix** : copie défensive (`cfg = dict(cfg)`, `cfg["starter"] = dict(...)`) — aucune mutation du config du caller.
- **État** : ✓ corrigé — 1269 byte-identique (hash `c8c55ecf05e4`) en process vierge, après 1 et après 1400 seeds ; sweep gaté 0-2000 rejoué : 2000 victoires / 0 défaite ; voir §7 de `docs/nondeterminism.md`.

## 3. Avertissements résiduels (à surveiller, non bloquants)

### 3.1. `usage_pass warning: <four>: consommé mais aucun candidat à rattacher`

- **Symptôme** : `stone-furnace`, `steel-furnace`, `electric-furnace` apparaissent en consommé — leur item est un INGRÉDIENT d'autres recettes (ex. `randputf-boiler` consomme `steel-furnace`, `randputf-assembling-machine-3` consomme `stone-furnace`, `randputf-tank` consomme `electric-furnace`) — mais U1 ne trouve aucun candidat pour leur rattacher une recette hébergée (tous les hôtes possibles déjà occupés / cyclent / pré-élec). Le contenu n'est pas mort (usage = être consommé et/ou recette d'atelier ailleurs), seulement pas hébergé sur CE four.
- **Observation** : fréquent (plusieurs warnings par sweep de 100). Non bloquant.
- **État** : balayages gatés 0-2000 à 2000/2000 victoires — ce warning ne dégrade pas la jouabilité.
- **À trancher** : acceptable (usage consommation) ou chercher un rattachement quand même (pool plus large de candidats).

### 3.2. `extractor_timing: <extracteur> requis au spawn mais atelier N >= plateau gratuit 2 — fabricable seulement en profondeur`

- **Symptôme** : un extracteur est utilisé dès le spawn (consommé par la chaîne initiale) mais sa recette de fabrication est posée dans un atelier dont l'index ≥ 2 (pas dans le plateau gratuit) → on ne peut le fabriquer qu'après avoir débloqué cet atelier.
- **Constat** : en pratique le rejoueur réussit quand même (le « requis au spawn » est tôt mais la contrainte réelle reste l'atelier). Averto seulement.
- **À trancher** : si un cas réel bloque, forcer l'extracteur requis-spawn à un atelier du plateau gratuit (craft à la main).

## 4. Choses « oubliées » par rapport au vanilla (détectées)

- **Fabrication d'atelier parfluide** : corrigé (§2.1) — c'est l'oubli le plus structurant : un bâtiment ne doit jamais se fabriquer avec un fluide.
- **Modèle de mine des patchs item** : corrigé (§2.3) — le rejoueur et le générateur avaient dérivé vers un « mining obligatoire » incompatible avec l'amorce.
- **Graphe entièrement le nôtre (pas de remplaçant)** : rappel acté — aucune substitution « vanilla-like » tolérée : si un item boucle, on corrige le graphe, on ne remplace pas l'item.
