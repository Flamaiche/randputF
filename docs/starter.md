# Démarrage et chaîne initiale

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 7. La phase de démarrage

Le randomizer détermine tout dès le spawn (l'électricité suivra sa propre
logique, §10) :

1. **Kit de départ randomisé** : le joueur ne commence pas forcément avec le
   même équipement. Son arme de départ est tirée au hasard, et **les munitions
   se calent sur l'arme** (`starter.ammo_count` exemplaires, défaut 50 —
   plafonnées au stack du munition, configurable §16) pour qu'il puisse
   effectivement l'utiliser. Le kit
   fournit aussi le fabricateur, l'extracteur URPLS de la seed et un
   combustible si besoin — à raison d'**UNE amorce par type d'extracteur**
   (une foreuse par type de sol ; et côté fluides : **une pumpjack** pour les
   patchs, **une pompe offshore** pour les lacs — §7.5, deux milieux
   distincts). Ce n'est PAS la dotation qui rend la suite faisable : c'est
   l'**unlock**.
   **Chaque ressource du run (patchs ou lacs, §7.5) a la recette de son
   extracteur débloquée « juste-au-besoin » (§C3)** : la tech gratuite
   `starter-extraction` ne garde que les extracteurs utiles dès le spawn (leur
   ressource est consommée par la chaîne initiale) ; un extracteur dont la
   ressource n'est servie qu'en profondeur part avec le **premier consommateur**
   (tech d'usage, au plus tard — jamais après) ; un extracteur jamais utilisé
   suit le balayage de contenu (§9.6), sur une tech payante tirée
   aléatoirement. Contrainte de fabrication : l'extracteur n'est jamais
   débloqué avant l'atelier qui le fabrique (U2). Quand on a besoin d'une
   ressource, son extracteur est donc déjà craftable : on en refabrique autant
   qu'il faut (le poisson se pêche dans les lacs, §7.5). L'amorce du kit ne
   fait que briser l'œuf/poule du premier exemplaire — même pour un extracteur
   différé, le kit fournit toujours son item.
2. **Techs gratuites du starter** : les premières recettes (la chaîne
   initiale, §8) sont débloquées par les techs du starter
   (`randputf-starter-*`), **gratuites** — coût nul, auto-complétées au
   runtime (free_researches). Elles se craftent avec **tout le pool du début**,
   ressources au sol ET ressources non-infinies (bois/pierre/poisson).
3. **Techs de prologue** (`randputf-prologue-*`) : juste après ces techs
   gratuites, les recettes **propres** des produits dont le bootstrap
   consommait des ressources non-infinies (§9.5) sont regroupées en techs de
   prologue de **≤ 5 unlocks chacune** (plafond §13, jamais une tech géante —
   une seule suffit s'il y a peu de recettes, aucune tech si aucune recette).
   Ce ne sont pas des
   free_researches : chaque prologue se débloque par **hand-craft** d'un item
   du bootstrap (§9.3) — façon vanilla (automation/logistics) : le joueur
   fabrique l'item déclencheur à la main et la tech s'active aussitôt. Le
   joueur sort vite de la dépendance au bois/pierre/poisson et débloque
   simultanément l'entrée en science avec
   le lab du starter.
4. **Site de crash randomisé** : les conteneurs `crash-site-*` du crash
   vanilla (munitions, plaques…) sont **vidés puis remplis aléatoirement**
   : chaque slot reçoit `n` copies d'un matériau aléatoire du pool de loot
   (`wreck.loot`, §16), avec `n ∈ {0, 1, 2, 3}` tiré selon une loi pondérée
   **strictement décroissante** (0 le plus fréquent → slot vide, 3 le plus
   rare) : `seed.wreck.counts = [c0, c1, c2, c3]` calculés par la formule
   générique `c3 = t`, `c2 = t + a`, `c1 = 100 − 5t − 2a`, `c0 = c1 + b`
   (exiger `6t + 3a < 100` et `b ≥ 1`), garantissant la somme des valeurs
   `0·c0 + 1·c1 + 2·c2 + 3·c3 = 100`. Défauts `(t,a,b) = (15, 1, 1)` →
   P(0) ≈ 30,8 % : le crash est riche (un vaisseau à 5 slots ≈ 6 matériaux en
   moyenne) et **un conteneur n'est jamais entièrement vide** (force-fill au
   runtime si le tirage a tout mis à 0). Chaque conteneur n'est traité qu'une
   fois (loot préservé aux rechargements), le tirage est déterministe par seed
   (générateur indépendant `game.create_random_generator`). Le pool de loot se
   limite
   aux **ressources non-infinies** (bois, pierre, poisson) : ce sont les
   seules qu'on ne peut pas miner/automatiser, et on évite tout item crafté
   (plaques, fours…) dont la recette n'est pas garantie débloquée par
   l'arbre randomisé.
5. **Lacs de fluide** : 3e type de **raw ressource**, après les items et les
    fluides pumpjack (§6). Le mod **supprime toute l'eau vanilla de la carte**
    (océans, shallow…) puis ne génère QUE les lacs tirés par la seed
    (`seed.map.lakes = [{resource, richness}]`) : chaque lac est une tuile
    `randputf-lac-<fluid>` (copie de la tuile eau, **recolorée**) portant
    `fluid = <fluide tiré>` — une **pompe offshore vanilla** posée dessus
    débite ce fluide, **infini** comme l'eau. Richesse = taille du lac (volume
     illimité). **Contraste patchs/lacs (§7)** : un *patch* fluide est une
     **entité** resource `basic-fluid` posée sur la terre → il se mine avec la
     **pumpjack** (électrique, §10) ; un *lac* est une **tuile** → il se pompe
     avec la **pompe offshore** (énergie void, sans électricité). Les deux
     extracteurs ont leur recette au starter et un amorce au kit quand les deux
     milieux sont présents. Comptage `count ∈ [min, max]` (défaut 1, zéro possible via
     config) : un fluide non tiré n'a **aucun lac** (= indispo à l'extraction
     par lac), et si aucun lac n'est tiré la carte est sans eau. Placement
     **CREUSÉ au runtime** (`control.lua`, `on_chunk_generated`) : le scatter
     `resource-autoplace` a été abandonné car ses nappes de départ se
     chevauchaient près du spawn et un seul liquide (le dernier, d'ordre le
     plus élevé) dominait et éclipsait les autres (vérifié headless :
     heavy-oil 1154 tuiles vs water 150 vs steam 108, à richesse quasi égale).
     Chaque fluide tiré reçoit donc **une nappe discrète de rayon `LAKE_RADIUS`
     (6 tuiles)**, à une position **distincte sur un anneau de rayon
     `LAKE_RING_RADIUS` (26 tuiles) autour du spawn** (angles équirépartis) :
     aucune superposition → tous les liquides sont visibles et pompables, et la
     surface totale est faible (π·6² ≈ 113 tuiles par lac, au lieu de >1000).
     Le mapgen ne pose **aucune** tuile de lac (voir neutralisation ci-dessous).
    **Neutralisation de l'eau vanilla** : forcer `autoplace.probability_expression = 0`
    sur les prototypes de tuiles d'eau ne suffit pas — le mapgen conserve des
    tuiles (mesuré : ~3 000 water/deepwater résiduelles sur la carte). La
    neutralisation réelle passe par l'override du mapgen de planète :
    `map_gen_settings.property_expression_names["tile:<eau>:probability"] =
    "<expression négative>"` (noise-expression `randputf-no-water`), appliqué
    à chaque tuile `water_tile_type_names` sur nauvis — résultat mesuré :
    **0 tuile d'eau vanilla**, les seules nappes étant les lacs tirés.
    **Couleur du lac** : chaque nappe utilise une palette **pastel** dérivée
    de la `base_color` du fluide — luminosité garantie ≥ 0.55, saturation
    ≥ 0.25, plafond 0.92 — visible au sol (`variants[].tint` + `effect_color`)
    ET sur la carte (`map_color`). Les patches ressources utilisent des couleurs
    vives (composantes 30..130/255) ; les lacs en pastel se distinguent
    naturellement sans les écraser. Fluides sans chromatisme : teinte de secours
    distincte par fluide (table `lake_fallback_hue` : crude-oil → brun huile
    orangé, steam → bleu clair, hydrogen → cyan…).
    **Bordures : tous les lacs sont bordés** : chaque lac reçoit une **berge**
    dessinée par les tuiles de TERRE voisines. Le data-stage
    (`data-updates.lua`) ajoute le nom de chaque tuile-lac
    (`randputf-lac-<fluid>`) aux `transitions[].to_tiles` de toutes les tuiles
    de terre qui ciblent déjà l'eau vanilla (les 7 noms de
    `water_tile_type_names`, pas seulement `water` — couverture complète des
    biomes). La **berge dépend du biome environnant** : autour du spawn c'est
    sable/herbe (grass/sand), donc des berges douces ; ailleurs, selon le
    biome où le lac tombe, la transition varie. Transitions patchées triées au
    data-stage pour un résultat 100 % déterministe.
    **Déclenché au runtime** (`control.lua`, `fill_lake`) : le remplacement de
    la tuile-fantôme par la tuile-lac colorée se fait avec
    `set_tiles(..., correct_tiles = true)` — le moteur recalcule alors les
    bords autour des tuiles modifiées (même mécanisme que le landfill), ce qui
    fait apparaître la berge autour du lac rempli. La marque des lacs bordés
    est portée par une table Lua locale (`lake_borders`), jamais par une clé de
    prototype.
    **Coupe nette** : seul le fantôme (blanc, avant remplissage) « coupe » sans
    bord — il n'est volontairement pas ciblé par les transitions et est
    remplacé dès la génération du chunk ; les lacs finis sont toujours bordés.

    **Les lacs ne peuvent pas couvrir le spawn / le site de crash** : chaque
    nappe est posée sur l'anneau de rayon `LAKE_RING_RADIUS` (26 tuiles) autour
    du spawn, hors du site de crash (centré sur 0,0) et de la zone de départ,
    tout en restant **accessible à pied dès le départ**. Générateur à part :
    `lakes.py` échantillonne **sans remise** — au plus **un lac par fluide**
    (le mod déduplique aussi par sécurité).
    **Purge runtime des cartes legacy** (`control.lua`) : les cartes créées
    avant le fix embarquent `property_expression_names` vide et conservent les
    tuiles d'eau vanilla du mapgen. Au premier chargement, `purge_chunk_water`
    remplace ces tuiles (`water`, `deepwater`, `water-shallow`, `water-green`,
    `deepwater-green`, `water-mud`, `water-wube`) par la tuile de terre
    dominante du chunk — balayage en carré croissant depuis le spawn, 32
    chunks/tick, curseur persisté dans `storage` (reprise après rechargement).
    Les lacs tirés par la seed sont préservés. Mesuré sur `testtest1`
    (139 546 tuiles) : purge complète en ~1 000 ticks sans impact perceptible
    sur l'UPS. La pompe côtière affiche nativement le fluide de sa tuile source
    (2.0, `tile.fluid`) : aucun tooltip custom nécessaire.
