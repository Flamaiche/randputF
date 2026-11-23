# Dérives, bugs corrigés et écarts connus

Retour : [docs/README.md](README.md).

Ce catalogue sépare les choix de conception, les bugs déjà corrigés et les écarts encore ouverts. Il ne présente jamais une correction prévue comme livrée. Chaque entrée reste courte et vérifiable.

## Ce que ça change pour l'utilisateur

- Les dérives assumées font partie du gameplay généré.
- Les bugs corrigés ne doivent plus bloquer une seed.
- Les écarts connus restent visibles jusqu'à leur correction réelle.

## Mots à connaître

- [divergence assumée](glossaire.md) — écart volontaire par rapport au jeu de base.
- [cycle](glossaire.md) — dépendance fermée qui rend un graphe non jouable.
- [jalon](glossaire.md) — étape qui garantit une catégorie de contenu.
- [rejeu](glossaire.md) — simulation qui détecte les blocages.

## Dérives assumées

- Les recettes des ateliers sont entièrement générées. L'ordre de fabrication des ateliers fait donc partie du jeu.
- Les bâtiments à recette fixe portent une transformation unique, souvent fluide à fluide.
- Les packs de recherche utilisent des intermédiaires, jamais les matières premières environnementales.
- Le palier de départ se débloque par craft manuel, avant l'arrivée des laboratoires.
- Les patchs item sont ramassables au début puis infinis après pose d'une foreuse. Les patchs fluide exigent un pumpjack et les lacs une pompe offshore.
- Les lacs sont creusés au runtime. Le mapgen ne pose aucune tuile de lac ; le flood-fill évite les chevauchements de fluides.

## Bugs corrigés

### Fabrication d'atelier avec des ingrédients FLUIDES → ordre d'usage impossible

Un bâtiment atelier ne se fabrique plus avec des fluides. La garde couvre désormais tous les bâtiments ateliers et extracteurs. Le blocage signalé a disparu.

### Cycle d'hébergement MUTUEL créé par le ré-hébergement U2

Le garde de fermeture transitive couvre les cycles où deux ateliers se fabriquent l'un l'autre. Le ré-hébergement U2 ne referme plus ce cycle.

### Cycle d'hébergement LONG refermé par le ré-hébergement U1

Le graphe d'hébergement est parcouru depuis l'item de l'atelier cible vers le produit. Les cycles longs sont détectés avant le ré-hébergement U1.

### Patch ITEM requérant une foreuse (modèle de mine erroné)

Le rejoueur ne demande plus de foreuse pour le ramassage initial d'un patch item. La foreuse reste requise pour un prélèvement infini.

### Jalon d'une raw gatée au 1er INGRÉDIENT alors qu'elle est requise comme ATELIER

Le plancher d'une raw gatée couvre aussi les usages comme machine. La fermeture des coûts et des déclencheurs de technologies est prise en compte.

### Ordre des effets `unlock-recipe` d'une tech non déterministe (set non trié)

Les effets de recherche sont triés avant sérialisation. La seed ne dépend plus de l'ordre de hachage du processus Python.

### Gating « inerte » (jalons tous ≤ 0) rendant la passe B auto-cassante

Quand tous les jalons sont à zéro ou moins, la passe A est conservée telle quelle. Aucun export de ressources tardives n'est produit dans ce cas.

### Dépendance à l'ordre des seeds d'un même processus (mutation config)

La configuration est copiée avant la seconde passe. Une seed ne peut plus hériter de l'état d'une seed précédente dans le même processus.

## Écarts connus

- Le commentaire sur `buffer_capacity` dans `tool/parsers/vanilla.py` décrit encore l'ancien dump. Le champ est désormais exporté, lu et utilisé.
- Les anciennes pages décrivent encore le rejeu comme optionnel et le garde-fou anti-dump comme actif. Dans `randputf test`, le code courant rejoue par défaut et accepte les dumps moddés.
- Les sections `pools` et `weights` sont validées mais n'ont aucun effet sur le moteur.

### Écart connu : terminologie historique

Les mots « bugs corrigés » et « écarts connus » ne sont pas interchangeables. Une entrée passe de la seconde à la première seulement quand le code et les tests confirment la correction.

## Historique

- Les versions 2.0 appartiennent aux tags `v0.0.0` et `v0.0.1`.
- La version courante vise Factorio 2.1 avec 873 tests.
- Le témoin courant de la seed 5 est `e61667692c486e5b9c30efa9f4fbc891`.
- Les anciens balayages de graines
 restent des diagnostics historiques, pas la preuve de l'état courant.
- Les brouillons et plans non livrés vivent dans `atelier/`, hors des livrables.

## Garanti / non garanti

| Garanti | Non garanti |
|---|---|
| Les corrections listées sont distinctes des intentions. | Un écart connu peut être corrigé sans mise à jour immédiate de cette page. |
| Les dérives assumées décrivent le gameplay livré. | Les mods tiers ajoutent leurs propres écarts. |
| L'historique ne remplace pas l'état courant. | Les anciens balayages ne sont pas rejoués à chaque release. |

## Aller plus loin

- [solvabilite.md](solvabilite.md) — à lire quand un blocage de graphe est suspecté.
- [nondeterminism.md](nondeterminism.md) — à lire quand la reproductibilité est en cause.
- [release.md](release.md) — à lire quand l'écart concerne le zip publié.
- [vanilladb.md](vanilladb.md) — à lire quand l'écart concerne `buffer_capacity`.
- [testeur.md](testeur.md) — à lire quand le rejeu doit être vérifié.

## Lectures associées

- **Parent** : [docs/README.md](README.md) — index de la documentation.
- [etat-code.md](etat-code.md) — état courant des composants.
- [runtime.md](runtime.md) — comportement réel du mod.
- [lacs.md](lacs.md) — dérive assumée des lacs runtime.
