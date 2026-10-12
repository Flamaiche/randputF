# L'amorçage du run

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

> **Cas partagé** entre [starter.md](starter.md) (la phase de départ),
> [recettes.md](recettes.md) (la génération), [energie.md](energie.md) (le premier
> générateur) et [tech.md](tech.md) (l'arbre). L'amorçage est la manière dont un run
> démarre **sans œuf/poule** : rien de ce dont le joueur a besoin ne doit exiger ce
> qu'il n'a pas encore. Les règles transverses sont rassemblées ici ; chaque phase y
> renvoie pour le détail.

## Les règles d'amorçage

### Bootstrap craftable à la main

Les premières recettes (la chaîne initiale, [starter.md](starter.md#la-chaîne-initiale-starter)) sont
**craftables à la main** : ingrédients solides, sans catégorie ni atelier, donc
disponibles avant toute électricité. Le **premier générateur électrique** et le
**pylône d'amorçage** suivent la même règle ([energie.md](energie.md#lélectricité)) : leurs
ingrédients **bannissent tout item** dont la fabrication passe par un atelier
électrique. Seuls restent ceux obtenus sans réseau : ressource brute (patch minerais),
kit, environnement, ou recette dans un atelier non-électrique ou à la main. Les recettes
bootstrap **doublent le coût de leurs ingrédients non infinis**
(bois/pierre/poisson), faisant de la sortie du bootstrap un objectif économique
([recettes.md](recettes.md#relais-des-ressources-non-infinies)).

### Déblocage « sur le tas »

Toutes les ressources étant déblocables, une recette peut introduire à tout moment le
besoin d'une ressource brute encore inconnue : le randomizer l'intègre **immédiatement**,
génère au besoin la méthode d'obtention (extraction, craft intermédiaire, combustible)
et le craft correspondant si le joueur ne le possède pas. Si une recette emploie une
ressource **non automatisable**, sa méthode d'obtention est débloquée **au même moment**,
et tout élément intermédiaire requis est produit « sur le tas » selon le type de
ressource. Il en résulte **l'absence d'impasse** conjuguée à l'imprévisibilité totale du
chemin.

### Recette orpheline et claim d'atelier

Lorsqu'un bâtiment de craft est débloqué « sur le tas » pendant la génération d'un
élément (via `_pick_building` → `_unlock_building`, typiquement un assembleur de tier
supérieur exigé par une recette récursive), il génère une recette `randputf-<bâtiment>`
qui doit impérativement être **claimée par la tech de l'élément en cours de génération**
— sinon elle devient **orpheline** (craftable mais jamais déblocable). `_generate_for_element`
compare `unlocked_buildings` avant/après l'élément puis ajoute tout nouveau bâtiment à
`step_buildings`/`unlocks_buildings` de la tech, avec déduplication et ordre conservé. Le
mécanisme couvre **l'ensemble** des déblocages d'ateliers sur le tas, quel que soit
l'élément (aucune recette orpheline mesurée sur 200 seeds). Le validateur signale tout
écart sans rejeter la seed ([tech.md](tech.md#larbre-technologique), item 6 de
[invariants.md](invariants.md#règles-de-solvabilité)).

### Techs gratuites et techs de prologue

Le starter débloque gratuitement les premières recettes (`randputf-starter-*`,
`free_researches` auto-complétées au runtime) : coût nul, craftables avec tout le pool du
début (ressources au sol ET non-infinies). Ensuite, les recettes **propres** des produits
dont le bootstrap consommait des ressources non-infinies sont regroupées en **techs de
prologue** (`randputf-prologue-*`, ≤ 5 unlocks chacune), positionnées juste après les
techs gratuites (une seule s'il y a peu de recettes, aucune sinon). Elles ne sont **pas**
gratuites : chacune se débloque par **hand-craft** d'un item du bootstrap, façon vanilla
(*automation*/*logistics*).

Les **déclencheurs hand-craft** suivent la règle « item disponible AVANT la tech ». Pour
éviter le bug classique consistant à tirer les candidats depuis une liste étendue après
coup (items tardifs comme le four électrique, le réacteur nucléaire ou le silo, qui
bloqueraient la tech **pour toujours**), les candidats viennent **exclusivement des
recettes des techs gratuites du starter** (accessibles au bootstrap) et chaque
déclencheur est vérifié **strictement en amont** de sa tech
(`test_craft_trigger_prologue_craftable_des_le_starter`). La quantité à hand-crafter n'est
jamais un singleton trivial : chaque prologue exige un **nombre d'items**
(`research_trigger` `craft-item`) égal à `count = round(2^(n + 1/4))` avec `n ~ randint(2, 6)`
(`relay_phase.py:185`), l'exposant calé sur la première science (`relay_phase.py:183`),
soit de 2^2.25 ≈ 5 à 2^6.25 ≈ 76 items. Le `craft_trigger_count` est propagé aux techs
(`tech_tree.py:311`) ; un tirage aléatoire ultérieur parmi des techs plus profondes
applique la même contrainte, avec un pool limité aux recettes déjà unlockées (hors
produits futurs).

### Garantie « besoin avant l'élément »

Le fil rouge de l'amorçage : **aucun élément ne doit être débloqué avant ses
prérequis**. C'est la même garantie que « extracteur avant besoin »
([ressources-brutes.md](ressources-brutes.md#les-formes-dune-ressource-brute)) et « source+transport chaleur avant
le sink » ([chaleur.md](chaleur.md#la-chaleur)). Elle est assurée à la création (oracle
early, [solvabilite.md](solvabilite.md#vérificateur-en-profondeur-bootstrap-sûr)), pas par une passe de rattrapage.

---

## Lectures associées

- **Parent** : [starter.md](starter.md) — la phase de démarrage.
- **Concepts liés** : [recettes.md](recettes.md) — la phase récursive ; [energie.md](energie.md) — électricité ; [tech.md](tech.md) — arbre technologique et fin de partie ; [invariants.md](invariants.md) — invariants de solvabilité.
