"""Base de donnees normalisee du contenu vanilla.

Schema intermediaire entre le dump brut du jeu et le moteur de tirage.
Chaque bâtiment y est decrit par type fonctionnel, slots in/out types
et directives (possibilites).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Ensembles de noms figés : définis UNIQUEMENT dans tool/common/tagsets.py
# (source unique, docs/tags.md §14). Re-exportés ici pour ne rien casser chez
# les consommateurs historiques (``from tool.common.db import ...``).
from tool.common.tagsets import (
    ENVIRONMENTAL_ITEMS,          # noqa: F401
    NON_STACKABLE_ITEM_TYPES,     # noqa: F401
    ROCKET_CHAIN,                 # noqa: F401
    VALID_RECIPE_CATEGORIES,      # noqa: F401
    VEHICLE_GUNS,                 # noqa: F401
)

SLOT_ITEM = "item"
SLOT_FLUID = "fluid"
SLOT_FUEL = "fuel"
SLOT_ENERGY = "energy"


# TAGS de bâtiment qui possèdent une production propre (« ont une recette ») :
# ils transforment une entrée en une sortie. Les « distribution » (pylônes) et
# « other » ne produisent rien : jamais des fabricateurs à recette fixe.
PRODUCING_TAGS = ("is_research", "is_crafter", "is_generator", "is_extractor")


def has_hidden_recipe(b: "BuildingDef") -> bool:
    """Bâtiment porteur d'une RECETTE CACHÉE : production codée en dur, non
    accessible comme recette de craft avant la transformation du mod.
    Détection PAR CAPACITÉS (aucune liste de noms) :
      * un tag PRODUCTEUR (``is_research``, ``is_crafter``, ``is_generator``,
        ``is_extractor``) ;
      * une ENTRÉE — item, fluide OU combustible (fuel = pseudo-ingrédient) ;
        la SORTIE reste item/fluide : slots (''item_output_slots''/
        ''fluid_outputs'') OU items résiduels de combustion
        (''fuel_residues'', burnt_result) — jamais électricité/chaleur/
        ressource/recherche ;
      * AUCUNE catégorie de crafting valide (pas un atelier multi-recettes).

    En vanilla : boiler/heat-exchanger (fluide → fluide) et nuclear-reactor
    (item → résidu item). Sa chaleur et l'électricité de ses pairs sont des
    sorties non-recettables : le réacteur est RÉVÉLÉ. Les générateurs/
    extracteurs/lab restants n'ont pas cette signature.

    ``is_fixed_crafter`` / ``is_fixed_fluid_crafter`` restreignent au
    sous-ensemble qui reçoit réellement une recette randomisée."""
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
    """Sous-ensemble de ``has_hidden_recipe`` pour lequel le générateur crée
    UNE recette « fluide → fluide » randomisée : atelier ``is_crafter`` à
    entrée et sortie fluides. En vanilla : boiler et heat-exchanger. Les
    autres bâtiments à recette fixe gardent leur comportement figé."""
    return (
        has_hidden_recipe(b)
        and getattr(b, "is_crafter", False)
        and getattr(b, "fluid_inputs", 0) > 0
        and getattr(b, "fluid_outputs", 0) > 0
    )


def is_fixed_crafter(b: "BuildingDef") -> bool:
    """Bâtiment à recette FIXE pouvant HÉBERGER une recette de craft :
    atelier ``is_crafter`` taggé avec sortie (fluide OU item), ou combusteur
    à résidu (``fuel_residues`` non vide — réacteur nucléaire → résidu item).
    Sur ce sous-ensemble le générateur crée sa recette randomisée. Les
    générateurs/extracteurs/lab (chaleur, électricité, ressource, recherche)
    restent exclus."""
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

# Les VRAIS pylônes (poteaux électriques) sont désormais taggés
# ``BuildingDef.is_power_pole`` (vanilla.py) — le beacon est une distribution
# mais PAS un pylône (il ne transporte pas le courant, §9.1/§10). La cadence
# garantie et le starter ne débloquent que ceux-ci.


@dataclass(frozen=True)
class ItemDef:
    """Item solide du dump (objet craftable ou brut), avec les TAGS
    de classification cumulables (munitions, arme, armure, pack de science,
    outil…) et le type brut du dump comme source de vérité."""
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
    # Type brut du dump (source de vérité : "item", "gun", "armor", ...).
    item_type: str = ""
    # Combustible : catégorie de fuel et RÉSIDU de combustion (l'item produit
    # quand le combustible est brûlé, ex. réacteur : uranium-fuel-cell →
    # depleted-uranium-fuel-cell). Rempli quand le dump a été régénéré avec
    # l'exporter ; sinon vide.
    fuel_category: str = ""
    burnt_result: str | None = None
    # Stack size réel (0 = inconnu : dump non régénéré). Quand il est connu,
    # il fait foi ; sinon on déduit la stackabilité du type.
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
        """Empilable (stack_size > 1) ? Factorio refuse qu'une recette produise/
        consomme plus de 1 exemplaire d'un item non-stackable (armure, arme,
        véhicule, télécommande...). ``stack_size`` réel fait foi ; sinon on se
        rabat sur le type (types non-stackables connus)."""
        if self.stack_size:
            return self.stack_size > 1
        return self.item_type not in NON_STACKABLE_ITEM_TYPES


@dataclass(frozen=True)
class FluidDef:
    """Un fluide est identifie par son nom uniquement :
    la temperature n'est pas une dimension ici."""

    name: str
    fuel_value: float | None = None


