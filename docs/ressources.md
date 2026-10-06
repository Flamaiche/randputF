# Les ressources au sol

## 6. Les ressources au sol

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Au spawn, la carte est entièrement re-décidée :

- le nombre de patchs est aléatoire, dans une **fourchette de 3 à 8** ;
- chaque patch reçoit un type tiré au hasard parmi **tous** les candidats :
  - un item quelconque du pool « beltable », ou
  - un fluide quelconque du pool « pipable » ;
- le tirage est **sans remise** : une ressource apparaît au plus une fois sur
  la carte (jamais deux patchs de petroleum-gas, par exemple) ;
- il n'y a **aucune contrainte d'homogénéité** : certains patchs peuvent
  n'être que des fluides, d'autres que des items, ou un mélange des deux ;
  c'est totalement aléatoire ;
- l'abondance (richesse) des patchs est également variable ;
- **Patchs item et fluides** : tous posés au sol par le mod **au runtime**
  (pose explicite des gisements, §6.5), le mapgen n'en dessine plus aucun.
  La seed fournit pour chaque patch un **centre** (serré au spawn), un **rayon
  de dispersion** et un **nombre de blocs/puits adapté au kind** : les **fluides**
  gardent quelques puits éparpillés (`wells_per_patch`, défaut 3..8 - un
  pumpjack se branche sur n'importe quelle tuile du champ), les **items**
  forment des **champs ORGANIQUES façon vanilla** : un **disque bruité** où
  chaque tuile est posée selon un **hash déterministe par tuile** — cœur quasi
  plein (`~1 %` de trous, fraction `NOISE_CORE` du rayon), anneau externe
  dilué, contour ondule — l'équivalent visuel d'une vraie couche d'ore. La
  taille est celle d'une vraie veine (`item_patch_radius`, défaut `9..17`,
  soit des champs d'environ **170 à 615 tuiles posées**), dense comme une couche
  de fer/cuivre de Factorio.
  Le mod **pose chaque bloc/puits au runtime** — entité-resource
  `randputf-minerai-<item>` (minée par une foreuse) ou `randputf-oil-<fluide>`
  (pompée par un pumpjack) — dispersé aléatoirement autour du centre, jamais
  alignés. **Richesse fluide** = rendement par puits (puits profonds) ;
  **richesse item** = part de richesse totale du champ répartie **par tuile**
  (`richness / count`), comme un minerai vanilla qui se tarit par morceaux ;
- les ressources **non automatisables** (arbres, poissons, etc.) sont
  **exclues** du calcul des ressources brutes : elles ne constituent jamais un
  patch. Elles demeurent **récoltables à la main dès le départ** (pool
  environnemental de base) et utilisables comme ingrédients, mais de manière
  **pondérée** :
  - quantité limitée et **petites** quantités demandées ;
  - **rarement** choisies (poids faible) tant qu'un item de production existe
    (patch item ou item déjà fabriqué) — elles apparaissent surtout dans les
    **tout premiers crafts** ;
  - en **priorité** uniquement quand la seed n'a **aucun** patch item : elles
    servent alors de matière première de démarrage, en particulier pour
    **fabriquer les extracteurs** (on débloque la fabrication du pumpjack / de
    la perceuse avant toute ressource au sol).
- les items « briques garanties » ne sont **jamais** des patchs : lab (§8),
  les 3 ingrédients de la fusée et le rocket-silo (§14). Ce sont des recettes
  générées et unlockées par une tech précise ; si un such item tombait au sol,
  la recette garantie n'existerait pas et l'invariant d'endgame serait cassé.
- les **science packs** ne sont **jamais** des patchs (§13) : leur économie
  repose sur le craft (chaque pack se fabrique, jamais extrait du sol). Posé
  au sol, un pack briserait la filière de coût des techs — le premier pack,
  seedé par le starter, n'aurait pas de recette et les techs récursives n'auraient
  aucun coût à payer au démarrage.

Conséquence structurelle : plus aucune plaque de fer/cuivre/charbon ni gisement
de pétrole classique n'est garantie au sol — le joueur découvre à chaque
partie de quoi son monde est fait.

### 6.5 Pose explicite des gisements (runtime)

Tous les patchs — **item ET fluide** — n'utilisent plus le
`resource-autoplace` vanilla (qui produisait des gisements réguliers/alignés) :
le mod les **pose au runtime**.

Pour chaque patch, la seed embarque :
- `center {x,y}` — le **centre du gisement**, déterministe : le premier est
  posé ~25 tuiles du spawn (une ressource disponible dès le début), puis chaque
  gisement ~24 tuiles plus loin, à des **angles éparpillés** (jamais alignés,
  pour casser l'aspect « rangée » du vanilla) — **cluster serré au spawn** :
  les 3..8 gisements restent tous dans un rayon accessible à pied très tôt
  (~25..193 tuiles au pire cas de 8 patchs, ~25..145 pour les 3..6 usuels) ;
- `count` — le **nombre de blocs/puits**, adapté au kind du patch :
  **fluides** = puits éparpillés (config `wells_per_patch`, défaut `[3, 8]`) ;
  **items** = nombre **RÉEL de tuiles** posées par l'algo de forme du champ
  (derivé, `item_field_tiles`, défaut ~55..75 % de l'aire du disque) — pas
  `ceil(π·r²)` qui sur-estimait le champ et diluait la richesse par tuile ;
- `cluster_radius` — le **rayon de dispersion** autour du centre : large pour
  les puits fluides (défaut `9..16`), taille de champ « type vanilla » pour les
  items (défaut `9..17`, ~170 à ~615 tuiles posées — l'aire théorique du
  disque 254..908), la taille d'une vraie veine) ;
- `well_seed` — la **graine locale** pour dériver chaque position de bloc/puits.

Au runtime (`on_chunk_generated`), quand un chunk contenant le gisement est
généré, chaque bloc/puits est posé en entité-resource
`randputf-minerai-<item>` / `randputf-oil-<fluide>` par `surface.create_entity`,
avec sa **richesse appliquée via `entity.amount`**.
La position de chaque bloc/puits est dérivée de façon **reproductible et
indépendante de l'ordre de génération des chunks** : un HASH DÉTERMINISTE par
tuile (`well_seed` + coordonnées relatives au centre, miroir exact entre
`tool/generator/map_patches.py` et `mod/control.lua`), donc l'ordre
chunk-par-chunk n'a aucune influence. Les puits **fluides** restent éparpillés à
l'extérieur du centre (fraction `0.25..1` — un pumpjack se branche sur
n'importe quelle tuile) ; les **items** forment un **disque bruité façon
vanilla** : un **cœur quasi plein** (fraction `NOISE_CORE` du rayon, ~1 % de
trous — une vraie veine n'a pas de grands trous internes), un **anneau externe
dilué** en densité décroissante jusqu'au bord, et une **ondulation du contour**
(`NOISE_WOBBLE`) qui casse l'aspect « cercle parfait ». Un bloc/puits qui
tomberait sur un lac ou un obstacle est simplement ignoré (position non
posable), les autres restent. Pour un **item**, la richesse de la seed est le
**total du champ** : chaque tuile reçoit `richness / count` (per-tile, où
`count` = nombre réel de tuiles posées — le total tombe pile, plus d'aire
théorique sur-estimée), un **fluide** garde un **rendement par puits**
(`richness` intégral à chaque puits).

#### Randomisation non-finie (A1)

Optionnel (section `nonfinite:` de la config, `enabled: false` par défaut —
chantier A1) : par gisement et avec un flux RNG dédié (`randputF:nonfinite:`),
la richesse totale est multipliée par un facteur aléatoire `richness_factor`
(défaut `0.4..2.5`) et le rayon par `radius_factor` (défaut `0.6..1.8`). Pour un
**ITEM**, `count` est systématiquement réévalué via
`item_field_tiles(radius, well_seed)` : le champ posé reste exactement le
disque bruité déterministe, seul le ratio `richness/count` par tuile varie.
L'identité (kind + ressource) n'est jamais touchée (tirée par §6).

En `data-updates`, ces entités ont `autoplace` avec `base_density = 0` : le
mapgen ne les instancie jamais (spécification requise — le moteur refuse un
resource sans autoplace — mais génération nulle) ; seule la logique runtime
les instancie.

#### Identité des fluides : la température n'existe pas

Un fluide est défini uniquement par son **identité de ressource pipable** —
« tout ce qui peut circuler dans un tuyau ». Deux fluides portant le même nom
mais à des températures différentes sont **le même fluide** : pour randputF,
la température n'est pas une dimension, elle n'existe pas en tant que critère
de distinction.

Cette règle neutralise les cas ambigus du jeu (chaudière, réacteur nucléaire,
échangeurs de chaleur) : ces bâtiments **font une action** (chauffer,
transférer de la chaleur) mais leur chaleur n'est pas considérée comme une
transformation du fluide. Un fluide chauffé ou refroidi reste ce fluide ; seul
un changement de nom (eau → vapeur) constitue une autre ressource, et il passe
alors par une recette classique, jamais par un simple écart de température.
