# Idées et chantiers non livrés (randputF)

> **Cadrage : tout ce qui suit est une idée non livrée.** Aucun élément de ce
> dossier n'est intégré au produit ni promis pour une version. L'état courant
> est dans [`docs/README.md`](../docs/README.md) ; le contrôle des idées par le
> testeur de dump est décrit dans [`docs/testeur.md`](../docs/testeur.md).
> `atelier/` contient des plans et des idées, `notes/` contient les notes de
> release publiées.

## Exécutable Windows pour les joueurs (avec l'interface graphique)

**Pourquoi.** Toute seed autre que celle obtenue par défaut impose l'outil
Python (`pip install .`). Un joueur Windows sans Python ne peut pas générer sa
propre seed : cette barrière reste à lever pour un parcours joueur complet.

**Dépend de l'interface graphique.** L'exécutable n'est pas un but en soi, il
est le véhicule de l'IG. Le produire avant l'IG donnerait un double-clic sans
écran — donc à traiter dans le même chantier que l'IG, pas avant.

**Livrable attendu.** Un `.exe` qui embarque `mod/`, `data/` et `config/`,
c'est-à-dire exactement les dossiers que le wheel embarque déjà (liste de
paquets explicite dans `pyproject.toml`). Le point de départ est donc le paquet
installé, pas le checkout.

**Invariant à protéger — point non négociable.** Le témoin de déterminisme ne
vaut que si le mod produit par l'exécutable est identique à celui produit par la
CLI. L'exécutable figé est un environnement d'exécution différent : pas de
checkout, ressources embarquées, pas de `pip install .`. Sans test, il peut
diverger de la CLI sans que rien ne le voie — et le témoin ne garantirait plus
rien pour le joueur qui l'utilise. Un test doit donc générer une seed via
l'exécutable et comparer le md5 à celui de la CLI, comme la vérification déjà
faite en local lors du passage à la 0.0.1.

### Ce que fait le projet de référence

`vaibhavvikas/factorio-mod-downloader` (le plus cité pour les outils mod
Factorio) n'est plus en Python : sa v0.4.0 est en Rust + Tauri v2, avec des
binaires natifs pour plusieurs systèmes. L'argument de vente de la
réécriture est explicite dans sa note de version : « no browser drivers, no
python scripts ».

Ses versions Python antérieures sont conservées dans des forks
(`Sebastianpolska/factorio-mod-downloader_fork`) et montrent le cahier des
charges d'origine : `customtkinter` + `pillow` + `requests` + `selenium` +
`chromedriver-autoinstaller`, distribuées en `.exe` PyInstaller `--onedir
--windowed`. Le README expliquait qu'au premier lancement l'application
téléchargeait 30 à 35 Mo de pilotes de navigateur.

**Ce qu'il faut en retenir : le poids ne venait pas de Python.** Il venait de
`selenium` — le projet scrapait le portail de mods avec un navigateur
automatisé. Passer à Rust a supprimé le navigateur, pas le langage. Un autre
gestionnaire de mods, `Musyoka2020-eng/FactorioManager`, est en Python + tkinter
+ PyInstaller (fichier `.spec`) et fonctionne ; il se limite au Windows pour le
`.exe`.

### Pourquoi randputF est un cas plus favorable

Le problème résolu par ces projets est le réseau : portail de mods à interroger,
jeton d'authentification, téléchargement HTTP. randputF n'a aucune dépendance
réseau — `tool/` ne fait aucun appel HTTP, et les prototypes vanilla viennent
d'un dump JSON embarqué (`data/vanilla_dump.json`). Il n'y a ni portail à
scraper, ni pilote à télécharger, ni jeton à gérer.

Générer un mod est plus simple que télécharger un mod : pas de client HTTP, pas
d'API de portail. Le `.exe` embarque exactement les mêmes dossiers que le wheel
(`--add-data "mod;mod"`, `"data;data"`, `"config;config"`) et se contente
d'appeler le générateur. Le produit est le mod en local, pas un téléchargement.

Voie envisagée : **tkinter pour l'IG v1** (inclus dans Python, zéro dépendance),
**PyInstaller pour l'exécutable**. L'interface graphique suffit à ouvrir ce
chantier ; l'exécutable n'est pas un chantier séparé.

## Câbler le rejoueur dans `generate` (garde de sortie)