6. **Landfill garanti dès le prologue si lacs** : un lac est un **mur**
   infranchissable tant que le joueur ne peut pas le franchir. Quand la seed
   tire **au moins un lac**, la chaîne du starter appelle `ensure_obtainable`
   sur le `landfill` dès le bootstrap (recette `randputf-landfill` unlockée
   par `starter-transformation`, craftée avec le pool de début, §8/§13) : le
   joueur peut toujours franchir/combler l'eau de la carte dès le départ.
   Sans lac, inutile d'imposer le landfill — sa recette tombe alors au hasard
   dans le balayage de couverture (§9.6).

## 8. La chaîne initiale (starter)

Une fois les types de ressources brutes posés, le randomizer construit la
première boucle de production :

1. **Extraction** : un ou plusieurs bâtiments extracteurs sont choisis en
   fonction des ressources immédiatement à collecter — le milieu de chaque
   patch désigne la famille d'extracteurs possibles : foreuses pour le sol, et
   côté fluides le **support physique** de la ressource : un **patch** est une
   entité `basic-fluid` → **pumpjack** (électrique) ; un **lac** est une tuile →
   **pompe offshore** (énergie void).
2. **Transformation** : un bâtiment de fabrication est choisi pour créer ou
   transformer une ressource en une autre. Tout peut y passer : selon ses
   directives, il acceptera items, fluides ou les deux. Un assembleur tier 1
   refusera une recette fluide là où un assembleur tier 2 l'acceptera.
