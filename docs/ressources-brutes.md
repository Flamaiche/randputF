# Les ressources brutes et leur extraction

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## Les formes d'une ressource brute

Ce doc est le **cas partagé** entre [ressources.md](ressources.md) (qui pose les raw)
et [starter.md](starter.md) (qui les extrait au démarrage) : il décrit ce qu'elles ont
en commun — leur **forme**, leur **support** et leur **extracteur**.

Une **ressource brute** (raw) est extraite directement du milieu. Elle se présente
sous **trois formes**, chacune avec son support physique et son extracteur :

| Forme | Support sur la carte | Extracteur | Énergie | Milieu |
|---|---|---|---|---|
| **Patch d'items** | entité-ressource `randputf-minerai-<item>` | **foreuse** (`mining-drill`) | électrique ou combustible | `ground` |
| **Patch de fluide** | entité-ressource `randputf-oil-<fluide>` (`basic-fluid`) | **pumpjack** (`mining-drill` + `resource_categories ⊇ basic-fluid`) | électrique | `fluid` |
| **Lac de fluide** | tuile `randputf-lac-<fluide>` | **pompe offshore** | énergie void (aucune électricité) | `water` |

Trois conséquences structurent tout le reste :

- **Deux milieux fluides distincts** : un *patch* et un *lac* de fluide portent le
  même contenu (un fluide pipable) mais pas le même support — **entité** posée sur la
  terre pour l'un, **tuile** d'eau pour l'autre. Le moteur en déduit **deux
  extracteurs** distincts : pumpjack (électrique) et pompe offshore (énergie void).
  C'est ce qui rend un générateur à vapeur **amorçable sans électricité** dès que la
  seed tire au moins un lac (voir [energie.md](energie.md#lélectricité)).
- **Une amorce par type d'extracteur** : le kit de départ fournit l'item de chaque
  extracteur utile (une foreuse par type de sol ; côté fluides, un pumpjack pour les
  patchs et une pompe offshore pour les lacs). Le kit ne rend pas la suite faisable
  par sa dotation : c'est l'**unlock** qui la rend faisable (voir
  [starter.md](starter.md#la-phase-de-démarrage), déblocage « juste-au-besoin »).
- **La richesse se lit par forme** : un patch d'item répartit sa richesse **totale par
  tuile** posée ; un patch de fluide conserve un **rendement par puits** ; un lac a une
  richesse de forme (taille/densité) mais un **volume illimité**.

La **pose** de chaque forme (tirage sans remise, disque bruité des champs d'items,
puits éparpillés des fluides, fantôme puis remplissage des lacs) est détaillée dans
[ressources.md](ressources.md#les-ressources-au-sol) ; la mécanique runtime du lac est dans
[starter.md](starter.md#la-phase-de-démarrage) (point 5) ; la **chaîne initiale** qui consomme ces formes est en
[starter.md](starter.md#la-chaîne-initiale-starter).

---

## Lectures associées

- **Parent** : [ressources.md](ressources.md) — les ressources au sol.
- **Concepts liés** : [starter.md](starter.md) — la phase de démarrage ; [energie.md](energie.md) — électricité ; [model.md](model.md) — le modèle randput : terminologie et classification des bâtiments.
