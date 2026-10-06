# Combat, armement et transports

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## 11. Combat et armement

- **Les biters ne changent pas** : pour le moment, leur comportement, leur évolution et la pollution restent identiques à la version vanilla.
- **Les armes sont randomisées** : leur déblocage suit le système de pourcentages appliqué aux autres bâtiments.
- **Munitions** : chaque arme obtenue est liée à un type de munitions spécifique. Les autres catégories de munitions sont traitées comme des crafts standards plus tard, ou plus tôt si elles ont été sélectionnées comme recettes. **Garantie jouable** : si une arme est débloquée par une technologie alors qu'**aucune** munition de sa catégorie n'est disponible, les munitions manquantes sont générées et débloquées dans **la même tech**. Une arme n'est jamais inutile. Si une munition compatible existe déjà, rien n'est ajouté.
- **Une arme par tech** : le groupement du §13 ne fusionne jamais deux étapes de combat consécutives (même règle que pour les pylônes au §9.4). Cela évite qu'une seule technologie débloque plusieurs armes et leurs munitions d'un coup. Chaque arme arrive seule, avec sa munition dédiée.

## 12. Transports avancés

Trains, véhicules et logistique avancée utilisent le même modèle que les armes. Ce sont des **catégories d'objets** déblocables par pourcentages. Les dépendances sont **minimes** et fixées lors du tirage : un véhicule peut exiger un **combustible** ; un train impose les **rails avant ou en même temps** que lui. Aucun autre traitement spécial n'est appliqué.

### 12.1 Armes montées randomisées

Les armes **montées-uniquement** (`VEHICLE_GUNS` : canons, mitrailleuses, lance-flammes, artillerie, roquettes de spidertron) sont **exclues du pool de poing** (§11) et du balayage (§9.6). Sans véhicule, elles seraient inutilisables ; elles ne sont donc **jamais craftées**. La randomisation des véhicules utilise une **pool cachée** : `pools.vehicle_weapons` liste des **items gun** (armes montées et certaines armes de poing comme le fusil à pompe, le submachine-gun ou le lance-roquettes). Chaque **véhicule armé** (tank, spidertron, wagon d'artillerie) reçoit **1..4 armes** tirées dans cette pool, avec ou sans remise selon la configuration. Un tank peut ainsi hériter d'un fusil à pompe et un spidertron d'une pièce d'artillerie.

**« Arme dans arme »** : chaque arme tirée est **CLONÉE pour CE véhicule** par `data-updates.lua` (`randputf-<véhicule>-<arme>`, via `table.deepcopy`) et **remplace une arme vanilla** de l'entité. Le véhicule ne conserve que les armes tirées : le tank et le spidertron remplacent leur tableau `guns`, le wagon d'artillerie son `gun` unique. Il n'y a ni item, ni recette, ni unlock pour ces clones : la pool sert uniquement à l'assignation. Les items de poing de la pool conservent leur recette normale (§11). Les items *legacy* (mitrailleuse de tank vanilla, spidertron-rocket-launcher-2/3/4) deviennent du contenu mort sans recette ni unlock.

**Portée scalée selon la taille du véhicule** : la portée du clone augmente avec la taille du véhicule selon la formule `range × (1 + max(taille - base_size, 0) × scale)`. La `taille` correspond à l'extent de la `selection_box` (tank 2.6, spidertron 2, wagon d'artillerie 6). Avec les valeurs par défaut (`base_size: 2`, `scale: 0.4`), le tank augmente la portée de ses armes de ×1.24 et le wagon de ×2.6. Le spidertron, à la taille de base, conserve les portées d'origine. La **munition** consommée par le clone (ammo_category) est celle de l'arme source, car chaque munition est déjà randomisée et craftable (§9.6).

**Munitions garanties après le véhicule** : lors de la création de la technologie d'un véhicule, le générateur vérifie les munitions de ses armes (via `ammo_category`). Celles qui n'ont pas encore de recette sont créées immédiatement et **dispatchées dans les 3 techs isolées qui suivent celle du véhicule** (`randputf-ammo-<véhicule>-<munition>`). Elles coûtent des packs de science déjà débloqués. Le joueur reçoit ainsi son véhicule, puis ses munitions rapidement après au laboratoire. Les munitions déjà présentes ne sont pas recalculées.

L'assignation est enregistrée dans `vehicle_armament` (items gun réels, sans champ `vehicle_armament_items`), la pool dans `pools.vehicle_weapons` et le scale dans `pools.vehicle_range_scaling`. **Aucune valeur n'est en dur** : `armed_vehicles`, `vehicle_weapons`, `vehicle_slots_min/max`, `vehicle_slots_with_replacement`, `vehicle_range_base_size` et `vehicle_range_scale` se configurent via `recursive:` (§16).

**La randomisation est APPLIQUÉE aux prototypes d'entités** : `data-updates.lua` clone et ré-arme chaque véhicule selon `vehicle_armament`. Sans cette étape, les véhicules conserveraient leur armement vanilla et la seed n'aurait aucun effet en jeu.