3. **Transport** : en fonction des besoins de ces quelques ressources de
   début, le joueur se voit débloquer tapis et tuyaux — randomisés, car il en
   existe plusieurs tiers — ainsi que les périphériques associés : splitters,
   tunnels/undergrounds côté tapis, équivalents côté tuyaux.
4. **Logistique** : des bras robotisés sont ajoutés — avec probabilité
   `starter.inserter_chance` (défaut 0.5, défini dans
   `config/defaults.yaml` §16).

**Contrainte anti-cycle fondamentale** : si un bâtiment de cette phase exige
une entrée supplémentaire (le cas d'école : une perceuse électrique qui boit
un fluide dès le début), alors :

1. ce fluide doit pouvoir être obtenu ;
2. les tuyaux qui le transportent peuvent être fabriqués **à partir de ce
   fluide**, ou **d'une autre ressource** ;
3. mais **jamais à partir de la ressource qui en a besoin** — l'entrée
   auxiliaire provient toujours d'une branche déjà valide, indépendante du
   bâtiment qu'elle alimente.

**Extracteurs items-only** : la recette qui fabrique un extracteur (perceuse,
pumpjack, pompe offshore) n'utilise **jamais de fluide comme ingrédient** —
surtout pas celui qu'il sert justement à extraire. Dès le starter, ces
bâtiments se craftent uniquement avec des items, ce qui rend leur déblocage
possible avant même qu'aucune ressource au sol (et en particulier aucun
fluide) ne soit atteignable.

