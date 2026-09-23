# Idées et chantiers à développer (randputF)

Ce document répartit ce qui **reste à développer** en quatre grands chantiers
logiques :

- **A. Ressources au sol** — ce qui concerne les matières premières et la carte ;
- **B. Difficulté & monde** — biters, évolution, pollution, profils de difficulté ;
- **C. Progression & recettes** — quantités de craft, arbre technologique, déblocages ;
- **D. Écosystème & garanties** — cohérence et paires utiles du générateur.

Chaque point peut être gardé, corrigé ou écarté. Les chantiers clôturés
(forme des gisements ITEM `§A` — count = tuiles RÉELLES posées, cœur plein,
anneau dilué, hash déterministe miroir Lua/Python ; bordure des lacs `§A`,
vérifs bootstrap `C2`, bug `water_tile_type_names` `C4`,
doc §7.5 `C5`, anti-duplication `C6`, fabricateurs à recette fixe `C7`, audit
des tags `C8`, graphe de production `C9`, réseau de chaleur — triade
source/transport/sink garantie à la volée par `_ensure_heat_prereq`,
anciennes idées « déjà implémentées »)
sont retirés de ce document — ils sont décrits dans le README et `docs/`.

**Ordre conseillé** : A1 d'abord (il prépare les autres chantiers ressources et
la solvabilité non-infinie), puis C (progression), puis B (difficulté).

---

## A. Ressources au sol

### A1. Randomiser les ressources non-infinies ? (idée)

Idée (à trancher) : les ressources **non-infinies** (patches finis,
environnement bois/pierre/poisson, fluides non infinis) restent telles quelles
alors que les lacs/fluides infinis sont déjà randomisés. Deux voies possibles :

**(a) Les randomiser** — comme le reste de la seed (identité, richesse/volume
finis), sans casser la solvabilité du bootstrap. **Pilotage par une constante
on/off (`true/false`)** pour activer ou désactiver la randomisation (défaut : à
définir).

*FAIT — voie (a) branchée (branche `annexe`) : section `nonfinite:` dans
`config/settings.yaml`, `enabled: false` par défaut ; facteurs multiplicatifs
ALÉATOIRES (flux RNG dédié `randputF:nonfinite:`) par gisement sur la richesse
totale et le rayon. Invariant runtime préservé : le `count` d'un ITEM est
réévalué via `item_field_tiles(radius, well_seed)` — le champ posé par le mod
reste exactement le disque bruité, seul ratio richesse/tuile varie. Score :
`map_patches.apply_nonfinite_randomisation`, tests
`tests/test_nonfinite_pipeline.py`.*

**(b) Les laisser telles quelles**, en remplaçant juste le charbon — les 3
ressources non-infinies principales (poisson `raw-fish`, bois `wood`, roche
`stone`) restent inchangées, et le charbon **n'apparaît plus en patch** : il est
remplacé **par moitié de bois et moitié de roche** (le rôle de combustible se
reporte sur le bois + la roche). Variante minimaliste qui change le bootstrap
sans toucher aux quantités/identités des autres ressources.

*Prototype (voie a) : `tool/prototypes/nonfinite_randomisation.py`
(richesse/count/rayon, constante `enabled`) — non branché au pipeline. Dernier
chantier « ressources » à faire avant ceux de difficulté (B) et de progression
(C).*

### A2. Gisements profilés par la difficulté

