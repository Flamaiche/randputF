# Développement : roadmap et mise en route

Retour : [docs/README.md](README.md).

Cette page prépare un environnement de travail. Elle distingue les fonctions livrées, les chantiers en cours et les idées non retenues. Les idées non livrées restent dans `atelier/`.

## Ce que ça change pour l'utilisateur

- L'environnement Python minimal suffit pour générer ; `.[dev]` ajoute pytest.
- Un dump doit être régénéré quand la version de Factorio change.
- Les idées de l'`atelier/` ne se retrouvent dans aucun livrable.

## Mots à connaître

- [dump vanilla](glossaire.md) — photographie des prototypes extraite du jeu.
- [témoin](glossaire.md) — empreinte de reproductibilité.
- [rejeu](glossaire.md) — simulation de la progression sans interface.
- [artefact](glossaire.md) — fichier généré, jamais suivi dans git.

## Fonctionnement

### Mise en route

1. Créer un environnement virtuel Python avec `python3 -m venv .venv`.
2. Installer le paquet et ses outils de test avec `.venv/bin/pip install -e '.[dev]'`.
3. Vérifier l'installation avec `.venv/bin/python -m pytest -q`.
4. Lancer `.venv/bin/python -m tool generate --seed 5` pour une seed figée.
5. Ajouter `--install` pour copier le mod dans le dossier mods indiqué par `config/user.yaml`.
6. Ajouter `--no-html` pour omettre les vues HTML.

Sans `--seed`, la graine vient de l'horloge système. Avec `--seed 5`, le résultat est reproductible pour un même triplet dump, configuration et seed. Les artefacts vont dans `output/`. Le mod assemblé reste séparé des rapports.

### Récupérer le dump

Le mod compagnon `exporter/` doit être copié dans le dossier mods Factorio. Sa version déclarée dans `info.json` est utilisée. La création d'une partie déclenche l'écriture du dump.
 Le chemin dépend du système, comme décrit dans [exporter.md](exporter.md). Le fichier obtenu remplace `data/vanilla_dump.json`.

Un dump produit avec randputF actif est accepté. Il est canonisé à la lecture, sans ancien garde-fou `EXPORT REFUSE`. La canonisation choisit les recettes préfixées actives et ignore les artefacts à double préfixe.

### Vérifier une modification

La suite compte 862 tests. Le témoin courant de la seed 5 est `e61667692c486e5b9c30efa9f4fbc891`, avec la commande `randputf witness --seed 5 --expect e61667692c486e5b9c30efa9f4fbc891`. Le script `tools/check_anchors.py` contrôle les liens internes de la documentation. La CI lance les tests puis ce contrôle.

Un changement de défaut de configuration change le témoin. Il doit alors être reporté dans `.github/workflows/ci.yml` et dans [witness.md](witness.md).

### Roadmap livrée

1. La génération complète du graphe vanilla est livrée.
2. L'arbre technologique linéaire et la chaîne de fusée sont livrés.
3. La génération de graine à partir de l'heure est livrée.
4. Le dump est extrait par le moteur Factorio via l'exporteur Lua.
5. Les lacs sont creusés au runtime, sans autoplace de ressource fluide.
6. La purge de l'eau vanilla et le remplissage déterministe sont livrés.

### Chantiers à venir

Le classement des bâtiments pourrait être déporté vers l'exporteur. Les types de munitions, la stackabilité réelle et les dépendances entre bâtiments relèvent du même chantier. L'objectif reste de réduire les heuristiques côté Python.

Le passage à un arbre technologique branché reste une piste. Aucune modification de ce type n'est livrée. Les idées non retenues, comme la nappe de rayon fixe pour les lacs, restent dans `atelier/`.

### Livrables

Le wheel inclut `mod/`, `data/`, `config/` et les paquets énumérés dans `pyproject.toml`. Le dossier `atelier/` est exclu par `.gitattributes` et par la liste explicite des paquets. Aucun artefact généré n'est suivi dans git. Le détail de publication figure dans [release.md](release.md).

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les commandes de base fonctionnent depuis l'environnement virtuel. | Les mods tiers ne sont pas pris en charge. |
| Les tests et les ancres sont vérifiés en CI. | Une machine sans Graphviz n'écrit pas le graphe SVG intégré. |
| `atelier/` reste hors des livrables. | Les idées de `atelier/` peuvent devenir obsolètes. |

## Aller plus loin

- [architecture.md](architecture.md) — à lire quand la structure du projet est recherchée.
- [config.md](config.md) — à lire quand un réglage doit être changé.
- [exporter.md](exporter.md) — à lire quand le dump doit être régénéré.
- [modules.md](modules.md) — à lire quand le statut d'un module est incertain.
- [release.md](release.md) — à lire quand une version doit être publiée.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [etat-code.md](etat-code.md) — état courant des composants.
- [witness.md](witness.md) — vérification du déterminisme.
- [DEVIANCES.md](DEVIANCES.md) — écarts assumés et bugs corrigés.