@dataclass
class BuildingDef:
    """Bâtiment décrit par des TAGS ORTHOGONAUX CUMULABLES (atelier, générateur
    et producteur de chaleur en même temps, aucune classification exclusive).
    ``equivalent_functional_type`` (vanilla.py) peut reconstruire l'ancien type
    exclusif pour vérification."""

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
    # Sorties « spéciales » NON recettables — TAGS ORTHOGONAUX cumulables.
    # ``produces_electricity`` = vrai producteur de courant (steam-engine,
    # turbine, burner-generator, solar-panel) ; ``produces_heat`` = producteur
    # de chaleur (nuclear-reactor). Le réacteur produit de la chaleur (+ résidu
    # de combustible), pas d'électricité : écarté de l'électricité PAR
    # CAPACITÉS, sans liste de noms. ``has_hidden_recipe`` ne compte jamais
    # ces sorties.
    produces_heat: bool = False
    produces_electricity: bool = False
    # Items résiduels de combustion (burnt_result des combustibles du bâtiment,
    # INSCRITS APRÈS LE PARSE — dépendent de la base items). SORTIES item
    # recevables (ex. réacteur → depleted-uranium-fuel-cell).
    fuel_residues: frozenset[str] = frozenset()
    directives: dict = field(default_factory=dict)
    # Tag « fabricateur à recette cachée » détecté par capacités au chargement du
    # dump (boiler/heat-exchanger et équivalents de mod). Sert à soustraire ces
    # bâtiments du pool des ateliers et à assigner une recette fixe.
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
    """Recette brute du dump : nom, catégorie, ingrédients, produits et
    temps d'énergie — lue directement depuis ``vanilla_dump.json``."""
    name: str
    category: str = ""
    ingredients: tuple = ()
    products: tuple = ()
    energy: float = 0.5


