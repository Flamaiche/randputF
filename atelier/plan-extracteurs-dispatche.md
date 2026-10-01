# Plan v2 : jalons de ressources (« late raw resources »)

Document de travail retracé : gestation de l'idée, mesures, puis **mise en
œuvre réelle (v3, implémentée)** — voir §8. Le rollback (§4) et la règle
50 % (§2) n'ont **pas** été retenus.

Retour : [docs/README.md](../docs/README.md).

---

## 0. Contexte (corrigé) — le problème de départ

Le vrai point de départ, plus loin dans le design :

> **On ne veut PAS avoir tous les extracteurs du jeu disponibles au début.**

L'approche actuelle (C3 `extractor_timing`, « dispatcher plus loin les extracteurs
dont on n'a pas besoin dès le début ») **ne marche pas et est mal faite** : on
cuisine les recettes du starter avec tout le pool, puis on déplace froidement des
claims en fin de pipeline → softlocks au rejoueur (65/75 échecs après le correctif
item-ingrédient). Cette approche « dispatch » est **abandonnée** au profit d'un
design par **jalons de ressources**.

But visé avec le nouveau design :
- **meilleure ascendance du joueur** (progression qui donne envie : on débloque
  des ressources au fil du jeu comme des paliers) ;
- **meilleur contrôle des raws ressources** (on sait où et quand chaque raw entre
  dans le graphe) ;