**Bootstrap non-infinies, puis relais** : au tout début, le joueur possède
*toutes* les ressources, y compris les non automatisables (arbres, rochers,
poissons). Ces dernières servent de matière première d'appoint du démarrage —
leur présence garantit un début de run qui marche, même pour les seeds sans
aucun patch item. Mais elles ne sont **pas tenables à long terme** : tout
produit dont la recette générée en consomme obtient une **recette relais**
(§9.5), débloquée dans les 3 premières techs.

**Le lab est une brique du starter — type « recherche »** : tout bâtiment
consommant des science packs (`lab_inputs`) est classé dans un type fonctionnel
dédié, `recherche` (§5.1), et non parmi les transformateurs : ce n'est pas un
atelier de craft, il n'a rien à faire dans le pool des recettes artisanales
(anti-cycle §8). Sans lab, la partie se fige dès les premières techs gratuites
consommées : le starter garantit donc par construction qu'un bâtiment de
recherche tombe dans la **2e recherche gratuite** (starter-transformation),
avec une recette craftée avec le pool de début.

**Un seul combustible — toutes catégories** : le mod redéfinit au data-stage la
catégorie de combustible de **chaque brûleur** pour qu'elle accepte *toutes* les
catégories du jeu (charbon, bois, combustible solide **et** cellules d'uranium,
etc.) — `mod/data-updates.lua`. La seed n'a donc **pas** à filtrer par
catégorie : le kit de départ glisse simplement le combustible à la plus grande
`fuel_value` du pool obtenu, et il est toujours utilisable quel que soit le
brûleur du kit (perceuse, chaudière, four, réacteur…). Sans ce patch, un kit
pouvait tirer une cellule d'uranium (catégorie « nuclear ») dans un
`burner-mining-drill` n'acceptant que « chemical » : inutilisable.
