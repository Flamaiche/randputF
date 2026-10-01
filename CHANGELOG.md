# Changelog

Résumé des versions, format « highlights ». Le détail technique et le
catalogue des corrections seed par seed vivent dans
[`docs/`](docs/README.md) — notamment [DEVIANCES.md](docs/DEVIANCES.md) (bugs et
dérives), [solvabilite.md](docs/solvabilite.md) (preuves) et
[nondeterminism.md](docs/nondeterminism.md).

Format : les faits sont repris des docs, jamais inventés ici. « gaté » est le
vocabulaire du projet (gating, §16 de `seed.md`), pas une faute.

---

## v1.0.0

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

- **Bootstrap guard (seed 13)** : un cycle où l'électricité exigeait déjà
  l'électricité (turbine → landfill → tuyau → atelier électrique) rendait la seed
  injouable ; le bootstrap sûr résout ce cas.
- **Ordre d'usage des fluids (seed 426)** : un atelier à ingrédients fluides
  rendait l'ordre d'usage impossible ; corrigé.
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