- réduction des échecs rejoueur (mesure 126/75 aujourd'hui, objectif < 75).

---

## 1. Principe : les « late raws » comme jalons

### Détection des ressources à retirer du début
Au démarrage, on passe les raws/fluides en revue et on détecte ceux qui ont **le
moins de dépendance au début** :

- **dépendance de craft** (très peu de recettes du début les consomment) ;
- **dépendance de chaleur** (non requis par la chaîne chaleur/énergie du spawn) ;
- **dépendance d'électricité** (non requis par la chaîne élec du spawn).

Ces ressources — les « late raws » — sont **retirées du set de départ** et
**réutilisées plus loin** : ce sont les **jalons de ressource** de la run.

### Ce que ça change pour le joueur
Chaque late raw devient un palier : le joueur commence sans, puis « découvre » la
ressource quand le graphe en a besoin pour un craft important. D'où la meilleure
ascendance + le contrôle des raws (chaque raw a un point d'entrée défini).

---

## 2. Règle de placement d'un late raw dans le graphe

Quand il est temps de placer un late raw : on attribue **une ressource brute
aléatoire, pas encore placée**, à la **position plus loin** où le graphe en a
besoin.

### La ressource est placée comme un BESOIN
Le late raw entre dans le graphe **comme un besoin plutôt essentiel** : c'est une
ressource dont on aura pas mal besoin, donc les **crafts importants** s'y
branchent (on la branche là où elle fait le plus sens, cf. §4).

### Règle d'attribution de l'extracteur
Quand la ressource est placée comme besoin :

- **50 %** de chance de donner **un extracteur supplémentaire** à l'utilisateur,
  parmi ceux **pas encore donnés**, pour extraire cette ressource ;
- si **il n'y a pas encore d'extracteur** pour cette ressource →
  **100 %** (garanti : une ressource sans extracteur est inutilisable).

*(Interprétation du « supplémentaire » à préciser : extracteur bonus reçu au
placement vs extracteur simplement unlocké pour la ressource. Voir §7.)*

---

## 3. Reconstruction en deux temps (base sûre)

Une fois les late raws **reportés** (retirés du pool de départ) :

1. **Régénérer le starter** sur la base réduite → une **base sûre** : le spawn ne
   promet que des raws réellement présents dès le début (rien qui sera placé plus
   tard) ;
2. **Refaire le graphe** : on construit le graphe complet ; au moment où un late
   raw doit être placé, on le branche sur les **crafts importants** (§2/§4).

L'ordre des phases devient donc : *détection → retrait (report) → régénération du
starter → re-construction du graphe avec insertion des late raws* — au lieu de
*construction complète → dispatch froid des claims* (approche abandonnée, §0).

---

## 4. Construction du graphe : marche arrière (rollback)

Pour être efficace, l'implémentation du graphe doit pouvoir **faire marche
arrière** quand on le construit :

1. on **construit le graphe** normalement ;
2. on **surveille** quand un late raw doit être mis dans le graphe (condition §2) ;
3. quand ce moment arrive, on **continue le graphe un peu** (on laisse quelques
   crafts de plus) ;
4. pour la **ressource la plus utilisée** du segment parcouru, on la **remplace
   par le late raw** au moment où il fallait le placer (le late raw devient
   l'ingrédient principal des crafts importants de ce segment) ;
5. on **roll back le graphe** et on **le refait avec cette ressource** (on
   reconstruit le segment en branchant le late raw à sa place).

Résultat : chaque late raw est inséré là où il est **le plus utile** (la ressource
qu'il remplace était la plus consommée du moment), sans casser le graphe — d'où le
retour arrière au lieu d'une correction à froid.

---

## 5. Impact sur le code (repérage)

- `tool/generator/pipeline.py` : orchestration en 2 temps (détection+report →
  regénération starter → graphe avec rollback) ; la passe C4quater actuelle
  `apply_extractor_timing` est remplacée/réécrite selon le §2.
- `tool/generator/extractor_timing.py` : nouvelle loi (jalons, 50 %/100 %,
  remplacement de la ressource la plus utilisée) — l'actuel « dispatch » s'efface.
- `tool/generator/starter_chain.py` : starter regénéré sur le set réduit ; les
  extracteurs des late raws ne sont PAS exposés au départ.
- `tool/generator/recipes.py` : pool d'ingrédients position-dépendant (un late raw
  n'est utilisable qu'à partir de son jalon) + branchement des crafts importants ;
  gestion nécessaire du **rollback** (snapshot/restore du ProgressionState).
- `tool/replay/player.py` : la mesure (ne pas y toucher).

---

## 6. Mesure et plan d'exécution

1. Ajouter le **mécanisme rollback** sur l'état de construction
   (`ProgressionState` snapshot/restore) — pré-requis §4.
2. **Détection des late raws** (moindre dépendance craft/chaleur/élec au début) et
   **report** hors du starter ; régénération du starter sur la base sûre.
3. **Insertion des jalons** pendant la construction : placement +
   règle d'extracteur (50 % / 100 %) + remplacement de la ressource la plus
   utilisée + rollback du segment.
4. Re-balaver 0-201 (objectif : < 75 échecs, idéalement vers 201 victoires),
   relancer `pytest` (690 attendus).
5. Ajuster les invariants (cap/50 %/sélection de la ressource remplacée).
6. Traiter séparément la classe « SANS FUSÉE » (23 seeds — toutes techs
   recherchées mais victoire fusée impossible).
7. Mettre à jour `docs/DEVIANCES.md` §3.2 et ce plan selon les résultats.
   Commit sur `annexe`.

---

## 6bis. Mesures (tools/classify_late_raws.py, 0-201, pipeline ACTUEL)

Classification par `(seed, recette d'extracteur, ressource brute)` : bucket C3,
fermeture D4bis de la boîte du spawn, index + science du 1er consommateur.

| métrique | valeur |
|---|---|
| répartition des 1479 raws par échelon science du 1er consommateur | tier 0 : 1174 ; tier 1 : 148 ; tier 2 : 66 ; tier 3 : 36 ; tier 4 : 22 ; tier 5 : 19 ; tier 6 : 14 |
| raws hors boîte du spawn (`startup=False`) | 353 (dont 1174−1126… : boîte « True » 1126) |
| extracteurs non « starter » (bucket timed) | 113 / seed 0..6 (médiane 0) ; aucun « random » |

Constat structurant : **les 75 échecs se concentrent sur les fluides tardifs**
(H2SO4, famille pétrole/gaz/pétrogaz, vapeur, lubrifiant) cuisinés en
ingrédients de science packs — jamais un raw de la boîte du spawn. Seeds en
échec avec un raw hors boîte : 60/75 (80 %). La gating (« retirer du pool de
départ les raws non-spawn ») force donc le ré-bakage des packs sans ces raws →
recettes 1res moins profondes. Conséquences avalisées : les arbres des seeds
changent (majorité d'entre elles), les goldens des tests sont régénérés à
l'étape 4 (invariants, pas fixtures figées).

Opérationnalisation retenue pour le §6.2 : **late raw = raw avec
`startup=False`** (fermeture D4bis déjà codée dans
`extractor_timing._startup_raw_resources`, réutilisée sur la seed de la passe A).
La passe A (pipeline actuel) mesure ; la passe B régénère avec le pool réduit
(+ injection des jalons, §2/§4).

---

## 7. Points ouverts (à trancher)

- **« extracteur supplémentaire »** : au placement d'un late raw, on donne un
  extracteur bonus (un de plus que le minimum) OU on assure seulement qu'il a au
  moins un extracteur ? La lecture « parmi ceux pas encore donnés » reste à
  confirmer.
- **« ressource la plus utilisée »** : le critère exact pour choisir l'item/raw
  qui est remplacé par le late raw (plus consommé du segment ? plus produit ?
  plus critique pour la chaîne ?).
- **Probabilité 50 %** : par placement de late raw, par ressource, ou par
  segment ?
- **Portée du rollback** : on backwarde par segment (players du §4) ou récursif
  jusqu'au point de divergence ?
- **Hiérarchie des « crafts importants »** : comment décider qu'un craft est
  « essentiel » (packs ? chaîne fusée ? bâtiments ?) pour y brancher le late raw.
- La classe « SANS FUSÉE » : couverte par ce design ou correctif séparé ?

---

## 8. Mise en œuvre réelle (v3, implémentée)

Le design retenu abandonne le §2/§4 (remplacement de la ressource la plus
utilisée, règle 50 %, rollback de segment) au profit de l'« opérationnalisation »
du §6bis, affinée :

- **Architecture 2 passes, même seed** (`tool/generator/late_raws.py`,
  `pipeline.py`) : passe A = pipeline historique → plan mesuré (gating 100 %,
  injection déterministe) ; passe B = **même référence RNG**, prefixe
  (carte/élec/starter) **rejoué à l'identique puis dégradé** — les raws gatées
  sortent de `obtained`. Pas de « régénération du starter sur pool réduit » :
  le starter est rejoué à l'identique et son état est viergé après coup
  (**`StarterConfig.deferred`**, posé dans `cfg["starter"]["deferred"]`).
- **Late raw = raw hors boîte du spawn D4bis** (`startup=False` via
  `_startup_raw_resources`). Son **jalon** = échelon science (index de chaîne
  des packs) du 1er usage scanné sur la partie refaite : `_usage_floors`
  compte les consommations comme **ingrédient**, comme **atelier**
  (`crafted_in`), et la **fermeture transitive des coûts et déclencheurs** de
  chaque tech (préfixe des recettes débloquées ≤ index). Défaut : max des
  échelons si la raw n'est jamais requise structuellement.
- **Cas révélateur — seed 1299** : `randputf-stone-furnace` est
  `crafted_in='steel-furnace'` et `steel-furnace` était jalonnée au tier 4
  (1er **ingrédient**) alors qu'elle est requise comme **machine** dès le
  tier 0 (`production-science-pack` → `lab` → `electric-mining-drill` →
  `stone-furnace`) → les packs du coût de la tech 5 ne se fabriquent pas →
  défaite en gaté (88/88 en baseline). Le plancher intégrant l'usage machine +
  la fermeture des coûts la rétrograde au tier 0 → **victoire**.
- **Directive de passage (2026-09-30)** : après le balayage 1600-2000, une perte
  unique a resurgi — **seed 1757** (toutes les raws gatées jalonnées au tier 0 =
  gating « inerte » : rien de réellement retenu). Rejouer la passe B ne faisait
  que re-générer un **arbre différent** (régression sans gain de dispo, défaite
  à la tech 21 vs victoire 89/89 en baseline). Ajout : quand tous les jalons du
  plan sont ≤ 0, la seed sert la **passe A telle quelle**, byte-identique à
  l'historique (aucun export `late_raws`) — `pipeline.py`. En suivant, une perte
  de balayage non reproductible en process vierge a mis au jour une dépendance à
  l'ordre des seeds d'un même process (mutation en place du config partagé par
  la passe B — seed 1269) : corrigée par copie défensive (`docs/nondeterminism.md`
  §7) et le balayage complet re-joué.
- **Mesures (code corrigé)** : balayage gaté par paquets de 400 (vérification
  après chaque paquet) — **0-2000 : 2000 victoires / 0 défaite** (contigu) ;
  suite `pytest` **705 verts**, déterminisme byte-à-byte sous 3 hashseeds
  (0/1/2) sur seeds gatées 1/10/37/412/1299/1400.
- **Honorabilité du balayage** : celui-ci, comme toute génération multi-seeds,
  est porté par le garde §7 (`nondeterminism.md`) — une seed générée après 1400
  autres est byte-identique à une génération unique (process vierge = usage CLI
  réel).