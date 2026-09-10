# Idées, constats et corrections (workshop randputF)

Ce fichier collecte l'analyse demandée lors du workshop :

1. les mécaniques Factorio importantes pour la randomisation et leur couverture ;
2. la vérification de la bordure des lacs (et leur génération) ;
3. des idées de rajouts/corrections.

À valider point par point : chacun peut être gardé, corrigé ou écarté.

---

## A. Vérification de la bordure des lacs

**ACTÉ — l'ensemble du chantier lacs est clos** (A1→A6 + compléments runtime) :
1. bordure des lacs robuste (table Lua locale `lake_borders`, plus de clé prototype) ;
2. couverture complète via `water_tiles` (les 7 noms) ;
3. hashing Lua déterministe (`seed_hash`/`map_seed_hash`) pour `seed1` du mapgen ;
4. exclusion du spawn / site de crash du placement des lacs ;
5. un lac par fluide (échantillonnage sans remise dans `lakes.py`) ;
6. coupe nette des lacs (`variants.empty_transitions`) — réservée au **fantôme blanc** (`randputf-lac-neutre`) avant remplissage ; le remplissage réel redessine les berges par `set_tiles(..., correct_tiles = true)` (`fill_lake`, `control.lua`) : **tous les lacs sont bordés** (plus de parité « 1 lac sur 2 ») ;
7. **pompe offshore de lac** : la pompe côtière affiche nativement le fluide de sa tuile source (2.0, `tile.fluid`) — aucun tooltip custom nécessaire (pas d'entité hoverable sur la tuile lac).

Point résidu : la précision Lua au-delà de 2^53 (~9e15) sur les grosses seeds — **résolu/écarté** : le hashing est fait côté Python (`random.Random(f"randputF:{seed}")`), la seed y arrive en chaîne ; l'arithmétique brute sur `seed_value` n'intervient plus (§16 README).

---

## B. Mécaniques Factorio importantes pour la randomisation — couverture

**Bien couvert :**
- recettes / bâtiments / slots / directives (§5) ;
- extraction items-only + anti-cycle (§8) ;
- électricité amorçable à la main + pylône garanti (§10) ;
- munitions d'armes de poing calées (garantie jouable, §11) ;
- véhicules + munitions « dispatch » ≤ 3 techs (§12.1) ;
- science packs sans ressource brute (§13) ;
- chaîne fusée + silo (§14) ;
- clamp des non-empilables (§9.6) ;
- triggers hand-craft valides / pool gelé (§9.3) ;
- relais bootstrap ressources non-infinies (§9.5).

**Écartés volontairement / à surveiller :**
- **Biters / évolution / pollution** — inchangés (assumé §11). Voir idées B/C ci-dessous.
- **Quality (2.0)** — non traité (contenu seulement).
- **Support pairing générique** — les « paires utiles » ne sont garanties que pour
  les armes et les véhicules. Voir idées.

---

## C. Idées de rajouts et corrections (priorisées)

> **Nomenclature** : les blocs C1→C6 ci-dessous correspondent aux numéros des
> réponses utilisateur (1→6). Chacun est marqué ✔ **fait** ou **à voir**/**à
> développer**. Les anciennes idées du workshop « déjà implémentées » (énergie,
> équilibre cons/prod, compagnons, landfill, energy_required) sont traitées plus
> bas dans « Déjà implémenté », hors de la numérotation C1→C6 pour lever toute
> ambiguïté.

**C1. [à développer — Randomiser les ressources non-infinies] (dernier point
avant C3/B/D)** : les ressources **non-infinies** (patches finis, environnement
bois/pierre/poisson, fluides non infinis) restent telles quelles alors que les
lacs/fluides infinis sont déjà randomisés. → Les **randomiser** comme le reste
de la seed (identité, richesse/volume finis), sans casser la solvabilité du
bootstrap. **Pilotage par une constante on/off (`true/false`)** pour activer ou
désactiver la randomisation (défaut : à définir).

**C2. [✔ fait — Vérifs bootstrap / patches]** : vérifier que (a) les **patches et
ressources infinies** tirés sont **valides / les bons** (compatibles, cohérents),
et (b) le **début de partie est jouable** (premiers crafts possibles) — pour ne
**pas avoir à ajouter de ressources au départ** juste pour rendre les crafts
possibles.
*Implémenté : les **lacs** comptent désormais comme sources externes obtenables
dans `validate_pipeline` (anti-cycle / progressivité / pipe-rule), et
`_check_progressivity` inclut l'**environnement** dans le pool initial (corrige
le faux positif `stone`).* (IDEES C6 + C2 partagent cette logique.)

**C3. [à développer — Difficulté contrôlée] Knobs par seed** : `starting_area`,
densité de nids/évolution, taux de pollution par bâtiment, densité de falaises,
biomes de départ (forêt = bootstrap bois facile / désert = eau+bois durs). Ça
colle au concept (« aléatoire contrôlé ») : la seed devient aussi un profil de
difficulté. Attention solvabilité : pas de forêt trop pauvre en bois pendant le
bootstrap environnemental.

**C4. [✔ fait — Bug `water_tile_type_names`]** : cette variable globale est
utilisée avant définition (`mod/data-updates.lua`). Le fallback couvre le cas où
vanilla ne la fournit pas. (Mesuré 0 tuile d'eau : le résultat est bon.)

**C5. [✔ fait — Doc §7.5]** : un lac bordé s'appuie sur le biome environnant
(grass/sand) et la coupe « net » est asymétrique (terre dure / lac fondant,
redessinée au runtime par `correct_tiles = true`).

**C6. [✔ fait — Éviter la duplication d'une même ressource patch/lac]** : une même
ressource brute n'apparaît qu'UNE fois sur la carte (patchs item + patchs fluides
+ lacs). Les lacs sont tirés AVANT les patchs ; `generate_patches(lake_resources=...)`
évite de re-tirer un fluide déjà en lac, et la réparation électricité évite aussi
les ressources déjà posées. Vérifié sur 60 seeds : 0 chevauchement. Test de
régression : `test_c6_aucune_ressource_dupliquee_sur_la_carte`.

### Déjà implémenté (idées plus anciennes du workshop)

- **Énergie « seed sans électricité amorçable »** (`resolve_electricity` :
  shuffle/test/réparation par patch forcé, 20 essais puis erreur, §10).
- **Équilibre production/consommation** (`ProgressionState` balance,
  `record_recipe`, `balance_factor`, §C2 du README).
- **Companion guarantee** (`_dispatch_companions` : roboport↔robots,
  solaire↔accumulateur).
- **Landfill si lacs** (`_ensure_landfill` dans le starter, §7).
- **Randomiser `energy_required`** (`roll_energy`/`energy_per_ingredient`).
- **Patchs « petites nappes riches » / pose explicite des gisements (§6.5)** :
  les patchs item ET fluide ne sont plus dessinés par le mapgen. La seed fournit
  pour chaque patch un **centre** (cluster serré au spawn), un **rayon** et un
  **nombre aléatoire de blocs/puits** (`wells_per_patch`, défaut `[3, 8]`) ;
  le mod les **pose au runtime** (`create_entity` + `entity.amount`), dispersés
  aléatoirement autour du centre (jamais alignés), un PRNG par bloc/puits pour
  rester déterministe quel que soit l'ordre des chunks.
  Le premier gisement est toujours proche du spawn (~25 tuiles) mais les
  gisements restent resserrés — fini les grandes étendues alignées du vanilla.
- **Lecture des tags sur TOUS les bâtiments** : passage systématique sur
  chaque bâtiment/entité de la base pour lire ses tags (`is_*` §1–§8,
  `is_fixed_crafter`, `has_hidden_recipe`…) et vérifier qu'ils sont
  correctement pris en compte par la randomisation. Implémenté par
  `tool/audit/tags.py` (CLI `randputf audit`, invariants d'orthogonalité/
  cohérence sur le dump réel + la démo) et croisé par le check consommation
  par tag (`tag_verify.py`, hors repo). Référence : `docs/tags.md`.

---

**C7. [implémenté — Fabricateurs à recette fixe = éléments de l'arbre]** : le
boiler/heat-exchanger (bâtiment à recette fixe) est **un élément déblocable comme
n'importe quel autre** de l'arbre de récursion, pas un sous-produit de `building_fluids`.
Quand un **fluide est débloqué** dans l'arbre, **forcer l'utilité** du fabricateur :
lui **générer sa recette** « fluide → fluide » pour qu'il **produise ce fluide**
(output = ce fluide, input = fluide déjà obtainable ≠ output), et le placer au
**même niveau de recherche** que ce liquide. `building_fluid_assignments` découle
alors de la recette (réellement jouable), jamais indépendamment. Double détection
par **capacités** (aucune liste de noms) :
- tag large `has_hidden_recipe` = « a une RECETTE cachée » = une VRAIE recette
  (entrée item/fluide/**combustible** — ``item_input_slots``/``fluid_inputs``/
  ``fuel_categories`` — et sortie item/fluide —
  ``item_output_slots``/``fluid_outputs`` **ou** les résidus de combustion
  ``fuel_residues``) non accessible comme recette de craft AVANT la
  transformation. Le combustible est un pseudo-ingrédient d'entrée (sans lui
  la machine ne tourne pas). En vanilla : **boiler, heat-exchanger et
  nuclear-reactor** (le réacteur : un item quelconque en pseudo-combustible →
  un item en résidu, depleted-uranium-fuel-cell = la « recette cachée »
  item → item, normalisée sans référence à « nuclear »). Les autres
  générateurs/extracteurs/lab (soleil→élec, champ→ressource, packs→recherche :
  sortie non-recevable) n'ont PAS cette signature → mécanique moteur, jamais
  taggés (soustraits du pool des ateliers par ``_is_atelier``, aucune catégorie
  valide). La CHALEUR du réacteur (sortie « spéciale » ``produces_heat``,
  traitée plus tard comme l'électricité) reste une sortie non-recettable :
  il est donc RÉVÉLÉ (taggé) mais n'est jamais un atelier (aucun fake
  ``crafted_in``) ;
- sous-ensemble `is_fixed_crafter` = transformer avec sortie (fluide OU item)
  → **seuls** eux reçoivent une recette randomisée ; les variantes item
  (équivalents de mods) sont gérées de la même façon (output item non encore
  produit, inputs déjà obtenus). En vanilla `is_fixed_crafter` =
  `{boiler, heat-exchanger}` (seuls transformateurs à sortie fluide) ;
- sous-ensemble `is_fixed_fluid_crafter` = transformer avec entrée ET sortie
  fluide → le **pairing C7** « fluide introduit → fabricateur » et
  `building_fluid_assignments` (filters de fluid boxes) n'utilisent QUE cette
  variante ; en vanilla elle coïncide avec `is_fixed_crafter`.

**C8. [à développer — Programme de vérification des bâtiments inutilisés]** : écrire
un programme qui vérifie, sur une seed donnée, quels **bâtiments ne sont pas
utilisés** — soit jamais débloqués, soit débloqués mais **jamais utilisés
comme fabricateur** (`crafted_in` d'aucune recette). L'objectif est de repérer les
bâtiments « morts » ou sans utilité réelle dans la seed générée, pour traquer les
transformateurs/ateliers qui devraient jouer un rôle mais n'en jouent aucun.
Le tag `has_hidden_recipe` est la base de ce programme : toute machine taggée
(boiler/heat-exchanger en vanilla) doit être **routée** : recette randomisée
assignée (`is_fixed_crafter`) — jamais laissée tomber au sol « sans recette »
(le boiler sans recette était le cas de cette classe, résolu en C7).

**C9. [✔ fait — Graphe de production visuel à la génération]** : quand une
seed est générée, produire un **graphe des items** : un nœud par item, une
**arête par dépendance de craft** (item → ingrédient), chaque arête
**étiquetée par la quantité** nécessaire au craft (`amount` de l'ingrédient).
Sortie : un graphe **interactif autonome** `output/randputF_0.1.0/seed.graph.html`
généré pendant `--out` (à côté de `seed/seed.json`, **jamais** dans `mod/`
installé — pas de pollution du mod en jeu), rendu par Graphviz (`dot -Tsvg`)
depuis un `.dot` intermédiaire effacé, icônes embarquées en data-URI. Les
ressources brutes (patches, lacs, environnement) sont en ellipse grise, les
science packs en boîte orangée ; plusieurs recettes pour la même paire
produit→ingrédient regroupent leurs quantités. But : visualiser la
profondeur/ramification des chaînes (linéarité du départ, boucles), vérifier
la faisabilité d'une seed en dev.

---

## D. À développer (prochaine étape)

- **Randomisation des ressources non-infinies** — avec une **constante on/off**
  (`true/false`) pour activer ou non la randomisation (dernier point avant C3/B).
- **Section D — Craft quantity** : randomisation des **quantités** des recettes
  (plus du pur 1-pour-1 : un **facteur aléatoire** sur les volumes d'entrée/
  sortie), aujourd'hui non gérée.
- **Section B — Biters / évolution / pollution** (voir B ci-dessus).
- **C3 — Knobs de difficulté par seed** (voir C3 ci-dessus).
- **Mode « ressources rares au début » (exploration)** : un mode (constante
  on/off) qui rend les ressources **rares/précieuses au départ** — peu de
  gisements près du spawn → le joueur doit **aller chercher plus loin** (où
  les nappes/patchs sont plus denses/nombreux), façon vanilla oil à explorer.
  Concerne patchs items, patchs fluides et lacs. Attention solvabilité : le
  bootstrap reste jouable (assez de ressources de départ), la rareté ne doit
  pas bloquer les premiers crafts — elle pousse à l'exploration, pas à
  l'impasse.
- **Randomisation de la chaleur comme l'électricité** : appliquer la même
  logique que `resolve_electricity` (shuffle/test/réparation par patch forcé)
  à la chaleur (heat). S'assurer qu'un réseau de chaleur est toujours
  accessible et jouable sur chaque seed, avec un fabricateur de chaleur
  garanti dans l'arbre de récursion.
- **Tags de déblocage de l'arbre tech / sciences par bâtiment** : introduire
  des tags (comme ceux existants du lab et autres bâtiments fixes) qui
  conditionnent le déblocage de l'arbre technologique et des science packs
  en fonction du déblocage réel des bâtiments. Exemple : un science pack ne
  devient disponible que si le bâtiment capable de le fabriquer a été
  débloqué dans l'arbre de récursion. Cela verrouille/déverrouille des
  branches entières de tech selon les bâtiments obtenus, renforçant le
  côté « arbre de progression aléatoire ».
- **Extraction au starter trop riche — déblocage PROGRESSIF des extracteurs**
  **(constat en jeu, à développer)** : dès le spawn, le joueur accède à la fois
  à `burner-mining-drill` ET `electric-mining-drill`, plus pumpjack et
  offshore-pump : trop de bâtiments d'extraction d'un coup, la progression se
  « voit » en une seule tech. Désiré : débloquer l'extraction **au fur et à
  mesure** :
  - un seul extracteur (le plus primitif) au starter ; les foreuses plus
    évoluées se débloquent PAR la récursion, jamais en vrac au départ ;
  - la **« permission de miner »** façon vanilla : une ressource n'est minable
    que si son extracteur compatible est débloqué **et que la recherche
    nécessaire a été faite** (ex. l'uranium n'est pas minable sans recherche) ;
  - le déblocage d'un minerai peut être **conditionné à l'obtention d'un
    fluide/extracteur qui permet de le miner** (gating ressource→permission)
    — l'extraction devient une progression, pas un acquis du spawn.
  À connecter avec C1 (randomisation non-infinies) et la garantie « extracteur
  avant besoin » (§7) : la garantie suffit pour la solvabilité, il faut EN PLUS
  échelonner le starter pour ne pas tout donner d'emblée.

---

<finished>
Note : les anciennes annotations « Reponses : » ont été intégrées/remplacées par
l'état actuel (fait vs à développer) ci-dessus, pour éviter la confusion des
nomenclatures.
</finished>
