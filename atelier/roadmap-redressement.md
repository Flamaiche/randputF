# Feuille de route : redressement documentaire

> **Document de travail, non revu depuis son écriture.** Ses chemins,
> ses chiffres et le code qu'il cite peuvent avoir changé depuis. L'état
> courant est dans [`docs/`](../docs/) et
> [`CHANGELOG.md`](../CHANGELOG.md).

Plan d'action issu de la revue indépendante du 30 septembre 2026
(*revue complète de la documentation randputF*). Couvre les 10 actions
priorisées de la revue, plus les divergences doc/code detectees en
preparant ce plan.

Convention : chaque tache est un lot de commits sur `dev` (jamais de push
direct ; le push reste une decision du mainteneur). Effort indicatif.

Retour : [docs/README.md](../docs/README.md).

---

## Priorites

| Lot | Contenu | Effort | Depend de |
|---|---|---|---|
| A | Ligne assistant IA + lien branche `dev` | 5 min | - |
| B | `CHANGELOG.md` | 30 min | - |
| C | Passe de relecture (typos + densite) | 1 h | - |
| D | `docs/config.md` + amenagement du README | 30 min | C |
| E | `docs/witness.md` + release note restructuree | 1 h | - |
| F | Divergences doc/code (bootstrap_guard, release) | 45 min | - |
| G | Section graphe interactif dans `docs/` | 45 min | - |
| H | Nettoyage de `developpement.md` (separer chantier/release) | 30 min | - |
| I | Badge + README EN | 2-3 h | D, E |
| J | GIF / captures d'ecran | 1 h | - |

---

## Lot A : les deux lignes qui changent la perception (5 min)

- [x] **A1 — Mention de l'assistant IA** en fin de README, section discrete
      « Outils », pas en gros titre. Une ligne factuelle : l'assistant a
      assiste a la relecture et a la redaction ; la conception, les decisions
      et les corrections ont ete pilotees et validees par le mainteneur.
- [x] **A2 — Lien vers la branche `dev`** (« l'historique complet de
      developpement vit sur la branche `dev` » ; le `master` est squashé en un
      commit de release), dans la section « Structure du projet » ou en fin de
      README. Le squash est assume ; le lien rend le parcours accessible.

## Lot B : CHANGELOG.md (30 min)

- [x] **B1** Creer `CHANGELOG.md` a la racine, format « highlights »
      (3-5 puces par version), en tete : `## v1.0.0`.
