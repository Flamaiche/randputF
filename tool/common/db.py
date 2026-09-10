"""Base de donnees normalisee du contenu vanilla.

Schema intermediaire entre le dump brut du jeu et le moteur de tirage.
Chaque bâtiment y est decrit par type fonctionnel, slots in/out types
et directives (possibilites), conformement au README §5.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SLOT_ITEM = "item"
SLOT_FLUID = "fluid"
SLOT_FUEL = "fuel"
SLOT_ENERGY = "energy"

# Ressources non automatisables (README §3, §6 et §9.3) : récoltées à la main
# depuis des entités du monde (arbres -> wood, rochers -> stone, poissons ->
# raw-fish). Elles ne constituent JAMAIS un patch, demeurent disponibles dès
# le départ comme pool environnemental de base (ingrédients des premiers
# crafts), et restent des ingrédients possibles des recettes randomisées.
ENVIRONMENTAL_ITEMS = frozenset({"wood", "stone", "raw-fish"})

# Catégories de crafting valides (un bâtiment qui en possède une est un
# ATELIER GÉNÉRAL multi-recettes, pas un fabricateur à recette fixe). La liste
# est partagée ici (et non dans recipes.py) pour éviter tout cycle d'import
# avec les parsers : la détection du tag ``has_hidden_recipe`` (vanilla.py)
# et le moteur de tirage (recipes.py) s'appuient sur la même source.
VALID_RECIPE_CATEGORIES = frozenset({
    "crafting",
    "basic-crafting",
    "advanced-crafting",
    "smelting",
    "chemistry",
    "crafting-with-fluid",
    "oil-processing",
    "rocket-building",
    "centrifuging",
})


# Les TAGS de bâtiment qui POSSÈDENT une production propre (« ont une
# recette ») : ils transforment une entrée en une sortie — fluide, item,
# énergie, ressource ou recherche. Les « distribution » (pylônes) et « other »
# ne produisent rien : ils ne sont jamais des fabricateurs à recette fixe.
PRODUCING_TAGS = ("is_research", "is_crafter", "is_generator", "is_extractor")


def has_hidden_recipe(b: "BuildingDef") -> bool:
    """Détecte les bâtiments porteurs d'une RECETTE CACHÉE : une production
    codée en dur = une VRAIE recette, mais non accessible comme recette de
    craft AVANT la transformation du mod. Détecté PAR CAPACITÉS (aucune liste
    de noms) :

      * un tag PRODUCTEUR (``is_research``, ``is_crafter``, ``is_generator``,
        ``is_extractor`` — le bâtiment « produit » quelque chose) ;
      * une ENTRÉE — item, fluide OU combustible (fuel = pseudo-ingrédient :
        sans combustible la machine ne tourne pas) ; la SORTIE, elle, reste
        item/fluide : slots (''item_output_slots''/''fluid_outputs'') OU items
        résiduels de combustion (''fuel_residues'', burnt_result) — jamais
        électricité/chaleur/ressource/recherche (autres mécanismes, traités
        séparément) ;
      * AUCUNE catégorie de crafting valide : cette recette n'est pas
        accessible — ce n'est PAS un atelier général multi-recettes.

    En vanilla cela revient à boiler/heat-exchanger (fluide → fluide) ET au
    nuclear-reactor : il consomme un ITEM quelconque comme pseudo-combustible
    et produit un ITEM en résidu (depleted-uranium-fuel-cell) — une recette
    cachée item → item. Sa CHALEUR (``produces_heat``) et l'électricité de ses
    pairs sont des sorties non-recettables, traitées plus tard : le réacteur
    est donc RÉVÉLÉ (jamais un atelier, aucun fake crafted_in — générateur,
    ``is_fixed_crafter`` est restreint aux ateliers ``is_crafter``). Les
    générateurs/extracteurs/lab restants (soleil/combustible → électricité,
    champ → ressource, packs → recherche : pas de sortie item/fluide) n'ont
    PAS cette signature — mécanique moteur, jamais taggés. Les ateliers
    généraux (furnaces, AM, refinery, chemical-plant, silo) ne sont pas
    tagués (catégorie valide).

    ``is_fixed_crafter`` / ``is_fixed_fluid_crafter`` restreignent ce tag au
    sous-ensemble qui reçoit réellement une recette randomisée (atelier
    ``is_crafter`` à sortie item OU fluide)."""
    if not any(getattr(b, tag, False) for tag in PRODUCING_TAGS):
        return False
    has_atelier_category = any(
        c in VALID_RECIPE_CATEGORIES for c in getattr(b, "crafting_categories", ())
    )
    if has_atelier_category:
        return False
    has_input = (
        getattr(b, "item_input_slots", 0) > 0
        or getattr(b, "fluid_inputs", 0) > 0
        or bool(getattr(b, "fuel_categories", ()))
    )
    has_output = (
        getattr(b, "item_output_slots", 0) > 0
        or getattr(b, "fluid_outputs", 0) > 0
        or bool(getattr(b, "fuel_residues", ()))
    )
    return has_input and has_output


def is_fixed_fluid_crafter(b: "BuildingDef") -> bool:
    """Sous-ensemble de ``has_hidden_recipe`` sur lequel le générateur
    crée UNE recette « fluide → fluide » randomisée (IDEES C7) : un
    atelier ``is_crafter`` produisant un fluide avec une entrée fluide. En
    vanilla : boiler et heat-exchanger uniquement. Les autres bâtiments à
    recette fixe (générateurs, extracteurs, lab) gardent leur comportement
    figé — on ne leur invente jamais de recette de craft (fake
    ``crafted_in``)."""
    return (
        has_hidden_recipe(b)
        and getattr(b, "is_crafter", False)
        and getattr(b, "fluid_inputs", 0) > 0
        and getattr(b, "fluid_outputs", 0) > 0
    )


def is_fixed_crafter(b: "BuildingDef") -> bool:
    """Un bâtiment à recette FIXE qui peut HÉBERGER une recette de craft :
    atelier ``is_crafter`` taggé produisant une sortie (fluide OU item), OU
    un combusteur à résidu (``fuel_residues`` non vide) — le réacteur nucléaire
    produit depleted-uranium-fuel-cell en résidu : c'est sa sortie item
    recevable. Sur CE sous-ensemble le générateur crée sa recette randomisée
    (« fluide → fluid » comme boiler/heat-exchanger, « item → item » pour le
    réacteur ou un équivalent de mod). Les générateurs/extracteurs/lab (chaleur,
    électricité, ressource, recherche = pas de sortie recette) restent exclus."""
    return (
        has_hidden_recipe(b)
        and (
            (getattr(b, "is_crafter", False) and (
                getattr(b, "fluid_outputs", 0) > 0
                or getattr(b, "item_output_slots", 0) > 0
            ))
            or bool(getattr(b, "fuel_residues", ()))
        )
    )

# La chaîne fusée (les 3 ingrédients de ``rocket-part``, recette vanilla
# exempte §14). Elle est réservée à la fin de partie : aucune autre phase (en
# particulier l'électricité, qui pioche des combustibles) ne doit la débloquer
# en avance. Shared ici (et non dans endgame_phase) pour éviter tout cycle
# d'import entre generators.
ROCKET_CHAIN = frozenset({"processing-unit", "low-density-structure", "rocket-fuel"})

# Les VRAIS pylônes (poteaux électriques) sont désormais taggés
# ``BuildingDef.is_power_pole`` (vanilla.py) — le beacon est une distribution
# mais PAS un pylône (il ne transporte pas le courant, §9.1/§10). La cadence
# garantie et le starter ne débloquent que ceux-ci.

# Armes MONTÉES sur des entités (chars, véhicules, artillerie, spidertron) :
# dans le dump vanilla leur type est « gun », donc is_gun=True, mais elles ne
# sont PAS utilisables à pied par le personnage — les randomiser comme armes
# de poing (kit de départ, combat) produit du contenu mort / trompeur
# (ex. spidertron-rocket-launcher sans spidertron). Elles restent exclues du
# pool d'armes « de poing » et du balayage de couverture §9.6. Depuis la
# randomisation des véhicules (§7/§12.1), la pool RecursiveConfig.vehicle_weapons
# peut contenter ces items MONTÉS-UNIQUEMENT : jamais craftés, ils ne servent
# que de source à un clone monté sur le véhicule (§12.1) — les items legacy
# (tank-machine-gun, spidertron-rocket-launcher-2/3/4, identiques à -1) sont
# du contenu mort : jamais tirés, jamais unlockés.
VEHICLE_GUNS = frozenset(
    {
        "tank-cannon",
        "tank-machine-gun",
        "tank-flamethrower",
        "vehicle-machine-gun",
        "artillery-wagon-cannon",
        "spidertron-rocket-launcher-1",
        "spidertron-rocket-launcher-2",
        "spidertron-rocket-launcher-3",
        "spidertron-rocket-launcher-4",
    }
)

# Types d'items non-empilables (stack_size = 1 dans Factorio vanilla 2.0) :
# une recette ne peut en produire/consommer que 1 exemplaire. Fallback quand
# le dump n'emporte pas stack_size (type conservateur : clamper davantage ne
# casse rien, rater un item non-stackable fait crasher le chargement).
# NB : "tool" (science packs !) et "module"/"ammo" sont stackables et donc
# volontairement absents.
NON_STACKABLE_ITEM_TYPES = frozenset(
    {
        "gun",
        "armor",
        "item-with-entity-data",  # véhicules, wagons, locomotive
        "capsule",  # grenades, remotes, raw-fish — certains sont stack 1
        "repair-tool",
        "mining-tool",
        "selection-tool",
        "copy-paste-tool",
        "blueprint",
        "blueprint-book",
        "deconstruction-item",
        "upgrade-item",
        "rail-planner",
        "spidertron-remote",
    }
)


@dataclass(frozen=True)
class ItemDef:
    name: str
    subgroup: str = ""
    place_result: str | None = None
    fuel_value: float | None = None
    is_ammo: bool = False
    is_gun: bool = False
    is_armor: bool = False
    is_science_pack: bool = False
    is_tool: bool = False
    ammo_category: str = ""
    # Type brut du dump (source de vérité : "item", "gun", "armor",
    # "item-with-entity-data", "capsule", "tool", ...).
    item_type: str = ""
    # Combustible : categorie de fuel (brûlable dans les brûleurs qui la
    # listent dans leurs ``fuel_categories``) et RESIDU de combustion — l'item
    # produit quand le combustible est brûlé. Ce résidu est la SORTIE recevable
    # (item) d'un générateur à combustible (ex. réacteur :
    # uranium-fuel-cell → depleted-uranium-fuel-cell). Champ rempli quand le
    # dump a été régénéré avec l'exporter (exporter/control.lua) ; sinon vide.
    fuel_category: str = ""
    burnt_result: str | None = None
    # Stack size réel (0 = inconnu : dump non régénéré). Quand il est connu,
    # il fait foi ; sinon on déduit la stackabilité du type (voir
    # is_stackable).
    stack_size: int = 0
    # --- Tags §9 : items (docs/tags.md §12) ---
    is_environmental: bool = False    # récolté à la main (wood/stone/raw-fish)
    is_virtual_item: bool = False     # blueprint/planner/remote (non fabricable)
    is_module: bool = False           # module d'assemblage
    is_capsule_throwable: bool = False  # capsule lançable (grenades, remotes)

    @property
    def is_handheld_gun(self) -> bool:
        """Arme utilisable à pied (hors armes montées sur véhicule/spidertron)."""
        return self.is_gun and self.name not in VEHICLE_GUNS

    @property
    def is_stackable(self) -> bool:
        """Un item est-il empilable (stack_size > 1) ? Factorio refuse qu'une
        recette produise/consomme plus de 1 exemplaire d'un item non-stackable
        (armure, arme à feu, véhicule, télécommande...) — erreur de chargement
        « not stackable but has a max count of N ». ``stack_size`` réel du dump
        fait foi quand il est fourni ; sinon on se rabat sur le type (les
        types non-stackables sont connus : gun, armor, item-with-entity-data,
        capsules/remotes, outils de planification)."""
        if self.stack_size:
            return self.stack_size > 1
        return self.item_type not in NON_STACKABLE_ITEM_TYPES


@dataclass(frozen=True)
class FluidDef:
    """Un fluide est identifie par son nom uniquement (README §6) :
    la temperature n'est pas une dimension, elle n'existe pas ici."""

    name: str
    fuel_value: float | None = None


@dataclass
class BuildingDef:
    """Un bâtiment est décrit par des TAGS orthogonaux cumulables : il peut être
    à la fois atelier (``is_crafter``), générateur (``is_generator``) et
    producteur de chaleur (``produces_heat``) — plus aucune classification
    exclusive. `equivalent_functional_type` (vanilla.py) peut RECONSTRUIRE
    l'ancien type exclusif pour vérification, mais la logique ne repose plus
    que sur les tags."""

    name: str
    entity_type: str
    medium: str = ""
    # Tags de rôle fonctionnel (cumulables) — ils remplacent l'ancien
    # ``functional_type`` exclusif (research/transformer/generator/distribution/
    # extractor/other).
    is_research: bool = False          # lab : packs -> recherche
    is_crafter: bool = False           # atelier à sortie item/fluide (transformer)
    is_generator: bool = False         # producteur d'énergie (électrique ou chaleur)
    is_distribution: bool = False      # pylône / infrastructure de transport d'énergie
    is_extractor: bool = False         # ressource de l'environnement -> item/fluide
    is_other: bool = False             # ni producteur ni distributeur (backup)
    # Capacités brutes extraites du dump (champ, crafting, fluides...).
    has_crafting: bool = False
    has_mining: bool = False
    has_pumping: bool = False
    has_fluid_input: bool = False
    has_fluid_output: bool = False
    has_fuel: bool = False
    has_target_temperature: bool = False
    has_rocket_parts: bool = False
    crafting_categories: tuple[str, ...] = ()
    resource_categories: tuple[str, ...] = ()
    energy_type: str = "burner"
    fuel_categories: tuple[str, ...] = ()
    item_input_slots: int = 0
    fluid_inputs: int = 0
    fluid_outputs: int = 0
    item_output_slots: int = 0
    pumped_fluid: str | None = None
    # Sorties « spéciales », NON recettables (jamais des produits de recette de
    # craft) — TAGS ORTHOGONAUX qui se cumulent : une machine peut être à la
    # fois consommatrice de combustible, productrice de chaleur et productrice
    # de courant. ``produces_electricity`` = VRAI producteur de courant
    # (steam-engine, turbine, burner-generator, solar-panel) ; ``produces_heat``
    # = producteur de chaleur (nuclear-reactor). Le réacteur produit de la
    # chaleur (+ son résidu de combustible), PAS de l'électricité : il est donc
    # écarté de l'électricité PAR CAPACITÉS, sans liste de noms. ``has_hidden_recipe``
    # ne compte jamais ces sorties — leur traitement viendra plus tard.
    produces_heat: bool = False
    produces_electricity: bool = False
    # Items résiduels de combustion (les ``burnt_result`` des combustibles du
    # bâtiment INSCRITS APRÈS LE PARSE — ils dépendent de la base items, pas du
    # seul bâtiment). Ce sont des SORTIES item RECEVABLES : ex. le réacteur
    # produit depleted-uranium-fuel-cell. ``has_hidden_recipe`` les compte comme
    # sortie → un combusteur à résidu est une recette cachée item → item
    # (entrée = un item quelconque, pseudo-combustible).
    fuel_residues: frozenset[str] = frozenset()
    directives: dict = field(default_factory=dict)
    # Tag « fabricateur à recette cachée » détecté par capacités au chargement
    # du dump (boiler/heat-exchanger et tout équivalent de mod). L'arbre de
    # tech s'appuie sur ce tag pour soustraire ces bâtiments du pool des
    # ateliers et assigner une recette fixe aux transformateurs (IDEES C7).
    has_hidden_recipe: bool = False
    # --- Tags §1 : raffinement des rôles (docs/tags.md §1.1) ---
    is_power_pole: bool = False       # poteau électrique (type electric-pole + supply_area)
    is_beacon: bool = False           # module de transmission d'effet (type beacon)
    is_accumulator: bool = False      # stockeur d'énergie (type accumulator)
    is_energy_storage: bool = False   # stockage d'énergie (buffer_capacity > 0, pas de prod)
    is_offgrid: bool = False          # producteur hors réseau (solaire, burner-generator)
    consumes_electricity: bool = False  # consomme du courant (energy_source.type == 'electric')
    is_water_extractor: bool = False  # extracteur d'eau (medium == 'water')
    is_fluid_extractor: bool = False  # extracteur de fluide brut (medium == 'fluid')
    is_ground_extractor: bool = False # extracteur de minerai solide (medium == 'ground')
    # --- Tags §2 : logistique & transports (docs/tags.md §2) ---
    is_belt: bool = False             # transport-belt
    is_underground_belt: bool = False # belt sous-terrain
    is_splitter: bool = False         # séparateur de flux
    is_inserter: bool = False         # bras articulé
    is_pipe: bool = False             # tube de fluide
    is_pipe_to_ground: bool = False   # tube sous-terrain
    is_fluid_transport: bool = False  # union pipe + pipe-to-ground
    is_chest: bool = False            # stockage d'items (container)
    is_logistics_chest: bool = False  # poitrine logistique (logistic-container)
    is_storage: bool = False          # union chest + logistics-chest
    is_roboport: bool = False         # dock des robots
    is_robot: bool = False            # robot logistique ou de construction
    # --- Tags §3 : train & véhicules (docs/tags.md §3) ---
    is_rail: bool = False             # voie (droite/courbe/surélevée)
    is_rail_support: bool = False     # rampes/piliers (rail-support, dummies)
    is_rail_signal: bool = False      # signal/chain
    is_train_stop: bool = False       # gare
    is_locomotive: bool = False       # loco
    is_wagon: bool = False            # wagon cargo/fluide/artillerie
    is_vehicle: bool = False          # tous véhicules
    is_spider_vehicle: bool = False   # spider (spidertron)
    # --- Tags §4 : production spécialisée (docs/tags.md §4) ---
    is_furnace: bool = False          # four (smelting)
    is_assembler: bool = False        # machine d'assemblage
    is_chemical_plant: bool = False   # usine chimique
    is_refinery: bool = False         # raffinerie (oil-processing)
    is_centrifuge: bool = False       # centrifugeuse
    is_rocket_parts_crafter: bool = False  # silo à fusée
    # --- Tags §5 : énergie & chaleur (docs/tags.md §5) ---
    is_boiler: bool = False           # chaudière (type boiler, énergie burner)
    is_heat_exchanger: bool = False   # échangeur (type boiler, énergie heat)
    is_solar: bool = False            # panneau solaire
    is_reactor: bool = False          # réacteur nucléaire
    is_heat_transport: bool = False   # pipe de chaleur
    # --- Tags §5bis : modèle « chaleur » (docs/tags.md §5) ---
    # ``is_heat_source`` PRODUIT la chaleur (réacteur vanilla : energy burner +
    # has_heat_output). ``is_heat_sink`` la DEMANDE (échangeur : energy_source
    # type 'heat'). ``produces_heat`` est restreint à la SOURCE (moins pur que
    # l'ancien has_heat_output qui ratissait aussi la heat-pipe et l'échangeur).
    is_heat_source: bool = False      # producteur de chaleur (ex. nuclear-reactor)
    is_heat_sink: bool = False        # consommateur de chaleur (ex. heat-exchanger)
    is_burner_generator: bool = False # générateur brûleur
    # --- Tags §6 : extraction (docs/tags.md §6) ---
    is_mining_drill: bool = False     # foreuse de minerai
    is_pumpjack: bool = False         # pompe à pétrole
    is_offshore_pump: bool = False    # pompe d'eau
    is_well_pump: bool = False        # pompe de fluide brut
    # --- Tags §7 : combat & défense (docs/tags.md §10) ---
    is_turret: bool = False           # union des 4 familles de tourelles
    is_gun_turret: bool = False       # tourelle balistique (ammo-turret)
    is_laser_turret: bool = False     # tourelle laser (electric-turret — consomme le réseau)
    is_flame_turret: bool = False     # tourelle à flamme (fluid-turret)
    is_artillery: bool = False        # artillerie longue portée (artillery-turret)
    is_defensive_wall: bool = False   # muraille / porte
    is_landmine: bool = False         # mine
    is_combat_robot: bool = False     # robot de combat (destroyer/defender/distractor)
    # --- Tags §8 : signal-réseau & électronique (docs/tags.md §11) ---
    is_circuit_combinator: bool = False  # combinator de calcul (arithmetic/decider/selector)
    is_constant_combinator: bool = False # émetteur constant
    is_circuit_io: bool = False          # tout entité réseau circuits (combinators + speaker/display/switch)
    is_rgb_lamp: bool = False            # lampe / éclairage
    is_radar: bool = False               # radar / cartographie


@dataclass
class RecipeRef:
    name: str
    category: str = ""
    ingredients: tuple = ()
    products: tuple = ()
    energy: float = 0.5


@dataclass
class VanillaDB:
    seed_value: int = 0
    items: dict[str, ItemDef] = field(default_factory=dict)
    fluids: dict[str, FluidDef] = field(default_factory=dict)
    buildings: dict[str, BuildingDef] = field(default_factory=dict)
    recipes: dict[str, RecipeRef] = field(default_factory=dict)
    # Bac a rien-decide : items/fluides ecartes des pools (junk) et entites
    # sans capacite reconnue. Conserve pour requalification ulterieure.
    excluded_items: dict[str, dict] = field(default_factory=dict)
    excluded_fluids: dict[str, dict] = field(default_factory=dict)

    def beltable_items(self) -> list[ItemDef]:
        return sorted(
            (i for i in self.items.values() if not i.is_tool),
            key=lambda i: i.name,
        )

    def pipable_fluids(self) -> list[FluidDef]:
        return sorted(self.fluids.values(), key=lambda f: f.name)

    @property
    def extraction_only_fluids(self) -> frozenset[str]:
        """Fluides sans recette de production DIRECTE : l'eau (offshore-pump),
        le pétrole brut (pumpjack) et la vapeur (chaudière). Le
        barillage/débarillage est un cycle (fluide → baril → fluide), pas une
        production : on ignore les recettes dont le nom contient "barrel". Ces
        fluides sont des RESSOURCES BRUTES (README §3) : extraites de
        l'environnement, jamais craftées — infinies ou non."""
        produced = {
            p[1]
            for r in self.recipes.values()
            if "barrel" not in r.name
            for p in r.products
            if p[0] == SLOT_FLUID
        }
        return frozenset(name for name in self.fluids if name not in produced)

    def raw_resources(self, patch_resources: set[str]) -> frozenset[str]:
        """Ressources « brutes » d'une seed (README §3) : patches posés au sol
        (fini), items environnementaux récoltables à la main (arbres/rochers/
        poissons) et fluides d'extraction (eau/pétrole brut/vapeur — infinis
        ou non). Un science pack ne doit JAMAIS être crafté avec une ressource
        brute (§13) : exclue en génération (forbidden) et vérifiée par
        pipeline_validator."""
        return frozenset(patch_resources) | set(ENVIRONMENTAL_ITEMS) | self.extraction_only_fluids

    def fuel_items(self) -> list[ItemDef]:
        return sorted(
            (i for i in self.items.values() if i.fuel_value),
            key=lambda i: i.name,
        )

    def fuels_for(self, b: "BuildingDef") -> list[ItemDef]:
        """Les combustibles qu'un bâtiment PEUT brûler : items avec fuel_value
        dont la catégorie de fuel appartient aux ``fuel_categories`` du
        bâtiment. Un brûleur ne tourne qu'avec du combustible (pseudo-ingrédient
        d'entrée §6) — la correspondance se fait PAR CATÉGORIE, rien en dur."""
        if not getattr(b, "fuel_categories", ()):
            return []
        accepted = set(b.fuel_categories)
        return sorted(
            (i for i in self.items.values()
             if i.fuel_value and (i.fuel_category or "") in accepted),
            key=lambda i: i.name,
        )

    def fuel_residues(self, b: "BuildingDef") -> frozenset[str]:
        """Les SORTIES recevables (items) issues de la combustion : le résidu
        de chaque combustible du bâtiment (``burnt_result``). Pour le réacteur
        (categorie "nuclear") : depleted-uranium-fuel-cell — c'est SA sortie
        item. Vide si le dump n'a pas été régénéré (champs absents de
        vanilla_dump.json)."""
        return frozenset(
            i.burnt_result for i in self.fuels_for(b) if i.burnt_result
        )

    def fuel_item_flow(self, b: "BuildingDef") -> dict:
        """Vue NORMALISÉE d'une machine à combustible (TAG générique) : entrée
        = UN ITEM QUELCONQUE en pseudo-combustible (aucune référence à une
        catégorie type « nuclear »), sorties = les items résiduels de
        combustion (``burnt_result``). La machine devient ainsi simplement
        item → item (combustible → résidu) — plus simple et plus malléable
        pour la suite (chaleur/électricité traitées séparément).
        Exemple : nuclear-reactor → {"input": "item", "outputs":
        {"depleted-uranium-fuel-cell"}}."""
        return {
            "input": "item" if bool(getattr(b, "fuel_categories", ())) else None,
            "outputs": self.fuel_residues(b) or frozenset(),
        }

    def has_fuel_item_flow(self, b: "BuildingDef") -> bool:
        """Un combusteur produit-il un RÉSIDU item ? Entrée item (combustible)
        générique ET sortie item (résidu) : c'est une vraie transformation
        item → item, indépendante de toute catégorie de fuel (nuclear, ...)."""
        flow = self.fuel_item_flow(b)
        return flow["input"] is not None and bool(flow["outputs"])

    def fuel_fluids(self) -> list[FluidDef]:
        return sorted(
            (f for f in self.fluids.values() if f.fuel_value),
            key=lambda f: f.name,
        )

    def buildings_with_tag(self, tag: str) -> list[BuildingDef]:
        """Tous les bâtiments portant un TAG donné (``is_crafter``,
        ``is_generator``, ...). Un bâtiment multi-tags apparaît dans CHAQUE
        catégorie qu'il porte."""
        return sorted(
            (b for b in self.buildings.values() if getattr(b, tag, False)),
            key=lambda b: b.name,
        )

    def extractors_for_medium(self, medium: str) -> list[BuildingDef]:
        return sorted(
            (
                b
                for b in self.buildings.values()
                if b.is_extractor and (not medium or b.medium == medium)
            ),
            key=lambda b: b.name,
        )