Les gisements de la carte sont réglés **en fonction du niveau de difficulté**
de la seed (les knobs B1) : plus la difficulté est haute, plus les patches sont
**petits**, **peu riches** et **éloignés les uns des autres** ; plus elle est
basse, plus ils sont **grands**, **riches** et **proches** (l'inverse).

Le couple (taille, richesse, espacement) est dérivé du profil de difficulté de
la seed (déterministe via le PRNG) et appliqué à **tous** les gisements —
patches items, patchs fluides et lacs — pour rester cohérent avec la carte :
pas de nappes riches sur une seed infernale, pas de désert minéral sur une seed
tranquille.

Attention solvabilité : même en difficulté maximale, le bootstrap reste jouable
— le starter garantit des gisements minimums pour les ressources de départ
(iron, copper, coal, eau), assez grands, assez riches et assez proches pour les
premiers crafts ; la « rareté » pousse à l'exploration et à l'expansion, jamais
à l'impasse.

*Prototype : `tool/prototypes/rare_resources.py` pose une partie de la brique
(facteurs richesse/count), mais son axe est la DISTANCE au spawn — à réorienter
vers le profil de difficulté (B1), dont il dérivera chaque paramètre
(petit/pauvre/éloigné vs grand/riche/proche) — non branché au pipeline.*

---

## B. Difficulté & monde

### B1. Knobs de difficulté par seed

Chantier **difficulté pure** (ce n'est pas du contenu) : la seed devient un
profil de difficulté — `starting_area`, densité de nids/évolution, taux de
pollution par bâtiment, densité de falaises, biomes de départ (forêt = bootstrap
bois facile / désert = eau+bois durs). Ça colle au concept (« aléatoire
contrôlé »).

**Solvabilité 100 % garantie** : la difficulté ne touche **jamais** à
l'atteignabilité — tout reste déblocable, aucune voie coupée. Elle se joue
**principalement sur le nombre de ressources nécessaires** : les quantités
requises par recette / tech / science pack (coûts plus ou moins lourds), pas
sur des impasses. Attention quand même : pas de forêt trop pauvre en bois
pendant le bootstrap environnemental.

*Prototype : `tool/prototypes/difficulty_knobs.py`
(`DifficultyProfile.to_map_settings`) — non branché au pipeline.*

### B2. Biters / évolution / pollution

Inchangés pour l'instant (assumé §11). À revisiter via B1 : les knobs de
difficulté sont la brique naturelle pour les randomiser proprement (densité de
nids, facteur d'évolution, diffusion de pollution).

---

## C. Progression & recettes

### C1. Craft quantity

Randomisation des **quantités** des recettes (plus du pur 1-pour-1 : un
**facteur aléatoire** sur les volumes d'entrée/sortie), aujourd'hui non gérée.

*Prototype : `tool/prototypes/craft_quantity.py` (mode symétrique/asymétrique,
minimum 1 unité par ingrédient, déterminisme PRNG, constante `enabled`) — non
branché au pipeline.*

*FAIT (branche `annexe`) : passe post-assemblage branchée —
`tool/generator/craft_quantity.py`, flux RNG dédié, section `craft_quantity:`
de la config (`enabled: false`), montants jamais < `amount_min`, structure et
solvabilité intactes (le validateur ne lit que la structure). Voir
`docs/recettes.md §9.8` et `tests/test_craft_quantity_pipeline.py`.*

### C2. Tags de déblocage de l'arbre tech / sciences par bâtiment

**État : pas fait.** Aujourd'hui la contrainte « bâtiment avant usage » est
**implicite et pilotée par la recette** : le générateur ne pose jamais une
recette dans un atelier pas encore débloqué (`state.unlocked_buildings` — au
besoin il choisit un autre atelier obtenable ou le débloque sur le tas). C'est
une garantie de fabricabilité, pas une règle de progression.

Le chantier : introduire des **tags explicites** (comme `has_hidden_recipe`
pour les bâtiments à recette fixe, ou les tags du lab) qui **conditionnent le
déblocage de l'arbre technologique et des science packs au déblocage réel des
bâtiments** :

- un **science pack ne devient déblocable que si le bâtiment capable de le
  fabriquer a été débloqué** dans l'arbre de récursion ;
- des **branches entières de tech** se verrouillent/déverrouillent selon les
  bâtiments obtenus (ex. pas de tech « chaleur » tant que le fabricateur à
  recette fixe / la source de chaleur n'est pas débloqué).

Effet recherché : renforcer le « arbre de progression aléatoire » — le contenu
ne se résume plus à « chaque item a une tech », le joueur doit réellement
obtenir les machines pour débloquer ce qu'elles fabriquent. À concilier avec la
solvabilité 100 % (voir B1) : il s'agit de **réordonner/verrouiller** des
branches, jamais de les rendre inaccessibles.

### C3. Déblocage progressif des extracteurs — FAIT

**Implémentation** : `tool/generator/extractor_timing.py`, appelé dans
`pipeline.generate_seed` juste avant la 2e passe `usage_pass` (D2). La tech
gratuite `randputf-starter-extraction` ne garde que les extracteurs utiles dès
le spawn (ressource consommée par la chaîne initiale) ; un extracteur dont la
ressource n'est servie qu'en profondeur part avec le **premier consommateur**
(`max(premier-usage, atelier)` — le claim n'est jamais avant l'atelier qui
fabrique l'extracteur, contrainte U2 de D2) ; un extracteur jamais utilisé suit
le balayage §9.6 sur une tech payante tirée sur un RNG dédié déterministe. Le
rapport est stocké dans `seed["extractor_timing"]` et audité par
`tools/audit_usage.py` (invariants EXT1/EXT2/EXT3).

**Décisions actées** : le kit **garde son amorce** (1 item par extracteur,
même différé — l'œuf/poule du premier exemplaire reste brisé) ; le **choix de
l'extracteur par ressource reste le RNG actuel** (pas de préférence de
primitif).

**Validation** : `tools/audit_usage.py 0 201` → **U1 = 0, U2 = 0,
extracteurs = 0**, seeds violants = 0 ; pytest **672 passed** (dont
`tests/test_extractor_timing.py`, 3 tests × 20 seeds, et
`test_pipeline_invariants::test_extracteur_unlocke_avant_tout_consommateur`
actualisé : l'extracteur n'est plus forcément @tech 0 mais jamais APRÈS son
premier consommateur) ; seed 5 régénérée et réinstallée.

**Idée ouverte (extracteur à entrée fluide)** : il est possible dans Factorio
qu'un extracteur exige un **liquide en entrée** pour fonctionner (recette qui
existe dans le jeu). Aujourd'hui §8 interdit tout fluide dans la **recette de
craft** d'un extracteur — mais le cas serait l'inverse : le FONCTIONNEMENT
demanderait un apport liquide (typiquement les **foreuses minières
électriques**). À traiter en idée : il faudra un **nouveau tag** dans le dump
vanilla (ex. `requires_liquid` / extracteur à input fluide) pour détecter ces
entités et raisonner leur timing (un extracteur qui boit un liquide est un
consommateur de la ressource-liquide : le déblocage juste-au-besoin doit tenir
compte de sa propre source). Voir aussi la garantie « extracteur avant besoin »
§7 et l'anti-boucle §8.

### C4. Coûts de tech et rythme de déblocage (piloté par l'ardoise)

Deux axes à équilibrer une fois l'ardoise (B/tool difficulty) en place :

1. **Coûts des techs** : aujourd'hui les science packs ne sont pas calibrés —
   une tech peut coûter cher alors que son apport arrive tôt (et vice-versa).
   Les coûts devraient refléter la valeur du déblocage (rang dans la
   progression, utilité réelle via les tags C2, position dans l'ardoise).
2. **Contrôle de QUAND une tech se débloque** : c'est le vrai levier de rythme.
   Au lieu d'un simple ordre d'index (D2), conditionner le déblocage au
   **progrès réel dans l'ardoise** : n'autoriser la tech T que lorsque le joueur
   a obtenu (crafté/possédé) une fraction des items requis pour la run —
   ex. « X % du total de l'ardoise déjà produits » ou « les N items précédents
   du graphe maîtrisés ». Effet recherché : la progression se déroule « quand
   c'est le moment » (on ne déboule pas une tech profonde au tout début parce
   qu'on a eu sa clé par hasard), et chaque tech arrive alors que le joueur a
   déjà eu le besoin pratique qu'elle couvre — plutôt que de choisir au hasard
   dans un panier de déblocages.

Approximation C4 s'appuie sur : idx tech + ardoise (C1/B), graphe primaire DAG
(tests difficulty), et la garantie D2 (jamais de déblocage avant l'usage).
À trancher : mesure « items obtenus / total à avoir » au sens cumulé (ardoise)
ou au sens local (voisins du graphe).

---

## D. Écosystème & garanties

### D1. Support pairing générique

Les « paires utiles » ne sont garanties que pour les armes et les véhicules
(§12.1). Étendre le pairing au-delà (bâtiment de production → recette associée,
consommable → arme, etc.) : à préciser une fois les chantiers A/B/C avancés,
c'est un renfort de cohérence, pas une brique de contenu.

## D2. Garantie d'usage « dure » (bâtiment avant usage, niveau SEED) — FAIT

**Validation** : `tools/audit_usage.py 0 201` → U1 = 0, U2 = 0 ; pytest **669
passed** (dont `tests/test_usage_pass.py`, 2 tests × 20 seeds) ; seed 5
régénérée et réinstallée. Voir « Implémentation » (actualisée) en bas.

**État ANCIEN — garantie MONTANTE, pilotée par la recette (mou)** : le
générateur ne pose jamais une recette dans un atelier non débloqué
(`state.unlocked_buildings`, `_pick_building`) — au besoin il *débloque sur le
tas* (choisit un atelier quelconque et l'inscrit). C'est une garantie de
FABRICABILITÉ (C2) : chaque recette a un bâtiment jouable au moment où elle
existe. Mais rien ne garantit l'inverse sur la seed finale :

1. **Un bâtiment débloqué peut n'avoir AUCUN usage** — aucune recette de la
   seed `crafted_in`/`category` dessus → l'item débloqué est du contenu mort
   (déblocage par une tech, jamais utile ensuite) ;
2. **L'ordre des techs peut inverser l'usage** — une recette hébergée dans un
   bâtiment B peut être unlockée par une tech d'index **strictement inférieur**
   à celle qui débloque B lui-même (impossible à la création sur le tas, mais
   le panache du bootstrap/kit crée des exceptions à documenter).

**Garantie désirée — DEScendante, vérifiable sur la seed assemblée** : une
**passe post-récursion / avant relais** (`tool/generator/usage_pass.py`) analyse
le graphe final et GARANTIT par correction (pas juste détection) :

- **(U1) usage non-nul** : tout bâtiment **unlocké** (recette `randputf-<b>`
  présente) héberge ≥ 1 recette de la seed (par `crafted_in` ou une `category`
  dans ses `crafting_categories`) — sauf bâtiments **terminaux** dont l'usage
  est leur rôle moteur (lab, rocket-silo, générateurs : usage = produit qu'ils
  consomment au lancement / leur électricité, vérifié via le graphe) et sauf
  le kit du starter (bâtiments livrés par le kit, `starter.kit`).
- **(U2) ordre strict** : pour chaque recette R hébergée dans B (`crafted_in`),
  `index_tech(unlock(R)) ≥ index_tech(unlock(B))` — B est « la tech d'avant ».
  Exception assumée et vérifiée : les bâtiments du **kit** de départ (four de
  pierre, extracteur starter) et les bâtiments d'**auto-consommation** du
  bootstrap (§7 œuf/poule, déjà gérés par l'amorce du kit) — un bâtiment dans
  le kit est réputé débloqué en tech 0.
- **Correction (U2)** — par ordre de préférence, déterministe :
  1. **Bascule** : re-home R sur un atelier déjà débloqué `i_other ≤ i_recipe`
     du même pool (jamais si la source se retrouverait sans recette — U1) ;
  2. **Précéder R** : décaler le claim d'unlock de R sur le step qui débloque B
     → l'invariant devient une égalité. Refusé (exempté) si l'item de R est
     consommé par une recette débloquée AVANT B — c'est une
     **auto-consommation du bootstrap** (§7) : décaler R casserait la recette
     consommatrice, le déblocage précoce de R est voulu
     (`_reorder_claim` → `"consumed:<recette>"` → exemption) ;
  3. Sinon `warning` (jamais observé sur 0-200).
- **Correction (U1)** : bâtiment unlocké sans usage → soit **retirer** son
  déblocage (pas de contenu mort), soit lui **rattacher** une recette du même
  produit-d'atelier quand un candidat existe. Jamais de seed livrée avec un
  bâtiment mort.

**Implémentation** (actualisée) :
- prototype `tool/prototypes/usage.py` (dataclass `UsageConfig(PrototypeConfig)`,
  constantes `enabled` (défaut **true**), `kit_exempt` (bâtiments livrés par le
  kit, déduits de `StarterConfig`), `strict_order` (U2 on/off)) ;
- section `usage:` dans `config/settings.yaml` ;
- passe `tool/generator/usage_pass.py` appelée DEUX fois dans
  `pipeline.generate_seed` :
  - **passe primaire** après `ensure_rocket_chain`, AVANT `build_relay_recipes`
    (relais peuvent ré-utiliser un bâtiment mort et le masquer ; U1/U2 doivent
    être vérifiés sur le primaire avant leur création) ;
  - **passe finale** juste avant `build_linear_tech_tree`, sur l'ordre COMPLET
    `starter + welcome + ease + recursive + endgame` — les recettes relais et
    ease-up sont créées après la passe primaire et leurs techs prologue sont
    tôt alors que leur hôte peut être profond (cas seed 42, résolu par bascule
    vers l'AM-1 du kit) ;
  idempotente, déterministe (0 tirage RNG) ;
- audit dans `tools/audit_usage.py` (source unique de vérité `audit()`, relue
  par les tests) : lit les unlocks via `effects` `unlock-recipe` des techs
  FINALES (les clés `unlocks_recipes`/`unlocks_buildings` sont absentes des
  techs assemblées — toute lecture de ces clés est VACUÉE) ;
- invariants : `tests/test_usage_pass.py::test_u1_batiments_hotes_non_morts`
  (U1) et `test_u2_ordre_tech_avant_usage` (U2) — 20 seeds chacun, en plus du
  fuzz existant (667 → 669) ;
- stats sur 0-200 : passe primaire = 41 bascules U2 / 26 seeds, 71 rattachements
  U1 / 65 seeds, 0 warning ; exemptions bootstrap (reorder bloqué par
  consommation) sur seeds 36 (burner-generator→AM-2) et 83 (inserter→steel-furnace)
  — ces recettes ne peuvent ni être basculées (aucun hôte assez tôt à 2 slots
  item) ni être repoussées (leurs items sont consommés par le bootstrap :
  burner-mining-drill / pipe) ;
- tarring avec `progressive_extractors` (C3) : C3 échelonne le starter, la
  garantie U2 assure que tout déblocage d'extracteur précède son premier usage.

**Champs touchés** : `state.unlocked_buildings`, `state.steps`, ordre des
`technologies` (claims d'unlock déplacés), recettes (`crafted_in`),
`starter.kit`.

## D3. Prochain pas après D2 — SPEC

Une fois D2 en place, les chantiers C2 (tags bâtiment→tech) et C3 (extracteurs
progressifs) s'appuient dessus : C2 rend les tags explicites (déduits de la
garantie, plus implicites), C3 échelonne le starter en se reposant sur
« bâtiment avant usage » vérifié.

### Idées ouvertes (à trancher au fil du travail)

- **B1-style proche** : D2 pourrait être couplé à un audit `tool/audit/usage.py`
  en aval du pipeline (comme `audit/tags.py`) — rapport par seed des bâtiments
  morts au lieu d'une simple correction.
- **Connexion B1 (difficulté)** : à haute difficulté, des bâtiments volontaire-
  ment morts *pour la recette* mais utiles (cinglage, réacteurs) — la garantie
  U1 doit différencier « pas de recette hébergée » et « aucun usage gameplay ».
- **D1 pairing générique** : les paires utiles pourront réutiliser le même
  analyseur de graphe (consommateurs d'un bâtiment) au-delà des armes/véhicules.