@dataclass
class VanillaDB:
    """Base vanilla parsée : items/fluides/bâtiments/recettes du dump, plus
    les pools dérivées (beltable, pipable, combustibles, extracteurs…). C'est
    la source de vérité en lecture pour toutes les phases du générateur.
    ``seed_value`` porte la seed courante associée à cette base."""
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
        """Items solides posables sur tapis (hors outils), triés par nom."""
        return sorted(
            (i for i in self.items.values() if not i.is_tool),
            key=lambda i: i.name,
        )

    def pipable_fluids(self) -> list[FluidDef]:
        """Fluides pipables du dump, triés par nom."""
        return sorted(self.fluids.values(), key=lambda f: f.name)

    @property
    def extraction_only_fluids(self) -> frozenset[str]:
        """Fluides sans recette de production DIRECTE : eau (offshore-pump),
        pétrole brut (pumpjack), vapeur (chaudière). Le barillage est un cycle
        (fluide → baril → fluide) : recettes "barrel" ignorées. RESSOURCES
        BRUTES extraites de l'environnement, jamais craftées — infinies ou non."""
        produced = {
            p[1]
            for r in self.recipes.values()
            if "barrel" not in r.name
            for p in r.products
            if p[0] == SLOT_FLUID
        }
        return frozenset(name for name in self.fluids if name not in produced)

    def raw_resources(self, patch_resources: set[str]) -> frozenset[str]:
        """Ressources « brutes » d'une seed : patches posés au sol, items
        environnementaux récoltables à la main, fluides d'extraction. Un
        science pack ne doit JAMAIS être crafté avec une ressource brute :
        exclue en génération (forbidden) et vérifiée par pipeline_validator."""
        return frozenset(patch_resources) | set(ENVIRONMENTAL_ITEMS) | self.extraction_only_fluids

    def fuel_items(self) -> list[ItemDef]:
        """Items à valeur combustible, triés par nom."""
        return sorted(
            (i for i in self.items.values() if i.fuel_value),
            key=lambda i: i.name,
        )

    def fuels_for(self, b: "BuildingDef") -> list[ItemDef]:
        """Combustibles qu'un bâtiment PEUT brûler : items avec fuel_value dont
        la catégorie appartient aux ``fuel_categories`` (correspondance PAR
        CATÉGORIE, rien en dur)."""
        if not getattr(b, "fuel_categories", ()):
            return []
        accepted = set(b.fuel_categories)
        return sorted(
            (i for i in self.items.values()
             if i.fuel_value and (i.fuel_category or "") in accepted),
            key=lambda i: i.name,
        )

    def fuel_residues(self, b: "BuildingDef") -> frozenset[str]:
        """SORTIES recevables (items) issues de la combustion : le ``burnt_result``
        de chaque combustible du bâtiment. Réacteur → depleted-uranium-fuel-cell
        (c'est SA sortie item). Vide si le dump n'a pas été régénéré."""
        return frozenset(
            i.burnt_result for i in self.fuels_for(b) if i.burnt_result
        )

    def fuel_item_flow(self, b: "BuildingDef") -> dict:
        """Vue normalisée d'une machine à combustible : entrée = un ITEM
        quelconque en pseudo-combustible, sorties = les items résiduels
        (``burnt_result``). La machine devient item → item (chaleur/électricité
        traitées séparément).
        Exemple : nuclear-reactor → {"input": "item",
        "outputs": {"depleted-uranium-fuel-cell"}}."""
        return {
            "input": "item" if bool(getattr(b, "fuel_categories", ())) else None,
            "outputs": self.fuel_residues(b) or frozenset(),
        }

    def has_fuel_item_flow(self, b: "BuildingDef") -> bool:
        """Combusteur produisant un RÉSIDU item : entrée item (combustible)
        générique ET sortie item (résidu) — vraie transformation item → item."""
        flow = self.fuel_item_flow(b)
        return flow["input"] is not None and bool(flow["outputs"])

    def fuel_fluids(self) -> list[FluidDef]:
        """Fluides à valeur combustible, triés par nom."""
        return sorted(
            (f for f in self.fluids.values() if f.fuel_value),
            key=lambda f: f.name,
        )

    def buildings_with_tag(self, tag: str) -> list[BuildingDef]:
        """Bâtiments portant un TAG donné. Un bâtiment multi-tags apparaît dans
        CHAQUE catégorie qu'il porte."""
        return sorted(
            (b for b in self.buildings.values() if getattr(b, tag, False)),
            key=lambda b: b.name,
        )

    def extractors_for_medium(self, medium: str) -> list[BuildingDef]:
        """Extracteurs du dump pour un milieu donné ('item'/'fluid'), triés
        par nom — ou tous les extracteurs si ``medium`` est vide."""
        return sorted(
            (
                b
                for b in self.buildings.values()
                if b.is_extractor and (not medium or b.medium == medium)
            ),
            key=lambda b: b.name,
        )
