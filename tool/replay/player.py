"""Rejoueur « fake player » : simule une partie réelle sur la seed finale.

Au lieu d'une vérification statique d'invariants (audit_usage, solver), on
REJOUE la partie comme un joueur qui découvre la seed :

  - le kit spawn fournit des items de départ (starter_kit) ;
  - les techs gratuites (free_researches) sont déjà recherchées au spawn ;
  - chaque tech est recherchée dès que ses coûts (packs, ou ``craft_trigger``
    façon prologue §7) sont tous PRODUISIBLES avec ce que le joueur PEUT avoir
    à ce moment-là ;
  - « peut avoir » = fermeture obtenable : sources (environnement récolté à la
    main, patchs minés par un extracteur opérationnel, lacs pompés par pompe
    offshore, kit) + toutes les recettes débloquées dont l'atelier est obtenable
    et alimenté (électricité / combustible / chaleur) ;
  - l'électricité est disponible dès qu'un générateur obtenable peut tourner
    (fluide de lac assigné en entrée s'il en consomme, combustible s'il brûle)
    et qu'un pylône est obtenable.

La partie est gagnable ssi la chaîne fusée (silo + processing-unit +
low-density-structure + rocket-fuel) est atteignable en fin de parcours.

C'est un audit EXTERNE : il ne modifie pas la génération. Une seed qui rate la
victoire révèle un softlock réel (électricité, extraction, timing d'unlock…)
à corriger dans les phases, pas dans le rejoueur.
"""

from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass, field

from tool.common.db import ENVIRONMENTAL_ITEMS, SLOT_FLUID, SLOT_ITEM, VanillaDB

# Items attendus pour « lancer une fusée » (recette vanilla exempte, §14) :
# rocket-part se craft dans le silo avec ces 3 ingrédients.
VICTORY_ITEMS = (
    "rocket-silo",
    "processing-unit",
    "low-density-structure",
    "rocket-fuel",
)

MAX_DEPTH = 5          # profondeur de l'explication d'un blocage
UNKNOWN, ENV, KIT = "unknown", "environment", "kit"
MAX_QDEPTH = 6         # profondeur max de la recherche de faisabilité quantités


@dataclass
class Blocker:
    """Première tech non recherchable + explication lisible (bordereau)."""

    tech: str          # id de la tech bloquante (None si prérequis cassé)
    kind: str          # "prereqs" | "trigger" | "cost" | "lab"
    item: str          # item bloquant (pack, déclencheur, lab)
    reason: str = ""   # chaîne d'explication multi-étapes

    def __str__(self) -> str:
        head = f"{self.tech} : {self.kind}"
        return f"{head} {self.item}" + (f" — {self.reason}" if self.reason else "")


@dataclass
class ReplayReport:
    """Verdict d'une partie rejouée. Vocabulaire aligné sur la seed (voir
    docs/nomenclature-rejoueur.md) : ``mastered`` = item dont une recette
    débloquée a atteint 10× sortie (→ infini) ; ``never_masterable`` = sorties
    de recettes débloquées jamais prouvées ; ``blocker`` = première tech non
    recherchée (``kind`` ∈ "prereqs"|"trigger"|"cost"|"lab")."""

    victory: bool = False
    all_techs_researched: bool = False
    researched: int = 0
    total_techs: int = 0
    blocker: Blocker | None = None
    power_available: bool = False
    power_generator: str | None = None
    satellite_obtainable: bool = False
    obtainable_items: set[str] = field(default_factory=set)
    obtainable_fluids: set[str] = field(default_factory=set)
    researched_order: list[str] = field(default_factory=list)
    mastered: list[str] = field(default_factory=list)
    mastered_tier: dict[str, int] = field(default_factory=dict)
    never_masterable: list[str] = field(default_factory=list)

    def summary(self) -> str:
        state = "VICTOIRE" if self.victory else ("BLOQUÉ" if self.blocker else "SANS FUSÉE")
        n = f"{self.researched}/{self.total_techs}"
        details = f" ({self.blocker})" if self.blocker else ""
        return f"{state} techs={n} élec={'OUI' if self.power_available else 'NON'}{details}"


