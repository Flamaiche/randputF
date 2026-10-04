# Idées et chantiers à développer (randputF)

> **Document de travail, non revu depuis son écriture.** Ses chemins,
> ses chiffres et le code qu'il cite peuvent avoir changé depuis. L'état
> courant est dans [`docs/`](../docs/) et
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
vérification déjà faite en local lors du bump 1.0.1.

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
HTTP, pas d'API de portail. Le `.exe` embarque exactement les mêmes assets que le wheel
(`--add-data "mod;mod"`, `"data;data"`, `"config;config"`) et se contente
d'appeler le générateur. Le produit est le mod en local, pas un téléchargement.

Voie retenue : **tkinter pour l'IG v1** (inclus dans Python, zéro dépendance),
**PyInstaller pour l'exe**. Le passage à l'IG suffit à ouvrir ce chantier ;
l'exe n'est pas un chantier séparé.

