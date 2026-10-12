# La chaleur

Partie de la doc de conception randputF. Retour : [docs/README.md](README.md).

## La chaleur

La chaleur est un milieu transportable **à la manière d'un fluide**, mais qui
ne circule qu'entre les bâtiments capables de l'échanger. Rien n'est codé en
dur : la détection se fait **par capacités** (tags `is_heat_source`,
`is_heat_sink`, `is_heat_transport`), comme les autres familles de bâtiments
([tags.md](tags.md#modèle--chaleur--producteur--transport--consommateur)). En vanilla :

- **SOURCE** (`is_heat_source`) : *nuclear-reactor* — energy burner +
  `has_heat_output`. C'est lui qui **produit** la chaleur.
- **TRANSPORT** (`is_heat_transport`) : *heat-pipe* — la fait circuler entre
  la source et les consommateurs.
- **CONSOMMATEUR / SINK** (`is_heat_sink`) : *heat-exchanger* — energy_source
  `'heat'`. Il **demande** la chaleur pour convertir son fluide d'entrée en
  son fluide de sortie (sa recette fluide→fluide, [ressources.md](ressources.md)
  / [energie.md](energie.md#lélectricité)). En jeu, il ne fonctionne **QUE raccordé**
  à une source via des conduites (réseau de chaleur réel, `energy_source 'heat'`
  vanilla).

**Garantie de la triade — « à la volée » ([recettes.md](recettes.md#la-phase-récursive))** :
comme la garantie « extracteur avant besoin » du starter ([starter.md](starter.md)
), un consommateur de chaleur ne doit **jamais** être débloqué avant sa source
+ son transport — sinon l'échangeur réclamerait du heat réseau sans aucun moyen
d'en produire ni de le transporter (suite infaisable).
`recursive_phase._ensure_heat_prereq` pose la garantie au premier instant où un
sink reçoit sa recette de craft : il débloque, dans des techs **isolées
strictement antérieures**, la SOURCE et le TRANSPORT manquants (une source déjà
débloquée plus tôt n'est pas rejouée). Le pool **sans consommateur** rend le
modèle parfaitement **inerte** : aucune contrainte, aucun unlock ajouté.

Le réacteur (source) est alimenté en **combustible générique** (fuel categories
unifiées, [runtime.md](runtime.md#catégories-de-combustible-unifiées)) : aucune chaîne uranium dédiée, la
suite reste faisable.

## Lectures associées

- **Parent** : [energie.md](energie.md) — la chaleur est le second réseau de l'électricité.
- **Concepts liés** : [tags.md](tags.md#modèle--chaleur--producteur--transport--consommateur) (tags de rôle chaleur) ;
  [ressources.md](ressources.md#les-ressources-au-sol) / [runtime.md](runtime.md#fluides-génériques) (fluides
  génériques) ; [recettes.md](recettes.md#la-phase-récursive) (`_ensure_heat_prereq`) ;
  [vanilladb.md](vanilladb.md#tags-énergétiques--chaleur) (tags énergétiques & chaleur).