class FakePlayer:
    """Rejoue une seed. ``db`` = base vanilla, ``seed`` = seed finale."""

    def __init__(self, db: VanillaDB, seed: dict) -> None:
        self.db = db
        self.seed = seed

        self.recipes: list[dict] = seed["recipes"]
        self.techs: list[dict] = seed["technologies"]
        self.free: set[str] = set(seed.get("free_researches") or [])
        self.items_by_name: dict[str, list[str]] = {}
        for r in self.recipes:
            for res in r.get("results") or []:
                if res.get("type") != SLOT_ITEM:
                    continue
                self.items_by_name.setdefault(res["name"], []).append(r["name"])

        # Dépendances inverses de RECETTE (passe de maîtrise) : quel item un
        # item consomme-t-il (ingrédient OU atelier) → quelles sorties re-tenter
        # quand il devient sûr/infini (worklist au lieu du rescan exhaustif).
        self._consumers: dict[str, set[str]] = {}
        for r in self.recipes:
            outs = {
                res["name"] for res in (r.get("results") or [])
                if res.get("type") == SLOT_ITEM
            }
            if not outs:
                continue
            for ing in r.get("ingredients") or []:
                if ing.get("type") != SLOT_ITEM:
                    continue
                self._consumers.setdefault(ing["name"], set()).update(outs)
            if r.get("crafted_in"):
                self._consumers.setdefault(r["crafted_in"], set()).update(outs)

        # §6 révisé (late raws) : disponibilité réelle des ressources par
        # JALON. Une seed gatée exporte ``late_raws`` = {startup: [[kind,name]],
        # gated: {name: {kind, tier}}} — la ressource n'est utilisable qu'une
        # fois atteint son échelon science (`tier`, index de chaîne des packs).
        # Seules les raws MINABLES À LA MAIN du starter (startup) restent
        # libres dès le spawn (jamais listées dans ``gated``). Une seed SANS
        # export garde le comportement historique (carte = infinie au spawn).
        raw_info = seed.get("late_raws") or {}
        self.late_tier: dict[tuple[str, str], int] = {}
        for name, info in (raw_info.get("gated") or {}).items():
            try:
                self.late_tier[(info["kind"], name)] = int(info["tier"])
            except (KeyError, TypeError, ValueError):
                pass
        # Échelon science atteint : index max de la chaîne des packs consommés
        # par les techs déjà recherchées (miroir `late_raws._tech_tier`).
        self._science_chain = self._build_science_chain()
        self._tech_tier: dict[str, int] = {}
        for tech in self.techs:
            self._tech_tier[tech["id"]] = max(
                (
                    self._science_chain.index(i["name"])
                    for i in (tech.get("unit") or {}).get("ingredients", [])
                    if i.get("name") in self._science_chain
                ),
                default=-1,
            )

        # Extraction : modèle de CAPACITÉ physique (data-updates.lua) — la mapping
        # C3 (`extractor_timing`) ne fixe que le DÉBLOCAGE au fil de l'arbre
        # (audit EXT), pas la physique : tout patch item est en ``basic-solid``
        # et mineable par TOUTE foreuse compatible obtenable et opérationnelle
        # (burner → combustible ; électrique → réseau), un patch fluide
        # ``basic-fluid`` exige un pumpjack (électricité), un lac se pompe via
        # une pompe offshore (void, sans électricité). Le joueur peut donc
        # miner un patch item dès qu'il a une foreuse au kit — c'est ce que
        # modèle le rejoueur, quel que soit le format de seed.
        self.extractors = self._infer_extractors()

        # Fluides de lac (pompés par pompe offshore, énergie void) et patchs.
        map_ = seed.get("map") or {}
        self.lake_resources: set[str] = {
            la["resource"] for la in map_.get("lakes") or []
        }
        self.patch_resources: set[str] = {
            p["resource"] for p in map_.get("patches") or []
        }
        # Patches ITEM : ramassés à la main au spawn (stock fini de départ,
        # façon épave) — le drill ne sert qu'à les rendre infinis ensuite. Un
        # patch FUIDE, lui, exige un pumpjack (électricité). C'est le modèle
        # capacity (data-updates.lua) : tout patch item est en ``basic-solid``,
        # Physicalement ramassable sans foreuse.
        self.item_patch_resources: set[str] = {
            p["resource"] for p in map_.get("patches") or []
            if p.get("kind") == SLOT_ITEM
        }

        # Fluides assignés aux bâtiments à comportement fixe (§6/§10) : un
        # générateur à vapeur consume son ``input`` (fluid de lac).
        self.fluid_assignments: dict[str, dict[str, str]] = seed.get(
            "building_fluid_assignments", {}
        )

        # États de la partie.
        self.researched: set[str] = set(self.free)
        self.unlocked: set[str] = set()
        for tech in self.techs:
            if tech["id"] in self.researched:
                self.unlocked.update(self._unlocks_of(tech))
        self._prep_db()
        self._prep_kit()
        self._invalidate_caches()

    # ── Préparation ───────────────────────────────────────────────────────

    def _prep_db(self) -> None:
        self.items_db = self.db.items
        self.buildings_db = self.db.buildings

    # ── Disponibilité des raws par jalon (§6 révisé) ──────────────────────

    def _build_science_chain(self) -> list[str]:
        """Chaîne des science packs (miroir `late_raws._science_chain`) :
        ordonnés par l'index de déblocage de leur recette de craft — chaque
        pack coûte le précédent (§13)."""
        claim: dict[str, int] = {}
        for index, tech in enumerate(self.techs):
            for effect in tech.get("effects", []):
                if effect.get("type") == "unlock-recipe":
                    claim.setdefault(effect["recipe"], index)
        packs = {
            r["results"][0]["name"]
            for r in self.recipes
            if r.get("results") and r["results"][0].get("type") == SLOT_ITEM
            and str(r["results"][0]["name"]).endswith("-science-pack")
        }
        return sorted(
            packs,
            key=lambda p: (claim.get(f"randputf-{p}", 10**9), p),
        )

    def _current_tier(self) -> int:
        """Échelon science atteint : index max (chaîne des packs) parmi (a) les
        packs réellement produisibles dans le monde courant (le plus fiable :
        miroir de ``len(_unlocked_science_packs)-1`` du générateur) et (b) les
        techs déjà recherchées. Le max des deux signaux évite de sur-verrouiller
        une raw quand un tech ne coûte qu'un sous-ensemble de packs."""
        tiers = set()
        idx = [self._tech_tier[t] for t in self.researched if t in self._tech_tier]
        tiers.add(max(idx) if idx else -1)
        packs = sum(1 for p in self._science_chain if p in self._world_items)
        tiers.add(packs - 1)
        return max(tiers)

    def _raw_available(self, kind: str, name: str) -> bool:
        """Une raw est-elle utilisable en l'état ?

        Sans export ``late_raws`` (gating désactivé) tout reste disponible ;
        avec gating : une raw non start-up n'est disponible que si son JALON
        (tier) est atteint (les raws non gatées — startup — n'apparaissent
        jamais dans ``late_tier`` et valent donc True)."""
        if not self.late_tier:
            return True
        tier = self.late_tier.get((kind, name))
        return tier is None or tier <= self._current_tier()

    def _raw_infinite_now(self, item: str) -> bool:
        """``base_infinite`` restreint au jalon : un item gated n'est infini
        qu'à partir du moment où son jalon est atteint ; les raws non gatées
        (startup/environnement) restent infinies d'office."""
        if item not in self.base_infinite:
            return False
        if not self.late_tier:
            return True
        tier = self.late_tier.get((SLOT_ITEM, item))
        if tier is None:
            return True
        return tier <= self._current_tier()

    def _prep_kit(self) -> None:
        self.kit: set[str] = {
            e["name"]
            for e in self.seed.get("starter_kit") or []
            if e.get("type") == SLOT_ITEM
        }
        # Crash site : les conteneurs de l'épave fournissent aussi des items
        # (loot, §7.4) — un joueur les ramasse au spawn.
        self.kit |= {
            e
            for e in (self.seed.get("wreck") or {}).get("loot") or []
            if e in self.items_db
        }
        # Quantités finies du kit (nécessaires à la faisabilité « combien de
        # copies peut-on avoir ») — au-delà de la présence (ensemble).
        self.kit_counts: Counter[str] = Counter()
        for e in self.seed.get("starter_kit") or []:
            if e.get("type") == SLOT_ITEM:
                self.kit_counts[e["name"]] += e.get("count", 1)
        for x in (self.seed.get("wreck") or {}).get("loot") or []:
            if x in self.items_db:
                self.kit_counts[x] += 1
        # Patchs ITEM : ramassage à la main au spawn = stock FINI (count de la
        # ressource) tant qu'aucune foreuse opérationnelle ne le rend infini.
        self.item_patch_counts: Counter[str] = Counter()
        map_ = self.seed.get("map") or {}
        for p in map_.get("patches") or []:
            if p.get("kind") == SLOT_ITEM:
                self.item_patch_counts[p["resource"]] += p.get("count", 0)

        # Simulation FORWARD « comme un joueur » : un inventaire réel, un compteur
        # cumulé d'usinage, et une REGLE DE MAITRISE — dès qu'un item a été
        # fabriqué en quantité égale à la SORTIE de sa recette ×10 (had ≥
        # 10×sortie, ex. sortie 2 → maîtrise à 20), son craft est « devenu sûr » :
        # il devient INFINI, on n'a plus à le recrafter pour l'employer (l'atelier
        # est recrafé à chaque passe tant que la maîtrise n'est pas acquise). Les
        # ressources de base (environnement, patchs, lacs) sont infinies d'office.
        self.inv: Counter[str] = Counter(self.kit_counts)
        self.had: Counter[str] = Counter(self.kit_counts)
        self.base_infinite: set[str] = set(ENVIRONMENTAL_ITEMS) & set(self.items_db)
        self.base_infinite |= self.item_patch_resources
        self.base_infinite |= self.patch_resources
        self.base_infinite |= self.lake_resources
        self.mastered: set[str] = set()
        self.mastered_tier: dict[str, int] = {}
        # Caches (10×sortie, fermeture infinie par snapshot monde) — reconstruits
        # à chaque tech dans play() quand le monde débloqué change.
        self._mastery_goal: dict[str, int] = {}
        self._inf_cache: dict[
            tuple[frozenset[str], frozenset[str], bool], tuple[set[str], set[str]]
        ] = {}
        # Monde courant « obtenable » pour la garde d'énergie des ateliers
        # (mis à jour à chaque tech dans play()).
        self._world_items: set[str] = set()
        self._world_fluids: set[str] = set()
        self._world_power: bool = False
        self.fluids_obtainable: set[str] = set()

    def _infer_extractors(self) -> list[tuple[str, list[dict]]]:
        """Fallback pour seeds SANS passe ``extractor_timing`` (branche de
        base, pré-C3) : chaque ressource brute est rattachée à TOUS les
        extracteurs capables (foreuses pour un patch item, pumpjacks pour un
        patch fluide, pompes offshore pour un lac) ; elle devient atteignable
        dès que l'un d'eux est obtenable et opérationnel."""
        map_ = self.seed.get("map") or {}
        buildings = list(self.db.buildings.values())
        entries: list[tuple[str, list[dict]]] = []
        for la in map_.get("lakes") or []:
            cand = [b.name for b in buildings if getattr(b, "is_offshore_pump", False)]
            for name in cand or ["offshore-pump"]:
                entries.append((name, [{"type": SLOT_FLUID, "name": la["resource"]}]))
        for p in map_.get("patches") or []:
            res, kind = p["resource"], p.get("kind")
            if kind == SLOT_ITEM:
                # Item patch : RAMASSÉ à la main au spawn (resource finie) —
                # jamais une dépendance à une foreuse (le drill le rend infini,
                # mais l'obtention du premier exemplaire n'exige rien).
                continue
            cand = [
                b.name for b in buildings
                if getattr(b, "is_pumpjack", False) or getattr(b, "is_well_pump", False)
            ]
            fallback, t = "pumpjack", SLOT_FLUID
            for name in cand or [fallback]:
                entries.append((name, [{"type": t, "name": res}]))
        return entries

    def _unlocks_of(self, tech: dict) -> set[str]:
        out = set()
        for effect in tech.get("effects") or []:
            if effect.get("type") == "unlock-recipe":
                out.add(effect["recipe"])
        return out

    # ── Fermeture obtenable (le « peut avoir » du joueur) ─────────────────

    def _fuel_obtainable(self, items: set[str]) -> bool:
        return any(
            (self.items_db.get(n) is not None and self.items_db[n].fuel_value)
            for n in items
        )

    def _heat_chain_ok(self, items: set[str]) -> bool:
        has_source = any(
            b.name in items
            for b in self.buildings_db.values()
            if getattr(b, "is_heat_source", False)
        )
        has_transport = any(
            b.name in items
            for b in self.buildings_db.values()
            if getattr(b, "is_heat_transport", False)
        )
        return has_source and has_transport

    def _energy_ok(self, building, items: set[str], power: bool) -> bool:
        et = getattr(building, "energy_type", "burner")
        if et == "electric":
            return power
        if et == "burner":
            return self._fuel_obtainable(items)
        if et == "heat":
            return self._heat_chain_ok(items)
        return True  # void / inconnu : pas de contrainte d'énergie

    def _generator_ok(self, b, items: set[str], fluids: set[str]) -> bool:
        """Un générateur (produces_electricity) peut-il tourner ?"""
        if getattr(b, "fluid_inputs", 0) > 0:
            assign = self.fluid_assignments.get(b.name, {})
            inp = assign.get("input")
            if inp:
                return inp in fluids
            return bool(fluids)  # pas d'assignation : un fluide disponible suffit
        if getattr(b, "energy_type", "") == "burner":
            return self._fuel_obtainable(items)
        return True  # solaire / hors réseau : autonome

    def _add_power(self, items: set[str], fluids: set[str]) -> tuple[bool, str | None]:
        """Électricité dispo ? Un pylône obtenable + un générateur obtenable et
        opérationnel (fluide de lac assigné / combustible)."""
        if not any(
            b.name in items
            for b in self.buildings_db.values()
            if getattr(b, "is_power_pole", False)
        ):
            return False, None
        for b in self.buildings_db.values():
            if not getattr(b, "produces_electricity", False):
                continue
            if b.name not in items:
                continue
            if self._generator_ok(b, items, fluids):
                return True, b.name
        return False, None

    def _closure_items_buckets(self) -> tuple[set[str], set[str]]:
        """Items/fluides de départ (sources + kit + patches item ramassés)."""
        items = set(ENVIRONMENTAL_ITEMS) & set(self.items_db)
        items |= self.kit
        # Patches ITEM : ramassables à la main au spawn (resource finie, façon
        # épave/§7.4) — pas besoin de foreuse pour les obtenir au départ ; une
        # foreuse opérationnelle les rend infinis (capacity, data-updates.lua).
        # §6 révisé : un patch gated n'est pas ramassable avant son jalon.
        items |= {
            n for n in self.item_patch_resources if self._raw_available(SLOT_ITEM, n)
        }
        fluids: set[str] = set()
        return items, fluids

    def closure(self) -> tuple[set[str], set[str], bool, str | None]:
        """Fermeture obtenable AVEC le state courant (recettes débloquées).

        Point fixe : sources (environnement, kit) → extracteurs opérationnels
        (patchs/lacs) → électricité (générateur obtenable + pylône) → recettes
        dont l'atelier est obtenable et alimenté. Retourne ``(items, fluids,
        power, generator)``."""
        items, fluids = self._closure_items_buckets()
        power, generator = False, None
        changed = True
        while changed:
            changed = False
            # Extraction : patchs (foreuse) et lacs (pompe offshore void).
            for recipe_name, resources in self.extractors:
                extractor_item = recipe_name.removeprefix("randputf-")
                if extractor_item not in items:
                    continue
                b = self.buildings_db.get(extractor_item)
                if b is not None and not self._energy_ok(b, items, power):
                    continue
                for res in resources:
                    if not self._raw_available(res.get("type"), res["name"]):
                        continue
                    bucket = items if res.get("type") == SLOT_ITEM else fluids
                    if res["name"] not in bucket:
                        bucket.add(res["name"])
                        changed = True
            # Électricité : un générateur + un pylône suffisent au réseau.
            if not power:
                power, generator = self._add_power(items, fluids)
                if power:
                    changed = True
            # Recettes débloquées et exécutables.
            for recipe in self.recipes:
                if recipe["name"] not in self.unlocked:
                    continue
                if not self._recipe_runs(recipe, items, fluids, power):
                    continue
                for res in recipe.get("results") or []:
                    bucket = items if res.get("type") == SLOT_ITEM else fluids
                    if res["name"] not in bucket:
                        bucket.add(res["name"])
                        changed = True
        return items, fluids, power, generator

    def _recipe_runs(
        self, recipe: dict, items: set[str], fluids: set[str], power: bool
    ) -> bool:
        for ing in recipe.get("ingredients") or []:
            bucket = items if ing.get("type") == SLOT_ITEM else fluids
            if ing["name"] not in bucket:
                return False
        crafted_in = recipe.get("crafted_in")
        if not crafted_in:
            return True  # craft à la main
        if crafted_in not in items:
            return False  # atelier pas encore construisible
        b = self.buildings_db.get(crafted_in)
        if b is not None and not self._energy_ok(b, items, power):
            return False
        return True

    # ── Faisabilité QUANTITATIVE (le « combien » plutôt que le « quel ») ──
    #
    # La fermeture d'ensemble n'atteste qu'une OBTAINABILITÉ : si les ingrédients
    # d'une recette sont dans le bucket, la recette « tourne ». Mais un item peut
    # être obtenable et pourtant en quantité INSUFFISANTE à une recette (ex. le
    # steel-furnace du prologue exige 4 offshore-pumps : si le kit ne fournit
    # qu'1 pumpjack, les 3 offshore-pumps manquants sont infabriquables tant que
    # la recette du pumpjack n'est pas débloquée → softlock de QUANTITÉ qui
    # passe la fermeture d'ensemble).
    #
    # ``can_fund`` répond à « le joueur peut-il RÉUNIR ces quantités ? » :
    #   - les ressources INFINIES (environnement, patch item une fois une
    #     foreuse opérationnelle, fluides une fois l'extracteur opérationnel,
    #     et toute recette dont tous les ingrédients sont infinis) sont libres ;
    #   - le stock FINI (kit + patchs item ramassés à la main) est un budget
    #     PARTAGÉ : chaque recette puise dans le même panier, jamais deux fois ;
    #   - c'est une recherche en profondeur (peu de recettes par item, MAX_QDEPTH
    #     règles de profondeur) : le premier plan de fabrication qui tient gagne.

    def _infinite_items(
        self, items: set[str], fluids: set[str], power: bool
    ) -> tuple[set[str], set[str]]:
        """Items/fluides en quantité INFINIE pour le state courant :
        environnement, patch item miné par une foreuse opérationnelle, fluides
        extraits (lacs/patchs), et toute recette débloquée dont les ingrédients
        sont eux-mêmes infinis et l'atelier est disponible."""
        inf_items: set[str] = set(ENVIRONMENTAL_ITEMS) & set(self.items_db)
        inf_fluids: set[str] = set(fluids)
        cache_key = (frozenset(items), frozenset(fluids), power)
        hit = self._inf_cache.get(cache_key)
        if hit is not None:
            return hit[0], hit[1]
        drill_works = any(
            b.name in items
            and getattr(b, "is_mining_drill", False)
            and not getattr(b, "is_pumpjack", False)
            and self._energy_ok(b, items, power)
            for b in self.buildings_db.values()
        )
        if drill_works:
            inf_items |= {
                n for n in self.item_patch_resources
                if self._raw_available(SLOT_ITEM, n)
            }
        changed = True
        while changed:
            changed = False
            for recipe in self.recipes:
                if recipe["name"] not in self.unlocked:
                    continue
                if not self._recipe_runs(recipe, items, fluids, power):
                    continue
                ings = recipe.get("ingredients") or []
                if any(ing.get("type") == SLOT_ITEM and ing["name"] not in inf_items for ing in ings):
                    continue
                if any(ing.get("type") == SLOT_FLUID and ing["name"] not in inf_fluids for ing in ings):
                    continue
                for res in recipe.get("results") or []:
                    if res.get("type") == SLOT_ITEM and res["name"] not in inf_items:
                        inf_items.add(res["name"])
                        changed = True
                    elif res.get("type") == SLOT_FLUID and res["name"] not in inf_fluids:
                        inf_fluids.add(res["name"])
                        changed = True
        self._inf_cache[cache_key] = (inf_items, inf_fluids)
        return inf_items, inf_fluids

    def _recipe_result_amount(self, recipe: dict, target: str) -> int:
        for res in recipe.get("results") or []:
            if res.get("type") == SLOT_ITEM and res["name"] == target:
                return int(res.get("amount", 1))
        return 1

    def _obtain_qty(
        self,
        item: str,
        need: int,
        budget: Counter[str],
        inf: tuple[set[str], set[str]],
        items: set[str],
        fluids: set[str],
        power: bool,
        seen: frozenset[str] = frozenset(),
        depth: int = 0,
    ) -> bool:
        """Peut-on réunir ``need`` copies de ``item`` en piochant dans le budget
        fini (muté) et les recettes débloquées ? ``budget`` est partagé entre
        tous les ingrédients d'une recette (jamais dépensé deux fois)."""
        if need <= 0:
            return True
        if depth > MAX_QDEPTH:
            return False
        if item in inf[0] or item in inf[1]:
            return True
        if item in seen:
            return False  # cycle : aucune recette ne crée de copies avec ça
        have = budget.get(item, 0)
        if have > 0:
            take = min(have, need)
            budget[item] -= take
            need -= take
            if need <= 0:
                return True
        for producer in self.items_by_name.get(item, []):
            if producer not in self.unlocked:
                continue
            recipe = next(r for r in self.recipes if r["name"] == producer)
            # Atelier disponible (même garde que la fermeture d'ensemble).
            crafted_in = recipe.get("crafted_in")
            if crafted_in and crafted_in not in items:
                continue
            if not self._recipe_runs(recipe, items, fluids, power):
                continue
            per_run = self._recipe_result_amount(recipe, item)
            runs = math.ceil(need / per_run) if per_run else 1
            branch = Counter(budget)
            ok = True
            for ing in recipe.get("ingredients") or []:
                if ing.get("type") == SLOT_FLUID:
                    if ing["name"] not in fluids:
                        ok = False
                        break
                    continue
                q = int(ing.get("amount", 1)) * runs
                if not self._obtain_qty(
                    ing["name"], q, branch, inf, items, fluids, power,
                    seen | {item}, depth + 1,
                ):
                    ok = False
                    break
            if ok:
                budget.clear()
                budget.update(branch)
                return True
        return False

    def can_fund(
        self, needs: Counter[str], items: set[str], fluids: set[str], power: bool
    ) -> bool:
        """Le joueur peut-il réunir TOUTES les quantités de ``needs`` à la fois
        (stock fini partagé) avec les recettes débloquées ?"""
        inf = self._infinite_items(items, fluids, power)
        budget: Counter[str] = Counter(self.kit_counts)
        for patch, count in self.item_patch_counts.items():
            if patch in inf[0] or not self._raw_available(SLOT_ITEM, patch):
                continue
            budget[patch] += count
        for item, need in needs.items():
            if need <= 0:
                continue
            if not self._obtain_qty(
                item, need, budget, inf, items, fluids, power
            ):
                return False
        return True

    # ── Passe de MAÎTRISE (le « tester tout un par un » du joueur) ────────
    #
    # À chaque déblocage, le joueur ESSAIE réellement chaque recette nouvelle :
    # il la fabrique jusqu'à 10× la sortie de la recette (sortie 2 → 20, l'atelier
    # est recrafé à chaque passe — on ne le réutilise pas), et dès qu'un item
    # atteint 10× sa sortie il devient sûr (infini, plus besoin de le refabriquer
    # pour l'employer). Worklist inverse : quand un item passe sûr/infini, on ne
    # reteste que les recettes qui le CONSOMMENT (ingrédient ou atelier) — point
    # fixe identique de la boucle exhaustive (« un échec ne laisse aucune trace » :
    # inv/had sont restaurés, seule une réussite mute l'état). C'est l'accumulation
    # qui débloque les chaînes profondes (l'atelier de base se maîtrise d'abord,
    # puis débloque la recette au dessus, etc.) au lieu de tout refaire à chaque
    # demande en profondeur (cercle vicieux de l'ancien `_craft` à la demande).

    def _invalidate_caches(self) -> None:
        """Reconstruit les caches quand le monde débloqué change : ``_mastery_goal``
        (sortie max ×10 de chaque item chez ses recettes débloquées) et
        ``_inf_cache`` (fermeture « infinie » par snapshot du monde)."""
        self._inf_cache.clear()
        goal: dict[str, int] = {}
        for r in self.recipes:
            if r["name"] not in self.unlocked:
                continue
            for res in r.get("results") or []:
                if res.get("type") != SLOT_ITEM:
                    continue
                amt = int(res.get("amount", 1))
                if amt > goal.get(res["name"], 0):
                    goal[res["name"]] = amt
        self._mastery_goal = goal
        self.mastered = {
            n for n, c in self.had.items()
            if c >= 10 * goal.get(n, 0) and goal.get(n, 0) > 0
        }

    def _is_mastered(self, item: str) -> bool:
        """L'item est-il « sûr » ? (au moins 10× la sortie de sa recette.)"""
        out = 10 * self._mastery_goal.get(item, 0)
        return out > 0 and self.had.get(item, 0) >= out

    def _mastery_sweep(self) -> None:
        """Tente de porter chaque item (recette débloquée, non sûr, non infini)
        à 10× la sortie de sa recette, par worklist des consommateurs. ``had`` ne
        fait que croître et les échecs restaurent l'état — termine, et converge
        vers le même point fixe qu'un rescan exhaustif."""
        self._invalidate_caches()   # réflète le nouvel unlock dans `_mastery_goal`
        pending: deque[str] = deque()
        for r in self.recipes:
            if r["name"] not in self.unlocked:
                continue
            for res in r.get("results") or []:
                if res.get("type") != SLOT_ITEM:
                    continue
                name = res["name"]
                if name in self.item_patch_resources:
                    continue  # pas une recette de craft (raw ramassée)
                if self._is_mastered(name) or self._raw_infinite_now(name):
                    continue
                pending.append(name)
        forwarded: set[str] = set()
        while pending:
            name = pending.popleft()
            if self._is_mastered(name) or self._raw_infinite_now(name):
                continue
            if name not in self.mastered:
                if self._craft(name, 10 * self._mastery_goal.get(name, 0)):
                    # Un item devient sûr → ses CONSOMMATEURS (ingrédient/atelier)
                    # deviennent peut-être testables : on les re-tente.
                    self.mastered.add(name)
                    self.mastered_tier.setdefault(name, self._current_tier())
                    for consumer in self._consumers.get(name, ()):
                        if (not self._is_mastered(consumer)
                                and not self._raw_infinite_now(consumer)):
                            pending.append(consumer)
                continue
            # Déjà traité sans être « sûr » (sortie non requise : `_is_mastered`
            # reste faux) : on relance seulement la propagation vers ses
            # consommateurs (le matériel a pu s'améliorer), UNE fois — sinon les
            # cycles de produits à sortie non requise re-filent à l'infini.
            if name in forwarded:
                continue
            forwarded.add(name)
            for consumer in self._consumers.get(name, ()):
                if (not self._is_mastered(consumer)
                        and not self._raw_infinite_now(consumer)):
                    pending.append(consumer)

    # ── Simulation FORWARD (le « comme un joueur ») ──────────────────────
    #
    # Le joueur joue réellement : un inventaire `Counter` qu'il consomme et
    # remplit, tech après tech, du spawn jusqu'à la fusée. Il joue « avec les
    # recettes » :
    #   - chaque craft prélève ses ingrédients ET son atelier (crafted_in) de
    #     l'inventaire (« tout est consommé ») et y ajoute le résultat ;
    #   - les ressources de base (environnement, patchs item/fluide, lacs) sont
    #     INFINIES d'office (elles ne se consomment jamais) ;
    #   - MAÎTRISE : dès qu'un item a été fabriqué jusqu'à 10× la sortie de sa
    #     recette (had ≥ 10×sortie), son craft est « devenu sûr » → l'item devient
    #     INFINI, plus besoin de le recrafter pour l'employer. C'est l'accélération
    #     qui remplace le décompte exhaustif par item (la passe `_mastery_sweep`
    #     « essaie tout » à chaque déblocage).
    #
    # Les crafts d'une tech PAYENT PERSISTENT (le joueur garde son inventaire
    # entre les techs) ; la victoire = toutes les techs recherchées + les items
    # de la chaîne fusée fabriquables.

    def _craft(
        self,
        item: str,
        need: int,
        depth: int = 0,
        seen: frozenset[str] = frozenset(),
    ) -> bool:
        """Peut-on disposer de ``need`` copies de ``item`` en jouant vraiment ?
        (base infinie / maîtrise → gratuit ; sinon inventaire puis recettes
        débloquées, envergure et consommation comprises)."""
        if need <= 0:
            return True
        if self._raw_infinite_now(item) or self._is_mastered(item):
            return True
        if depth > MAX_QDEPTH:
            return False
        save = (Counter(self.inv), Counter(self.had))
        take = min(need, self.inv[item])
        self.inv[item] -= take
        need -= take
        if need <= 0:
            return True
        for producer in self.items_by_name.get(item, []):
            if producer not in self.unlocked:
                continue
            recipe = next(r for r in self.recipes if r["name"] == producer)
            per_run = self._recipe_result_amount(recipe, item)
            if per_run <= 0:
                continue
            runs = math.ceil(need / per_run)
            crafted_in = recipe.get("crafted_in")
            # BACKTRACK « avant la consommation bloquante » : état rembobiné si ce
            # producteur échoue (l'atelier déjà fabriqué et les ingrédients déjà
            # consommés sont remis en place) avant de tenter le producteur suivant.
            back = (Counter(self.inv), Counter(self.had))
            ok = True
            if crafted_in:
                # L'atelier est CONSOMMÉ à chaque craft (« tout est consommé ») :
                # le joueur doit en avoir `runs` exemplaires (base/maîtrise =
                # gratuits, sinon fabriqués), ET être alimenté (élec/combustible).
                b = self.buildings_db.get(crafted_in)
                if b is not None and not self._energy_ok(
                    b, self._world_items, self._world_power
                ):
                    continue
                if not self._craft(crafted_in, runs, depth + 1, seen | {item}):
                    continue
            for ing in recipe.get("ingredients") or []:
                if ing.get("type") == SLOT_FLUID:
                    if ing["name"] not in self.fluids_obtainable:
                        ok = False
                        break
                    continue
                q = int(ing.get("amount", 1)) * runs
                if not self._craft(ing["name"], q, depth + 1, seen | {item}):
                    ok = False
                    break
            if not ok:
                self.inv, self.had = back
                continue
            produced = per_run * runs
            self.inv[item] += produced
            self.had[item] += produced
            return True
        self.inv, self.had = save
        return False

    # ── Progression des techs (le « quand j'ai de quoi → je recherche ») ──

    def play(self) -> ReplayReport:
        report = ReplayReport(total_techs=len(self.techs))
        for tech in self.techs:
            tech_id = tech["id"]
            if tech_id in self.researched:
                continue
            # Prérequis (ordre linéaire : normalement déjà satisfaits).
            missing_prereqs = [
                p for p in tech.get("prerequisites") or [] if p not in self.researched
            ]
            if missing_prereqs:
                report.blocker = Blocker(tech_id, "prereqs", ",".join(missing_prereqs))
                break
            items, fluids, power, generator = self.closure()
            self._world_items, self._world_fluids, self._world_power = items, fluids, power
            self.fluids_obtainable = fluids
            self._invalidate_caches()
            report.power_available, report.power_generator = power, generator
            # Le lab reçoit les packs (garanti au starter, §8) — garde-fou.
            if "lab" not in items:
                report.blocker = Blocker(tech_id, "lab", "lab")
                break
            # Transaction façon joueur : on ne dépense que si TOUTE la tech est
            # abordable (déclencheur + packs). En cas d'échec, on restaure
            # l'inventaire (le joueur n'a pas usiné pour une tech ratée).
            save = (Counter(self.inv), Counter(self.had))
            ev = self._evaluate_tech(tech, items, fluids, power)
            trigger, stuck = ev
            if stuck is not None:
                self.inv, self.had = save
                if trigger:
                    report.blocker = Blocker(tech_id, "trigger", trigger, self.explain_qty(trigger, items, fluids, power))
                else:
                    report.blocker = Blocker(tech_id, "cost", stuck[0], self.explain_qty(stuck[0], items, fluids, power))
                break
            # Recherche : on débloque les effets de la tech, puis le joueur
            # « essaie tout » les nouvelles recettes (passe de maîtrise 10×).
            self.researched.add(tech_id)
            self.unlocked.update(self._unlocks_of(tech))
            self._mastery_sweep()
            report.researched_order.append(tech_id)
        report.researched = len(self.researched)
        report.all_techs_researched = report.researched == len(self.techs)
        # Victoire : chaîne fusée atteignable une fois l'arbre consommé.
        items, fluids, power, generator = self.closure()
        self._world_items, self._world_fluids, self._world_power = items, fluids, power
        self.fluids_obtainable = fluids
        report.power_available, report.power_generator = power, generator
        report.obtainable_items, report.obtainable_fluids = items, fluids
        report.satellite_obtainable = "satellite" in items
        report.mastered = sorted(self.mastered)
        report.mastered_tier = dict(self.mastered_tier)
        report.never_masterable = sorted(
            {
                res["name"]
                for r in self.recipes if r["name"] in self.unlocked
                for res in (r.get("results") or [])
                if res.get("type") == SLOT_ITEM
                and res["name"] not in self.mastered
                and res["name"] not in self.item_patch_resources
                and not self._raw_infinite_now(res["name"])
            }
        )
        report.victory = (
            report.all_techs_researched
            and "satellite" in items
            and all(self._craft(v, 1) for v in VICTORY_ITEMS)
        )
        return report

    def _evaluate_tech(
        self,
        tech: dict,
        items: set[str],
        fluids: set[str],
        power: bool,
    ) -> tuple[str | None, tuple[str, int] | None]:
        """Usine les besoins de ``tech`` dans l'état courant (inventaire muté).
        Retourne ``(trigger_raté, (pack_raté, quantité))`` : l'un des deux est
        non-None en cas d'échec, sinon (None, None)."""
        trigger = tech.get("craft_trigger")
        if trigger and not self._craft(trigger, 1):
            return trigger, None
        costs = tech.get("unit", {}).get("ingredients") or []
        count = tech.get("unit", {}).get("count") or 1
        for c in costs:
            need = int(c.get("amount", 1)) * int(count)
            if need > 0 and not self._craft(c["name"], need):
                return None, (c["name"], need)
        return None, None

    def explain_qty(
        self,
        target: str,
        items: set[str],
        fluids: set[str],
        power: bool,
        depth: int = 0,
        need: int = 1,
    ) -> str:
        """Pourquoi ``target`` n'est pas disponible en quantité suffisante :
        le plus court chemin de fabrication (min d'ingrédients) et le premier
        ingrédient fini (kit/patch) qui manque, borné en profondeur."""
        inf_items, inf_fluids = self._infinite_items(items, fluids, power)
        budget: Counter[str] = Counter(self.kit_counts)
        for patch, count in self.item_patch_counts.items():
            if patch in inf_items or not self._raw_available(SLOT_ITEM, patch):
                continue
            budget[patch] += count
        return self._explain_qty(
            target, need, budget, (inf_items, inf_fluids),
            items, fluids, power, depth,
        )

    def _explain_qty(
        self,
        target: str,
        need: int,
        budget: Counter[str],
        inf: tuple[set[str], set[str]],
        items: set[str],
        fluids: set[str],
        power: bool,
        depth: int,
        seen: frozenset[str] = frozenset(),
    ) -> str:
        if depth >= MAX_QDEPTH:
            return f"{target}×{need} → profondeur maximale atteinte"
        have = budget.get(target, 0)
        if have > 0 and need <= have:
            return f"{target}×{need} ← kit/patch fini (×{have})"
        rest = need - have
        producers = [
            r for r in self.recipes
            if r["name"] in self.unlocked and any(
                res.get("type") == SLOT_ITEM and res.get("name") == target
                for res in r.get("results") or [])
        ]
        if not producers:
            return (
                f"{target}×{rest} ← kit fini insuffisant (×{budget.get(target, 0)})"
            )
        missing: list[tuple[dict, list[dict]]] = []
        for r in producers:
            ings = r.get("ingredients") or []
            miss = [
                ing for ing in ings
                if (ing.get("type") == SLOT_ITEM and ing["name"] not in inf[0])
                or (ing.get("type") == SLOT_FLUID and ing["name"] not in inf[1])
            ]
            missing.append((r, miss))
        missing.sort(key=lambda t: len(t[1]))
        recipe, miss = missing[0]
        per_run = max(1, self._recipe_result_amount(recipe, target))
        runs = math.ceil(rest / per_run)
        bits: list[str] = []
        for ing in miss[:2]:
            q = int(ing.get("amount", 1)) * runs
            bits.append(
                f"{ing['name']}×{q} ← {self._explain_qty(ing['name'], q, budget, inf, items, fluids, power, depth + 1, seen | {target})}"
            )
        crafted_in = recipe.get("crafted_in")
        if crafted_in and crafted_in not in items:
            bits.append(f"atelier {crafted_in} absent")
        return f"{target}×{need} ({recipe['name']}): " + (" ; ".join(bits) if bits else "ingrédients manquants")

    # ── Explication d'un blocage (bordereau joueur) ──────────────────────

    def explain(
        self,
        target: str,
        items: set[str],
        fluids: set[str],
        power: bool,
        depth: int = 0,
        seen: frozenset[str] = frozenset(),
    ) -> str:
        """Pourquoi ``target`` n'est PAS obtenable : chaîne lisible du plus
        proche au plus profond, bornée en profondeur."""
        if target in ENVIRONMENTAL_ITEMS or target in self.kit:
            return "déjà obtenu (source/kit)"
        if depth >= MAX_DEPTH:
            return f"{target} → profondeur maximale atteinte"
        if target in seen:
            return f"{target} → cycle"

        # Ressource brute gatée (jalon §6 révisé) : le jalon n'est pas atteint.
        if not (self._raw_available(SLOT_ITEM, target)
                and self._raw_available(SLOT_FLUID, target)):
            return (
                f"{target} ← jalon non atteint "
                f"(tier {self._current_tier()})"
            )

        # Ressource brute : passe par son extracteur (C3).
        for recipe_name, resources in self.extractors:
            if any(res["name"] == target for res in resources):
                extractor_item = recipe_name.removeprefix("randputf-")
                return (
                    f"{target} ← {extractor_item} : "
                    f"{self.explain(extractor_item, items, fluids, power, depth + 1, seen | {target})}"
                )

        producers = [
            r for r in self.recipes
            if r["name"] in self.unlocked
            and any(res.get("type") == SLOT_ITEM and res.get("name") == target
                    for res in r.get("results") or [])
        ]
        if not producers:
            return f"{target} → aucune recette débloquée"
        # La recette « la plus près » : le moins d'ingrédients manquants.
        missing = [
            (r, [ing for ing in r.get("ingredients") or [] if ing["name"] not in items])
            for r in producers
        ]
        missing.sort(key=lambda t: len(t[1]))
        recipe, miss = missing[0]
        bits: list[str] = []
        for ing in miss[:2]:
            bits.append(f"{ing['name']} ← {self.explain(ing['name'], items, fluids, power, depth + 1, seen | {target})}")
        crafted_in = recipe.get("crafted_in")
        if crafted_in and crafted_in not in items:
            bits.append(f"atelier {crafted_in} ← {self.explain(crafted_in, items, fluids, power, depth + 1, seen | {target})}")
            return f"{target} ({recipe['name']}): " + " ; ".join(bits)
        b = self.buildings_db.get(crafted_in) if crafted_in else None
        if b is not None:
            et = getattr(b, "energy_type", "burner")
            if et == "electric" and not power:
                bits.append(f"électricité absente (générateur/pylône non obtenables)")
            elif et == "burner" and not self._fuel_obtainable(items):
                bits.append("combustible absent")
            elif et == "heat" and not self._heat_chain_ok(items):
                bits.append("chaîne chaleur absente (source/transport)")
        return f"{target} ({recipe['name']}): " + " ; ".join(bits) if bits else f"{target} (recette incomplète)"


def play(db: VanillaDB, seed: dict) -> ReplayReport:
    """Joue la seed avec un joueur simulé (API courte)."""
    return FakePlayer(db, seed).play()