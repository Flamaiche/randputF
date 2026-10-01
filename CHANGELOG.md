# Changelog

Résumé des versions, format « highlights ». Le détail technique et le
catalogue des corrections seed par seed vivent dans
[`docs/`](docs/README.md) — notamment [DEVIANCES.md](docs/DEVIANCES.md) (bugs et
dérives), [solvabilite.md](docs/solvabilite.md) (preuves) et
[nondeterminism.md](docs/nondeterminism.md).

Format : les faits sont repris des docs, jamais inventés ici. « gaté » est le
vocabulaire du projet (gating, §16 de `seed.md`), pas une faute.

---

## v1.0.1

Release de documentation et de configuration.

### Configuration à deux YAML

- **`config/settings.yaml` est remplacé** par `config/defaults.yaml` (tous les
  réglages par défaut, source unique, non modifiable) + `config/user.yaml`
  (surcharges facultatives). La génération lit la config fusionnée et la
  **valide** : type, plage, `min <= max`, contraintes croisées. Une clé inconnue
  ou une valeur impossible est une erreur explicite, jamais un défaut muet.
- **Migration** : si vous aviez modifié `settings.yaml`, recopiez vos surcharges
  dans `user.yaml` (mêmes clés, mêmes sections). Le format est identique ;
  `settings.yaml` n'est plus lu.
- **Plus aucune valeur de réglage en dur dans le moteur** : prototypes,
  générateurs, CLI et pipeline lisent tous leurs valeurs depuis le YAML.
- Référence complète des sections dans `docs/config.md`.

### Documentation

- **Refonte documentaire complète** (revue du 30 septembre 2026, lots A à I) :
  README, index `docs/`, `docs/config.md`, `docs/witness.md`,
  `docs/graphe-interactif.md`, `docs/solvabilite.md`, découpage de la densité
  (`starter.md`, `recettes.md`), `CHANGELOG.md`, `README_EN.md` pour les
  lecteurs anglophones.
- **Arbre de structure `docs/architecture.md` §18** remis à jour contre le code
  réel (vérifié par script : tous les `.py` des sept sous-dossires de `tool/`).
- **Témoin de déterminisme documenté** dans `docs/witness.md` : canonisation,
  exclusions, et pourquoi le hash change à chaque bump de version.
- Terme « gaté » (gating) déclaré comme vocabulaire du projet : ce n'est pas
  une faute de frappe.

### Notes de chantier

Les plans et notes de révision sont regroupés dans `atelier/`, **dossier absent
des tags**. Aucun tag ne contient de document de chantier.

### Garanties mesurées

- **722 tests** verts.
- **Témoin seed 5** : `ce428c2140ec7031f9604637ecf70cbc`. Le contenu du mod est
  inchangé depuis la v1.0.0 ; le hash change car le préfixe racine du zip porte
  `randputF_<version>`.

[v1.0.1]: https://github.com/Flamaiche/randputF/releases/tag/v1.0.1
[v1.0.0]: https://github.com/Flamaiche/randputF/releases/tag/v1.0.0

Première release publique. Randomizer total déterministe pour Factorio 2.0
(base, sans Space Age).

### Déterminisme vérifiable

- **Témoin de reproductibilité** : `randputf witness --seed 5 --expect
  12ac143e06174df126537b978ff928d3`. Le même contenu de mod, à l'octet près,
  vérifiable par n'importe qui (le hash est dans la CI et la release).
- **Canonisation indépendante de la machine et de la version de Python/zlib**
  (détail dans `docs/witness.md`).

### Garanties mesurées

- **722 tests** verts, rendus indépendants de l'environnement.
- **Rejoueur « fake player »** : **1501/1501 parties** rejouées victorieuses sur
  le balayage de seeds 0-1500 (rejouer une seed = la simuler comme un joueur la
  découvre). Invariants de solvabilité §15 garantis pour toute seed acceptée.
- **Déterminisme entre processus** et **indépendant de l'ordre** : une seed
  générée après 1400 autres reste byte-identique à celle d'un processus vierge
  (multi-sous-processus sous `PYTHONHASHSEED` 0/1/2).

### Corrections emblématiques (le chemin parcouru)

Le détail seed par seed est dans [DEVIANCES.md](docs/DEVIANCES.md). Les plus
significatifs :

- **Bootstrap sûr (seed 13)** : un cycle où l'électricité exigeait déjà
  l'électricité (turbine → landfill → tuyau → atelier électrique) rendait la seed
  injouable. Le redesign du bootstrap (graphe initial correct par construction)
  résout ce cas ; `bootstrap_guard` n'est plus une passe de production, il
  reste un diagnostic de test.
- **Fabrication d'atelier avec des ingrédients fluides (seed 426)** : la recette
  d'un bâtiment à ≥ 2 slots fluides se retrouvait hébergée dans un atelier
  fluide unlocké tard, donc jamais disponible à temps ; les bâtiments se
  fabriquent désormais uniquement avec des items.
- **Cycles d'hébergement (seeds 255, 1043)** : cycles mutuel (U2) et long (U1)
  créés par le ré-hébergement, cassés par les passes d'usage.
- **Ordre des effets `unlock-recipe` non déterministe (seed 1299)** : un `set`
  non trié rendait l'ordre des déblocages dépendant du hash de Python ; trié.
- **Jalon de raw gatée au 1er ingrédient (seed 1299)** : plancher recalculé sur
  l'usage réel (ingredients + ateliers).
- **Gating inerte (seed 1757)** : jalons tous ≤ 0 ; la passe B rejouée ne
  cassait plus rien.
- **Dépendance à l'ordre des seeds (seed 1269)** : la passe B mutait alors le
  config partagé ; état vierge porté par `StarterConfig.deferred`.

### Produit

- Mod Lua (`mod/`) produit par une CLI Python (`tool/`) ; dump JSON des
  prototypes vanilla embarqué (pas de dépendance runtime à l'exporter).
- Packaging wheel avec assets (`mod/`, `data/`, `config/`), vérifié par le job CI
  « wheel » (témoin exécuté hors checkout).
- Licence MIT. Documentation de conception complète dans [`docs/`](docs/README.md).

[v1.0.0]: https://github.com/Flamaiche/randputF/releases/tag/v1.0.0