- [x] **B2** Alimenter v1.0.0 depuis les sources deja ecrites (pas
      d'invention) :
      - `docs/DEVIANCES.md` §2 : seed 426 (§2.1 ordre d'usage), 255 (§2.2
        cycle mutuel U2), 1043 (§2.4 cycle long U1), 1299 (§2.5 jalon
        ingredient/atelier + §2.6 ordre `unlock-recipe` non deterministe),
        1757 (§2.7 gating inerte), 1269 (§2.8 dependance a l'ordre des seeds).
      - `docs/solvabilite.md` : bootstrap guard seed 13, rejoueur
        **1501/1501 victoires** (balayage 0-1500).
      - `docs/nondeterminism.md` : multi-sous-processus `PYTHONHASHSEED`.
- [x] **B3** Ajouter les liens vers `docs/DEVIANCES.md` (détail seed par seed)
      et `docs/solvabilite.md` (preuves chiffrées).
- [x] **B4** References **depuis** `README.md` et `docs/README.md` (index
      References).

Note : la revue parle d'un « parcours de 15 lignes » ; le CHANGELOG doit
rester court et factuel. Le detail reste dans `docs/`.

## Lot C : relecture typos et densite (1 h)

Passe sur `README.md` + les 16 fichiers de `docs/`. Corrections confirmees
lors de la preparation de ce plan :

- [x] **C1 — `docs/solvabilite.md:21` « CALSE un cycle »** → « casse un
      cycle » (le verbe du contexte est bien « casser », pas « calculer »).
- [x] **C2 — `docs/solvabilite.md:80` « ils ne disent rien d'un playlist reel »**
      → « ils ne disent rien d'un parcours reel » (le mot est *playthrough*,
      pas *playlist*).
- [x] **C3 — `docs/tech.md:52` « la quantite n'est jamais demandee »** →
      « demandee » (accords).
- [x] **C4 — NE PAS corriger « gaté »** (14 occurrences : `docs/seed.md`,
      `docs/DEVIANCES.md`, `docs/plan-extracteurs-dispatche.md`,
      `docs/nondeterminism.md`, `docs/developpement.md`). C'est du jargon du
      projet dérivé de *gating* (`late_raws.gated`, section `late_raws`), pas
      la faute « gatée » signalée par la revue. Corriger cassera le
      vocabulaire de `docs/nomenclature-rejoueur.md`.
- [x] **C5 — « ~7 % Mo »** (`README.md:135`) : mesuré sur le témoin local,
      `seed.graph.html` fait **7,2 Mo** (7 487 511 octets). Le `%` est une
      coquille → « ~7,2 Mo ».
- [x] **C6** Balayage des restes (« CALSE », « playlist », doubles espaces,
      accords) sur les autres fichiers, sans toucher au jargon.
- [x] **C7 — Densite** : `docs/solvabilite.md`, `docs/starter.md`,
      `docs/recettes.md` ont des paragraphes de 15 lignes imbriquees.
      Decouper en sous-sections, avec un exemple court en tete de section
      avant le detail. Les docs de reference (`tags.md`,
      `nondeterminism.md`) sont laissees telles quelles.

## Lot D : sortir la table de config du README (30 min)

- [x] **D1** Creer `docs/config.md` : reference complete des sections de
      `config/defaults.yaml` (les 17 sections) + regles de surcharge de
      `config/user.yaml` + schema de validation (type, plage, `min <= max`,
      contraintes croisees) + exemple de surcharge minimal.
- [x] **D2** Dans le README : ne garder que le resume (les 4 sections
      principales : `factorio_version`, `paths`, `map`, `starter`) + un lien
      vers `docs/config.md`. Le README passe de ~19 lignes de table a ~6.
- [x] **D3** Ajouter `docs/config.md` a l'index de `docs/README.md`.

## Lot E : temoin de reproductibilite et release note (1 h)

- [x] **E1** Creer `docs/witness.md` : ce qu'est le temoin, la commande
      (`randputf witness --seed 5 --expect 12ac143e06174df126537b978ff928d3`),
      et le detail de canonisation qui est aujourd'hui noye dans la release
      note : zlib-ng vs zlib, `os.walk` qui suit `os.scandir`, champ « version
      made by » du zip dependant de la plateforme. Reprendre la section
      existante de la release note (source : `/tmp/opencode/RELEASE_v1.0.0.md`
      si toujours presente).
- [x] **E2** Reecrire la release note v1.0.0 selon la structure proposee par
      la revue :
      1. titre « v1.0.0 — Randomizer total deterministe pour Factorio 2.0 »
         (le « randputF v1.0.0 » fait doublon avec le nom du repo) ;
      2. ~10 lignes : ce que c'est, ce que ca garantit ;
      3. « Determinisme verifiable » : commande witness + hash (**a garder,
         c'est la partie la plus forte**) ;
      4. « Garanties mesurees » : 1501/1501, invariants §15 ;
      5. installation ;
      6. lien vers `docs/witness.md` pour le detail.
- [x] **E3** Ajouter ~15 lignes sur le **chemin parcouru** dans la release note
      (la revue signale que le squash a efface la preuve de methode) :
      bootstrap guard seed 13, cycles d'hebergement 255/1043, ordre
      `unlock-recipe` 1299, dependance a l'ordre des seeds 1269, jalons de
      ressources tardives. Sources : `docs/DEVIANCES.md`.
- [x] **E4** La release note est sur GitHub (objet `gh release edit`) :
      c'est une action du mainteneur, pas un fichier du depot. Ne pas publier
      automatiquement.

## Lot F : divergences doc/code detectees (45 min)

Constate en preparant ce plan (preexistant a la migration config, present
aussi sur `master` `f94f471`).

- [x] **F1 — `bootstrap_guard` n'est plus execute par le pipeline.**
      `tool/generator/bootstrap_guard.py` existe et n'est appele que par les
      tests (`tests/test_bootstrap_guard.py`,
      `tests/test_pipeline_invariants.py:834,860`). Aucun appel dans
      `tool/generator/pipeline.py`. Or :
      - `docs/solvabilite.md:18` le decrit comme « une phase de cloture
        (bootstrap_guard, AFTER toutes les phases productrices) » ;
      - `docs/solvabilite.md:74-75` renvoie a une section de config
        `bootstrap_guard` (`enabled`, `prefix`, `ingredient_min/max`,
        `max_iterations`, `replace_first`) **qui n'existe pas** dans
        `config/defaults.yaml` et n'est lue par aucun code.
      - `docs/PLAN_bootstrap_inline.md` prevoyait justement de le supprimer
        (« Suppression du reparateur »), et `config/defaults.yaml` ne contient
        pas la section.
      → **Decider** (ordre suggere) : soit supprimer le module + ses tests et
      mettre la doc a jour, soit le re-integrer au pipeline et ajouter la
      section config. Le plan `PLAN_bootstrap_inline.md` va dans le premier
      sens ; la doc et le code divergent depuis.
- [x] **F2** Verifier que les autres docs ne decrivent pas de sections de
      config inexistantes (meme controle que F1 sur les 17 sections).
- [x] **F3 — Table de config du README** : decider si elle reste (voir Lot D)
      et verifier que chaque section citee existe dans `defaults.yaml`.

## Lot G : doc de conception du graphe interactif (45 min)

La revue identifie le **dernier angle mort de couverture** : `seed.graph.html`
est bien decrit cote utilisateur (README « Le graphe interactif »), mais son
*comment* (generation autonome, icones base64, structure du graphe) n'a pas de
section de conception. `docs/architecture.md:156-158` affirme explicitement le
contraire (« c'est une sortie joueur, pas une piece de conception ») : c'est
un choix a remettre en cause, pas une erreur de la revue.

- [x] **G1** Ecrire `docs/graphe-interactif.md` : pipeline d'export
      (`tool/exporters/seed_graph.py`), graphe produit→ingredient→produit,
      encodage base64 des icones, choix d'auto-suffisance du HTML, navigation
      et sous-graphes, determinisme de la sortie.
- [x] **G2**.decider si `docs/architecture.md:156-158` est remplace par un
      renvoi vers ce document.
- [x] **G3** Indexer le document dans `docs/README.md`.

## Lot H : separer le chantier de la release (30 min)

- [x] **H1** `docs/developpement.md` est un doc de dev mais reference depuis la
      release ; il contient des notes de chantier (la roadmap point 3 est un
      pave avec du vecu). Extraire les notes de chantier vers `IDEES.md` ou
      `docs/DEVIANCES.md`, ne garder que l'environnement de dev et la
      roadmap dans `developpement.md`.
- [x] **H2** Verifier que la release note ne renvoie plus a du contenu de
      chantier.

## Lot I : visibilite internationale (2-3 h)

- [x] **I1 — README EN** (ou badge « Documentation : FR | EN a venir » en attendant).
      Le public Factorio est massivement anglophone. C'est le verrou a lever
      pour une visibilite au-dela du cercle proche.
- [x] **I2** Badge licence en tete de README (MIT, deja en section Licence
      ligne 241).
- [ ] **I3** Le titre du repo (`randputF`) et la description GitHub meritent
      d'aligner le nom de produit sur « randomizer total deterministe ».

## Lot J : supports visuels (1 h)

- [ ] **J1** Generer une seed de showcase (gisement, kit de depart, graphe) et
      produire 3-5 captures : (a) la surface avec les gisements, (b) le kit de
      depart, (c) `seed.graph.html` ouvert.
- [ ] **J2** GIF de 15 s d'une generation (README + release note).
- [ ] **J3** Verifier les droits : icones vanilla (Factorio est moddable, les
      assets du jeu sont utilisables par les mods) → OK pour un mod, a
      confirmer pour un repo public.

## Lot K : wiki (optionnel, non prioritaire)

- [ ] **K1** La revue conclut qu'un wiki serait un **downgrade** (doc non
      versionnee, pas de review, pas d'offline, liens profonds fragiles). La
      feuille de route **ne prevoit pas** de wiki. Si un jour il en faut un :
      uniquement un guide joueur illustre (screenshots, exemples de seeds),
      le contenu visuel leger que personne n'aurait besoin de versionner.

---

## Ordre d'execution

1. **A** (5 min, aucun risque, gain de perception immediat)
2. **B** (CHANGELOG : restaure la preuve de methode, fort impact)
3. **C** (relecture : le detail le plus manuel, fait en un seul passage)
4. **F** (divergences doc/code : a traiter avant E pour ne pas documenter une
   phase fantome dans `witness.md`)
5. **D** (alléger le README)
6. **E** (`witness.md` + release note)
7. **G** (couverture du graphe)
8. **H** (separer chantier/release)
9. **I** (README EN, gros volume mais mecanique)
10. **J** (visuels, depend d'une seed de showcase stable)

## Regles

- Aucun push sans decision explicite du mainteneur.
- Chaque lot = un ou plusieurs commits `1.0.0 : ...` sur `dev`.
- Un doc modifie qui decrit un comportement du code doit cite `file.py:ligne`.
- Le jargon du projet (« gaté », « randput », « watershed », « bootstrap »)
  n'est pas une typo (cf. C4).
- Le determinisme est intouchable : le temoin seed 5 doit rester
  `12ac143e06174df126537b978ff928d3` (verifie par `.github/workflows/ci.yml`).
  Aucun lot de ce plan ne doit le modifier (lots A-J : documentation seule).