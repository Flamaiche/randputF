# Les ressources au sol

## 6. Les ressources au sol

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

Au spawn, la carte est entièrement redéfinie :

- le nombre de patchs est aléatoire, de **3 à 8** ;
- chaque patch reçoit un type tiré au hasard parmi **tous** les candidats : un item du pool « beltable » ou un fluide du pool « pipable » ;
- le tirage est **sans remise** : chaque ressource apparaît au plus une fois sur la carte (jamais deux patchs de petroleum-gas, par exemple) ;
- **aucune contrainte d'homogénéité** : les patchs peuvent être uniquement des fluides, uniquement des items, ou un mélange aléatoire des deux ;
- la richesse des patchs est également variable ;
- **Patchs d'items et de fluides** : tous posés au sol par le mod **au runtime** (voir §6.5), le mapgen n'en dessine aucun. Pour chaque patch, la seed fournit un **centre** (proche du spawn), un **rayon de dispersion** et un **nombre de blocs ou puits adapté**. Les **fluides** conservent quelques puits éparpillés (`wells_per_patch`, par défaut `3..8` ; un pumpjack se connecte sur n'importe quelle tuile). Les **items** forment des **champs organiques façon vanilla** : un **disque bruité** où chaque tuile est posée selon un **hash déterministe par tuile**. Ce disque comporte un cœur presque plein (`~1 %` de trous, fraction `NOISE_CORE` du rayon), un anneau externe dilué et un contour ondulé. La taille correspond à une vraie veine (`item_patch_radius`, par défaut `9..17`, soit environ **168 à 630** tuiles posées), dense comme un gisement vanilla de fer ou de cuivre.
  Le mod **pose chaque bloc ou puits au runtime** sous forme d'entité `randputf-minerai-<item>` (minée par une foreuse) ou `randputf-oil-<fluide>` (pompée par un pumpjack), dispersée aléatoirement autour du centre, sans alignement. La **richesse d'un fluide** équivaut au rendement par puits. La **richesse d'un item** correspond à la richesse totale du champ répartie **par tuile** (`richness / count`), simulant un gisement vanilla qui s'épuise par morceaux ;
- les ressources **non automatisables** (arbres, poissons, etc.) sont **exclues** des ressources brutes et ne forment jamais de patch. Elles restent **récoltables à la main dès le départ** (pool environnemental de base) et utilisables comme ingrédients, de manière **pondérée** :
  - Quantités limitées et demandes réduites.
  - Sélection **rare** (poids faible) si un item de production existe (patch d'item ou item déjà fabriqué). Elles apparaissent surtout dans les **premiers crafts** ;
  - Sélection **prioritaire** uniquement si la seed ne contient **aucun** patch d'item. Elles servent alors de matière première de démarrage, notamment pour **fabriquer les extracteurs** (la fabrication du pumpjack et de la foreuse se débloque avant toute ressource au sol).
- les items « briques garanties » ne sont **jamais** des patchs : lab (§8), les 3 ingrédients de la fusée et le rocket-silo (§14). Ce sont des recettes générées et débloquées par une technologie précise. Si un tel item apparaissait au sol, la recette garantie n'existerait pas, brisant l'invariant de fin de partie.
- les **science packs** ne sont **jamais** des patchs (§13) : leur économie repose sur la fabrication (chaque pack se fabrique, sans extraction du sol). Un pack au sol briserait la structure de coût des technologies : le premier pack, fourni au démarrage, n'aurait pas de recette, et les technologies récursives n'auraient aucun coût initial.

Conséquence structurelle : aucune plaque de fer, de cuivre, de charbon ni de gisement de pétrole classique n'est garantie au sol. Le joueur découvre à chaque partie la composition de son monde.

### 6.5 Pose explicite des gisements (runtime)

Tous les patchs — **item ET fluide** — s'affranchissent du `resource-autoplace` vanilla (qui alignait les gisements) : le mod les **pose au runtime**.

Pour chaque patch, la seed contient :
- `center {x,y}` — le **centre du gisement**, déterministe : le premier est posé à environ `25` tuiles du spawn (disponible dès le début), puis chaque gisement environ `24` tuiles plus loin, à des **angles éparpillés** (jamais alignés, pour casser l'aspect « rangée » du vanilla). Ce **cluster serré au spawn** regroupe les `3..8` gisements dans un rayon accessible à pied très tôt (environ `25..193` tuiles dans le pire des cas à 8 patchs, et environ `25..145` pour les `3..8` usuels) ;
- `count` — le **nombre de blocs ou puits**, adapté au type de patch : **fluides** = puits éparpillés (configuration `wells_per_patch`, par défaut `[3, 8]`) ; **items** = nombre **réel de tuiles** posées par l'algorithme de forme du champ (dérivé via `item_field_tiles`, par défaut ~65.5..70.5 % de l'aire du disque), évitant l'approximation `ceil(π·r²)` qui surestimait le champ et diluait la richesse par tuile ;
- `cluster_radius` — le **rayon de dispersion** autour du centre : large pour les puits de fluides (par défaut `9..16`), taille de gisement « type vanilla » pour les items (par défaut `9..17`, soit environ `168` à `630` tuiles posées pour une aire théorique de disque de `254..908`) ;
- `well_seed` — la **graine locale** pour dériver chaque position de bloc ou puits.

Au runtime (`on_chunk_generated`), quand un chunk contenant le gisement est généré, chaque bloc ou puits est posé en entité-ressource `randputf-minerai-<item>` ou `randputf-oil-<fluide>` par `surface.create_entity`, avec sa **richesse appliquée via `entity.amount`**.

La position de chaque bloc ou puits est calculée de façon **reproductible et indépendante de l'ordre de génération des chunks** : un hash déterministe par tuile (combinant `well_seed` et les coordonnées relatives au centre, miroir exact entre `tool/generator/map_patches.py` et `mod/control.lua`) garantit que l'ordre de génération des chunks n'a aucune influence. Les puits de **fluides** restent éparpillés à l'extérieur du centre (fraction `0.25..1` ; un pumpjack se branche sur n'importe quelle tuile). Les **items** forment un **disque bruité façon vanilla** : un **cœur presque plein** (fraction `NOISE_CORE` du rayon, avec environ `1` % de trous car une vraie veine n'a pas de grands vides internes), un **anneau externe dilué** en densité décroissante vers le bord, et une **ondulation du contour** (`NOISE_WOBBLE`) qui casse l'aspect de cercle parfait. Un bloc ou puits qui tomberait sur un lac ou un obstacle est ignoré, les autres sont posés. Pour un **item**, la richesse de la seed correspond au **total du champ** : chaque tuile reçoit `richness / count` (où `count` est le nombre réel de tuiles posées, ce qui évite toute surestimation de l'aire théorique). Un **fluide** conserve un **rendement par puits** (la valeur `richness` s'applique intégralement à chaque puits).

#### Randomisation non-finie (A1)

Optionnel (section `nonfinite:` de la configuration, `enabled: false` par défaut — chantier A1) : par gisement et via un flux RNG dédié (`randputF:nonfinite:`), la richesse totale est multipliée par un facteur aléatoire `richness_factor` (par défaut `0.4..2.5`) et le rayon par `radius_factor` (par défaut `0.6..1.8`). Pour un **item**, `count` est systématiquement réévalué via `item_field_tiles(radius, well_seed)` : le champ posé reste exactement le disque bruité déterministe, seul le ratio `richness/count` par tuile varie. L'identité (type et ressource) n'est jamais modifiée (définie au §6).

Dans `data-updates`, ces entités ont un `autoplace` avec `base_density = 0` : le mapgen ne les instancie jamais (le moteur exigeant un `autoplace` pour chaque ressource, même avec une génération nulle). Seule la logique au runtime gère leur apparition.

#### Identité des fluides : la température n'existe pas

Un fluide est défini uniquement par son **identité de ressource pipable** — « tout ce qui peut circuler dans un tuyau ». Deux fluides portant le même nom mais à des températures différentes constituent **le même fluide** : pour randputF, la température n'est pas une dimension et n'existe pas en tant que critère de distinction.

Cette règle neutralise les cas ambigus du jeu (chaudière, réacteur nucléaire, échangeurs de chaleur) : ces bâtiments **effectuent une action** (chauffer, transférer de la chaleur) mais la température n'est pas considérée comme une transformation du fluide. Un fluide chauffé ou refroidi reste le même fluide. Seul un changement de nom (eau → vapeur) définit une autre ressource, qui passe alors par une recette classique et jamais par un simple écart de température.
