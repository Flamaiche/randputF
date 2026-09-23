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

        # Mapping extracteur (recette randputf-<extracteur>) -> ressources
        # tirées (source de vérité posée par C3, ``seed["extractor_timing"]``).
        timing = seed.get("extractor_timing") or {}
        self.extractors: list[tuple[str, list[dict]]] = list(
            timing.get("extractors", {}).items()
        )

        # Fluides de lac (pompés par pompe offshore, énergie void) et patchs.
        map_ = seed.get("map") or {}
        self.lake_resources: set[str] = {
            la["resource"] for la in map_.get("lakes") or []
        }
        self.patch_resources: set[str] = {
            p["resource"] for p in map_.get("patches") or []
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

    # ── Préparation ───────────────────────────────────────────────────────

    def _prep_db(self) -> None:
        self.items_db = self.db.items
        self.buildings_db = self.db.buildings

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
        """Items/fluides de départ (sources + kit), avant recettes."""
        items = set(ENVIRONMENTAL_ITEMS) & set(self.items_db)
        items |= self.kit
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
            report.power_available, report.power_generator = power, generator
            # Le lab reçoit les packs (garanti au starter, §8) — garde-fou.
            if "lab" not in items:
                report.blocker = Blocker(tech_id, "lab", "lab")
                break
            # Déclencheur façon prologue (§7) : item crafté à la main.
            trigger = tech.get("craft_trigger")
            if trigger and trigger not in items:
                reason = self.explain(trigger, items, fluids, power)
                report.blocker = Blocker(tech_id, "trigger", trigger, reason)
                break
            # Coûts en science packs (§13).
            costs = tech.get("unit", {}).get("ingredients") or []
            stuck = next((c for c in costs if c["name"] not in items), None)
            if stuck is not None:
                reason = self.explain(stuck["name"], items, fluids, power)
                report.blocker = Blocker(tech_id, "cost", stuck["name"], reason)
                break
            # Recherche : on débloque les effets de la tech.
            self.researched.add(tech_id)
            self.unlocked.update(self._unlocks_of(tech))
            report.researched_order.append(tech_id)
        report.researched = len(self.researched)
        report.all_techs_researched = report.researched == len(self.techs)
        # Victoire : chaîne fusée atteignable une fois l'arbre consommé.
        items, fluids, power, generator = self.closure()
        report.power_available, report.power_generator = power, generator
        report.obtainable_items, report.obtainable_fluids = items, fluids
        report.satellite_obtainable = "satellite" in items
        report.victory = all(v in items for v in VICTORY_ITEMS)
        return report

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