# Idées et chantiers non terminés (randputF)

> **Document de travail, revu le 2026-11-17.** Les chantiers terminés ont été
> retirés ; l'état courant est dans [`docs/`](../docs/) et
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
dérive des faits du dump. Avancement (2026-11-17) :

- **Nettoyé** — `tool/replay/player.py` : `VICTORY_ITEMS`, `"satellite"` et
  le fallback de packs par suffixe supprimés (victoire =
  `db.rocket_chain` dérivée : `rocket_parts_required` → recettes de fusée →
  ingrédients, produits de lancement par `rocket_launch_products`) ;
  garde-fou lab par tag `is_research` ; fallbacks
  `"offshore-pump"`/`"pumpjack"` de `_infer_extractors` retirés. Les armes
  montées viennent de `entity.guns` du dump (`VanillaDB.vehicle_guns`).
- **Nettoyé** — audits et exports : `tool/audit/difficulty.py` lit toute la
  chaîne de lancement depuis `meta.rocket` ; `tool/exporters/seed_graph.py`
  prend les packs et leur ordre dans `meta.science_packs`, sans suffixe ni
  sentinelle d'icône ; `tool/generator/late_raws.py` et `tools/classify_late_raws.py`
  n'acceptent plus un pack que s'il est déclaré par le dump ;
  `tool/__main__.py` affiche les produits de lancement dérivés du dump ;
  `tool/exporters/complexity_graph.py` reconnaît le bâtiment de lancement par
  `rocket_parts_required` (plus par `type == "rocket-silo"`) ;
  `tool/common/db.py` reconnaît les barils par le sous-groupe `barrel`.
- **Restants, par design** — `tool/common/tagsets.py` (`ROCKET_CHAIN`,
  `ENVIRONMENTAL_ITEMS`, `VEHICLE_GUNS` : choix de conception consignés
  docs/tags.md §14) ; `tool/common/demo.py` (base synthétique de test) ;
  `build_vanilla_seed` (rapport baseline vanilla uniquement, jamais utilisée
  pour générer une seed) garde ses exclusions historiques `barrel`,
  `kovarex` et retraitement du combustible ; `tool/prototypes/usage.py` lit
  `usage.terminal_buildings` depuis la config (`lab`, `rocket-silo` par
  défaut, surchargeable).