**Pourquoi.** Le rejoueur prouve la solvabilité par simulation mais n'est
branché nulle part dans la génération : `generate_with_retry`
(`tool/service.py`) s'arrête au validateur statique
(`validate_seed`/`validate_pipeline`). La preuve vit seulement dans les balayages
et la suite de tests (1501/1501 victoires mesurées).

**Recommandation (non approuvée).** Dernier garde après la validation
statique : `FakePlayer(db, seed).play()` sur la seed retenue ; une défaite
déclenche un essai suivant, comme les autres rejets. Coût : une rejouée par seed
acceptée (~1 s mesuré). Bénéfice : aucune graine injouable ne peut être générée, même si
un invariant statique manque une dérive. À décider : le budget maximal d'essais
(aujourd'hui 10) reste-t-il suffisant si le rejoueur ajoute des rejets ?

**État.** Refusé implicitement jusqu'ici (le rejoueur est un audit externe,
volontairement hors du chemin de génération). À rouvrir le jour où l'interface
graphique expose `generate` directement.

## Noms vanilla en dur côté outil — état du chantier

Principe : l'outil ne doit porter aucun nom d'item vanilla ; tout se dérive des
faits du dump. Avancement (2026-11-17) :

- **Nettoyé** — `tool/replay/player.py` : `VICTORY_ITEMS`, `"satellite"` et le
  fallback de packs par suffixe supprimés (victoire =
  `db.rocket_chain` dérivée : `rocket_parts_required` → recettes de fusée →
  ingrédients, produits de lancement par `rocket_launch_products`) ; garde-fou
  lab par tag `is_research` ; fallbacks `"offshore-pump"`/`"pumpjack"` de
  `_infer_extractors` retirés. Les armes montées viennent de `entity.guns` du
  dump (`VanillaDB.vehicle_guns`).
- **Nettoyé** — audits et exports : `tool/audit/difficulty.py` lit toute la
  chaîne de lancement depuis `meta.rocket` ; `tool/exporters/seed_graph.py`
  prend les packs et leur ordre dans `meta.science_packs`, sans suffixe ni
  sentinelle d'icône ; `tool/generator/late_raws.py` et
  `tools/classify_late_raws.py` n'acceptent un pack que s'il est déclaré par le
  dump ; `tool/__main__.py` affiche les produits de lancement dérivés du dump ;
  `tool/exporters/complexity_graph.py` reconnaît le bâtiment de lancement par
  `rocket_parts_required` (plus par `type == "rocket-silo"`) ;
  `tool/common/db.py` reconnaît les barils par le sous-groupe `barrel`.
- **Restants, par design** — `tool/common/tagsets.py` (`ROCKET_CHAIN`,
  `ENVIRONMENTAL_ITEMS`, `VEHICLE_GUNS` : choix de conception consignés dans
  [`docs/tags.md`](../docs/tags.md)) ; `tool/common/demo.py` (base synthétique
  de test) ; `build_vanilla_seed` (rapport baseline vanilla uniquement, jamais
  utilisée pour générer une seed) garde ses exclusions historiques `barrel`,
  `kovarex` et le retraitement du combustible ; `tool/prototypes/usage.py` lit
  `usage.terminal_buildings` depuis la configuration (`lab`, `rocket-silo` par
  défaut, surchargeable).

## Mode « tout atteindre / tout crafter 10 » et règles dynamiques

> **Idée du 2026-11-19.** Une fois qu'une partie du modpack peut être terminée
> correctement, ajouter un **second mode** : atteindre et fabriquer chaque objet
> au moins 10 fois en fin de partie. Le mode actuel ne cherche que la fin du
> jeu ; le second servira de base pour mesurer les limites réelles du modpack.
>
> Objectif : déterminer tout ce que le modpack permet et ne permet pas. Le
> modpack est vaste, mais il contient aussi tout ce qu'une partie peut faire
> avec des cycles bien formés et des technologies recherchables beaucoup plus
> tard. Les chaînes doivent donc pouvoir être refaites autant que nécessaire.
>
> But : se rapprocher des règles à implémenter dans le modpack et, si la
> complexité l'impose, répartir ces règles en modules. Exemples : placer une
> boucle à un moment donné, déplacer une technologie plus tôt alors qu'elle ne
> sera utile que bien plus tard. Ces règles rendraient le modpack plus
> dynamique.
>
> Conséquence : le testeur doit produire des résultats et des sorties claires.
> Le diagnostic courant reste difficile ; un second mode avec un diagnostic
> explicite (cycle productif, starter manquant, atelier absent, technologie
> trop tardive…) est aussi important que le mode victoire.
