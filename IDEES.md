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

### C3. Déblocage progressif des extracteurs

Constat en jeu : dès le spawn, le joueur accède à la fois à `burner-mining-drill`
ET `electric-mining-drill`, plus pumpjack et offshore-pump : trop de bâtiments
d'extraction d'un coup, la progression se « voit » en une seule tech. Désiré :
débloquer l'extraction **au fur et à mesure** :

- un seul extracteur (le plus primitif) au starter ; les foreuses plus
  évoluées se débloquent PAR la récursion, jamais en vrac au départ ;
- la **« permission de miner »** façon vanilla : une ressource n'est minable que
  si son extracteur compatible est débloqué **et que la recherche nécessaire a
  été faite** (ex. l'uranium n'est pas minable sans recherche) ;
- le déblocage d'un minerai peut être **conditionné à l'obtention d'un
  fluide/extracteur qui permet de le miner** (gating ressource→permission) —
  l'extraction devient une progression, pas un acquis du spawn.

*Prototype : `tool/prototypes/progressive_extractors.py` (palier starter
`starter_max_extractors`, `research_map`, constante `enabled`) — non branché au
pipeline. À connecter avec A1 (randomisation non-infinies) et la garantie
« extracteur avant besoin » (§7) : la garantie suffit pour la solvabilité, il
faut EN PLUS échelonner le starter pour ne pas tout donner d'emblée.*

---

## D. Écosystème & garanties

### D1. Support pairing générique

Les « paires utiles » ne sont garanties que pour les armes et les véhicules
(§12.1). Étendre le pairing au-delà (bâtiment de production → recette associée,
consommable → arme, etc.) : à préciser une fois les chantiers A/B/C avancés,
c'est un renfort de cohérence, pas une brique de contenu.