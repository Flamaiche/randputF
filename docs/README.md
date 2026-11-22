# Documentation randputF

Retour : [README racine](../README.md).

Cette documentation explique ce que randputF génère, comment le mod applique une
seed et comment vérifier le résultat. Elle est écrite pour un lecteur qui n'a pas
le code sous les yeux. Les définitions sont regroupées dans le
[glossaire](glossaire.md).

## Choisir une porte

| Besoin | Porte | Première lecture |
|---|---|---|
| Je veux comprendre le principe | Comprendre | [glossaire](glossaire.md), [modèle](model.md) |
| Je veux suivre la création d'une partie | Jouer | [ressources](ressources.md), [starter](starter.md), [technologies](tech.md) |
| Je veux vérifier une seed | Vérifier | [solvabilité](solvabilite.md), [witness](witness.md), [testeur](testeur.md) |
| Je veux modifier l'outil | Développer | [architecture](architecture.md), [pipeline](pipeline.md), [runtime](runtime.md) |

## Parcours conseillé

### Jouer

1. [README racine](../README.md) — installer et lancer une partie.
2. [glossaire.md](glossaire.md) — comprendre les mots utilisés.
3. [starter.md](starter.md) — ce que contient le départ.
4. [tech.md](tech.md) — ce qui reste à faire jusqu'à la victoire.

### Comprendre

1. [glossaire.md](glossaire.md) — vocabulaire minimum.
2. [model.md](model.md) — bâtiments, slots et directives.
   - [tags.md](tags.md) — rôles utilisés par le modèle.
   - [ressources-brutes.md](ressources-brutes.md) — items, fluides, patches et lacs.
3. [ressources.md](ressources.md) — ressources au sol.
   - [lacs.md](lacs.md) — nappes de fluide.
4. [starter.md](starter.md) — départ et chaîne initiale.
   - [amorcage.md](amorcage.md) — règles de démarrage sans impasse.
5. [recettes.md](recettes.md) — génération récursive.
   - [aiguillage.md](aiguillage.md) — rattachement aux technologies.
   - [energie.md](energie.md) — courant et chaleur.
   - [chaleur.md](chaleur.md) — triade thermique.
   - [combat.md](combat.md) — armes et véhicules.
   - [tech.md](tech.md) — arbre technologique et fin de partie.

### Vérifier

1. [solvabilite.md](solvabilite.md) — ce qui est garanti.
   - [invariants.md](invariants.md) — liste courte des invariants.
   - [nomenclature-rejoueur.md](nomenclature-rejoueur.md) — vocabulaire du rejeu.
2. [seed.md](seed.md) — graine et reproductibilité.
   - [witness.md](witness.md) — témoin de déterminisme.
   - [nondeterminism.md](nondeterminism.md) — correctifs actifs.
   - [historique-nondeterminisme.md](historique-nondeterminisme.md) — historique daté.
3. [testeur.md](testeur.md) — contrôle et rejeu.
   - [graphe-interactif.md](graphe-interactif.md) — rapports HTML.

### Développer

1. [architecture.md](architecture.md) — structure du projet.
   - [pipeline.md](pipeline.md) — ordre d'exécution.
   - [modules.md](modules.md) — rôles des modules.
   - [config.md](config.md) — réglages.
   - [vanilladb.md](vanilladb.md) — dump et inférences.
2. [runtime.md](runtime.md) — contrat entre la seed et le mod Lua.
   - [exporter.md](exporter.md) — production du dump vanilla.
3. [developpement.md](developpement.md) — environnement et roadmap.
   - [etat-code.md](etat-code.md) — état courant des composants.
4. [release.md](release.md) — publication et versions.
   - [DEVIANCES.md](DEVIANCES.md) — dérives assumées et bugs corrigés.

## Index par fichier

### Vocabulaire et conception

| Document | Contenu |
|---|---|
| [glossaire.md](glossaire.md) | Définitions courtes des termes utilisés dans la doc. |
| [model.md](model.md) | [Terminologie](model.md#terminologie) ; [modèle randput](model.md#le-modèle-randput--classification-des-bâtiments). |
| [tags.md](tags.md) | Tags de bâtiments et d'items. |
| [ressources-brutes.md](ressources-brutes.md) | Formes des ressources et extracteurs. |
| [ressources.md](ressources.md) | Ressources au sol et pose runtime. |
| [lacs.md](lacs.md) | Génération des lacs de fluide. |
| [starter.md](starter.md) | Kit de départ et techs gratuites. |
| [amorcage.md](amorcage.md) | Règles de démarrage. |
| [recettes.md](recettes.md) | Génération des recettes. |
| [aiguillage.md](aiguillage.md) | Rattachement aux technologies. |
| [energie.md](energie.md) | Électricité et chaleur. |
| [chaleur.md](chaleur.md) | Triade source, transport, consommateur. |
| [combat.md](combat.md) | Armes, munitions et véhicules. |
| [tech.md](tech.md) | Arbre technologique et victoire. |

### Garanties et reproductibilité

| Document | Contenu |
|---|---|
| [solvabilite.md](solvabilite.md) | Bootstrap, validateurs et invariants. |
| [invariants.md](invariants.md) | Invariants énoncés une seule fois. |
| [nomenclature-rejoueur.md](nomenclature-rejoueur.md) | Correspondance seed et rejeu. |
| [seed.md](seed.md) | Graine, configuration et sorties. |
| [witness.md](witness.md) | Témoin de déterminisme. |
| [nondeterminism.md](nondeterminism.md) | Correctifs actifs. |
| [historique-nondeterminisme.md](historique-nondeterminisme.md) | Historique des diagnostics. |

### Architecture et outillage

| Document | Contenu |
|---|---|
| [architecture.md](architecture.md) | Structure du projet. |
| [pipeline.md](pipeline.md) | Chronologie de génération. |
| [modules.md](modules.md) | Rôles des modules Python. |
| [config.md](config.md) | Clés de configuration et validation. |
| [vanilladb.md](vanilladb.md) | Format du dump vanilla. |
| [exporter.md](exporter.md) | Exporteur Factorio. |
| [runtime.md](runtime.md) | Mod Lua et clés consommées. |
| [testeur.md](testeur.md) | Testeur de dump et rejeu. |
| [graphe-interactif.md](graphe-interactif.md) | Vues HTML. |
| [developpement.md](developpement.md) | Environnement de développement. |
| [etat-code.md](etat-code.md) | État courant du code. |

### État et historique

| Document | Contenu |
|---|---|
| [DEVIANCES.md](DEVIANCES.md) | Dérives assumées et bugs corrigés. |
| [release.md](release.md) | Publication et versions. |

### Documents liés

| Document | Contenu |
|---|---|
| [README racine](../README.md) | Installation et utilisation. |
| [README_EN.md](../README_EN.md) | Miroir anglais du README. |
| [CHANGELOG.md](../CHANGELOG.md) | Historique des changements. |
| [notes de release](../notes/README.md) | Notes publiées par version. |
| [atelier/IDEES.md](../atelier/IDEES.md) | Pistes non livrées. |
| [atelier/README_BRANCHE.md](../atelier/README_BRANCHE.md) | Branches conservées. |

## Lectures associées

- **Parent** : [README racine](../README.md) — installation et utilisation.
- [glossaire.md](glossaire.md) — à lire dès qu'un terme est inconnu.
- [CHANGELOG.md](../CHANGELOG.md) — historique des changements.
