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

