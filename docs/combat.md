# Combat, armement et transports

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 11. Combat et armement

- **Les biters ne changent pas** (pour l'instant) : comportement, évolution et
  pollution restent vanilla.
- **Les armes sont randomisées** : elles sont déblocables selon le même
  système de pourcentages que les autres bâtiments.
- **Munitions** : chaque arme est obtensible avec un type de balles calé sur
  elle. Les *autres* types de munitions (hors catégorie alignée) sont ensuite
  vus comme de simples crafts — plus tard ; ou potentiellement avant, s'ils
  ont été choisis comme recette plus tôt. **Garantie jouable** : quand une
  arme de poing est débloquée par une tech, si **aucune** munition de sa
  catégorie n'est encore débloquée, les munitions manquantes sont générées et
  unlockées dans **la même tech** que l'arme — jamais une arme inutilisable.
  Si une munition de la catégorie est déjà débloquée (avant ou dans la même
  tech), rien n'est ajouté : l'arme peut déjà tirer.

## 12. Transports avancés

Trains, véhicules et logistique avancée suivent exactement le même modèle
que les armes : ce sont simplement des **catégories d'objets** déblocables par
les mêmes pourcentages, avec si besoin des dépendances — toujours
**minimes**, posées au moment du tirage. Forme attendue de ces dépendances :
un véhicule peut exiger un **combustible** pour être utilisable ; un train
exige les **rails avant ou en même temps** que lui. Rien de plus : aucun
traitement spécial.

### 12.1 Armes montées randomisées

Les armes **montées-uniquement** (`VEHICLE_GUNS` : cannons, mitrailleuses,
lance-flammes, artillerie, roquettes de spidertron) sont **exclues du pool de
poing** (§11) et du balayage (§9.6) : sans leur véhicule elles seraient du
contenu mort — elles ne sont **jamais craftées**. La randomisation des
véhicules repose sur une **pool cachée** : `pools.vehicle_weapons` liste de
vrais **items gun** (les armes montées ci-dessus, mais aussi des armes de poing
« adoptables » comme le fusil à pompe, le submachine-gun ou le lance-roquettes).
Chaque **véhicule armé** (tank, spidertron, wagon d'artillerie) reçoit
**1..4 armes** tirées dans TOUTE la pool (avec ou sans remise selon la config) :
un tank peut donc hériter d'un pompe, un spidertron d'une artillerie, etc.

**« Arme dans arme »** : chaque arme tirée est **CLONÉE pour CE véhicule** par
`data-updates.lua` (`randputf-<véhicule>-<arme>`, `table.deepcopy`) et **remplace
une arme vanilla** de l'entité — le véhicule ne garde que les armes tirées
(le tank/spidertron remplacent leur tableau `guns`, le wagon d'artillerie son
`gun` unique). Ni item, ni recette, ni unlock : la pool ne sert QU'à
l'assignation (les items de poing de la pool gardent, eux, leur recette de main
normale, §11). Les items *legacy* (tank-machine-gun vanilla,
spidertron-rocket-launcher-2/3/4, identiques au -1) restent du contenu mort :
jamais de recette ni d'unlock.

**Portée scalée selon la taille du véhicule** : la portée du clone est
augmentée pour un véhicule plus gros —
`range × (1 + max(taille - base_size, 0) × scale)`, avec `taille` = extent de
la `selection_box` de l'entité (tank 2.6, spidertron 2, wagon d'artillerie 6).
Avec les défauts (`base_size: 2`, `scale: 0.4`) : le tank étire ses armes
×1.24, le wagon ×2.6, le spidertron (à la taille de base) garde les portées
d'origine. La **munition** consommée par le clone (ammo_category) est celle de
l'arme source : tout ammo est déjà randomisé/craftable (§9.6).

**Munitions garanties après le véhicule** : quand la tech d'un véhicule est
créée, le générateur vérifie les munitions de ses armes montées (par
`ammo_category`). Celles qui n'ont pas encore de recette (elles auraient été
réparties au hasard, potentiellement très après le véhicule) sont créées
immédiatement et **dispatchées dans les 3 techs isolées qui suivent celle du
véhicule** (`randputf-ammo-<véhicule>-<munition>`, payées en science pack déjà
unlocké) : le joueur reçoit son véhicule avec ses munitions au labo dans la
foulée. Les munitions déjà présentes ne sont pas rejouées.

L'assignation est récoltée dans `vehicle_armament` de la seed (items gun réels,
pas de champ `vehicle_armament_items`), la pool dans `pools.vehicle_weapons` et
le scale dans `pools.vehicle_range_scaling` — **aucune valeur en dur** :
`armed_vehicles`, `vehicle_weapons`, `vehicle_slots_min/max`,
`vehicle_slots_with_replacement`, `vehicle_range_base_size` et
`vehicle_range_scale` se configurent via `recursive:` (§16).

**La randomisation est APPLIQUÉE aux prototypes d'entités** : `data-updates.lua`
clone et ré-arme chaque véhicule à partir de `vehicle_armament`. Sans cela la
seed ne changerait RIEN en jeu : les véhicules garderaient leur armement vanilla
figé.
