"""Audit des TAGS de bâtiments (programme de vérification).

Vérifie qu'aucun bâtiment n'est « mort » : chaque tag producteur doit être
routé (consommé par une décision du générateur), chaque machine à recette
cachée doit être un fabricateur à recette fixe, et les invariants
d'orthogonalité des tags doivent tenir.

``audit_building_tags(db)`` renvoie un ``AuditReport``. Le CLI `randputf
audit` exit 1 si des violations sont trouvées.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tool.common.db import (
    VanillaDB,
    has_hidden_recipe,
    is_fixed_crafter,
    is_fixed_fluid_crafter,
)

ROLE_TAGS = ("is_research", "is_crafter", "is_generator", "is_distribution",
             "is_extractor", "is_other")

# Chaque invariant (tags §§1-8) : s'il est faux sur un bâtiment tagué, le
# prédicat produit une violation d'audit.
INVARIANTS = (
    # pylône ⇒ distribution (is_distribution = supply_area, surensemble).
    ("is_power_pole", lambda b: b.is_distribution,
     "pylône mais pas is_distribution (anomalie supply_area)"),
    ("is_water_extractor", lambda b: not (b.is_fluid_extractor or b.is_ground_extractor),
     "extracteur tagué sur deux mediums à la fois"),
    ("is_fluid_extractor", lambda b: not (b.is_water_extractor or b.is_ground_extractor),
     "extracteur tagué sur deux mediums à la fois"),
    ("is_ground_extractor", lambda b: not (b.is_water_extractor or b.is_fluid_extractor),
     "extracteur tagué sur deux mediums à la fois"),
    ("is_offgrid", lambda b: b.produces_electricity,
     "producteur hors-réseau sans produces_electricity"),
    ("consumes_electricity", lambda b: not (b.produces_electricity or b.is_accumulator),
     "consommateur de courant qui produit/stocke (réciproque exacte non tenue)"),
    ("produces_heat", lambda b: not b.produces_electricity,
     "producteur de chaleur ET de courant (tags orthogonaux exclusifs en vanilla)"),
    ("is_furnace", lambda b: b.is_crafter,
     "four non tagué is_crafter"),
    ("is_assembler", lambda b: b.is_crafter,
     "assembleur non tagué is_crafter"),
    ("is_chemical_plant", lambda b: b.is_crafter,
     "usine chimique non taguée is_crafter"),
    ("is_refinery", lambda b: b.is_crafter,
     "raffinerie non taguée is_crafter"),
    ("is_centrifuge", lambda b: b.is_crafter,
     "centrifugeuse non taguée is_crafter"),
    ("is_rocket_parts_crafter", lambda b: b.is_crafter,
     "silo à fusée non tagué is_crafter"),
    ("is_boiler", lambda b: b.is_crafter and b.has_hidden_recipe,
     "chaudière non taguée is_crafter / sans recette cachée"),
    ("is_heat_exchanger", lambda b: b.is_crafter and b.has_hidden_recipe,
     "échangeur non tagué is_crafter / sans recette cachée"),
    ("is_solar", lambda b: b.produces_electricity,
     "panneau solaire sans produces_electricity"),
    ("is_reactor", lambda b: b.produces_heat and is_fixed_crafter(b),
     "réacteur sans produces_heat ou non routé (recette fixe item)"),
    # pumpjack est un mining-drill de type : toute foreuse doit être extracteur,
    # et le pumpjack un extracteur de fluide.
    ("is_mining_drill", lambda b: b.is_extractor,
     "foreuse (mining-drill) non taguée extracteur"),
    ("is_pumpjack", lambda b: b.is_extractor and b.is_fluid_extractor,
     "pumpjack doit être extracteur de fluide"),
    ("is_offshore_pump", lambda b: b.is_extractor and b.is_water_extractor,
     "pompe offshore doit être extracteur d'eau"),
    # --- §7 : combat & défense (orthogonaux au rôle is_other) ---
    ("is_turret", lambda b: (b.is_gun_turret or b.is_laser_turret
                             or b.is_flame_turret or b.is_artillery),
     "tourelle taguée sans famille (union des 4 types)"),
    ("is_gun_turret", lambda b: b.is_turret and b.is_other,
     "tourelle balistique hors union turret / rôle productif"),
    ("is_laser_turret", lambda b: b.is_turret and b.energy_type == "electric"
     and b.consumes_electricity and b.is_other,
     "tourelle laser sans consommation réseau / rôle productif"),
    ("is_flame_turret", lambda b: b.is_turret and b.is_other,
     "tourelle à flamme hors union turret / rôle productif"),
    ("is_artillery", lambda b: b.is_turret and b.is_other,
     "artillerie hors union turret / rôle productif"),
    ("is_defensive_wall", lambda b: b.is_other,
     "muraille/porte taguée rôle productif"),
    ("is_landmine", lambda b: b.is_other,
     "mine taguée rôle productif"),
    ("is_combat_robot", lambda b: not b.is_robot and b.is_other,
     "robot de combat confondu avec is_robot (§2 logistique)"),
    # --- §8 : signal-réseau & électronique ---
    # `energy_source` absent du dump pour constant-combinator, power-switch et
    # display-panel (gap d'export) : la consommation réseau n'est vérifiable
    # que là où l'énergie est exportée ; sinon l'invariant porte sur le typage.
    ("is_circuit_combinator", lambda b: b.is_circuit_io and b.is_other
     and b.consumes_electricity,
     "combinator hors is_circuit_io / sans consommation réseau"),
    ("is_constant_combinator", lambda b: b.is_circuit_io and b.is_other,
     "émetteur constant hors is_circuit_io ou rôle productif"),
    ("is_circuit_io", lambda b: b.is_other,
     "entité circuits avec rôle productif"),
    ("is_rgb_lamp", lambda b: b.consumes_electricity and b.is_other,
     "lampe sans consommation réseau / rôle productif"),
    ("is_radar", lambda b: b.consumes_electricity and b.is_other,
     "radar sans consommation réseau / rôle productif"),
)


@dataclass
class AuditReport:
    violations: list[str] = field(default_factory=list)
    tag_counts: dict[str, int] = field(default_factory=dict)
    untagged: list[str] = field(default_factory=list)
    unrouted_hidden_recipes: list[str] = field(default_factory=list)
    buildings_checked: int = 0
    item_violations: list[str] = field(default_factory=list)
    item_tag_counts: dict[str, int] = field(default_factory=dict)
    uncraftable_violations: list[str] = field(default_factory=list)
    items_checked: int = 0

    @property
    def ok(self) -> bool:
        return not (self.violations or self.item_violations)


def audit_building_tags(db: VanillaDB) -> AuditReport:
    """Audite tous les bâtiments de ``db`` : violations d'invariants, machines
    à recette cachée non routées, comptage par tag."""
    report = AuditReport()

    for bname, b in db.buildings.items():
        report.buildings_checked += 1

        # 1. Tout bâtiment a au moins un rôle fonctionnel.
        roles = [t for t in ROLE_TAGS if getattr(b, t, False)]
        if not roles:
            report.untagged.append(bname)
            report.violations.append(f"{bname} : aucun rôle fonctionnel")

        # 2. Tags d'orthogonalité/cohérence.
        for tag, pred, msg in INVARIANTS:
            if getattr(b, tag, False) and not pred(b):
                report.violations.append(f"{bname} ({tag}) : {msg}")

        # 3. Machine à recette cachée ⇒ doit être routée (is_fixed_crafter).
        if has_hidden_recipe(b) and not is_fixed_crafter(b):
            report.unrouted_hidden_recipes.append(bname)
            report.violations.append(
                f"{bname} : has_hidden_recipe mais non routé (is_fixed_crafter "
                "faux) — bâtiment à sortie recevable jamais recetté"
            )

        # 4. Un fabricateur fluide doit bien être un fabricateur (sous-ensemble).
        if is_fixed_fluid_crafter(b) and not is_fixed_crafter(b):
            report.violations.append(
                f"{bname} : is_fixed_fluid_crafter hors is_fixed_crafter (incohérent)"
            )

        # Comptage des tags activés (champs booléens is_*/produces_*/...).
        for tagname in dir(b):
            if not tagname.startswith("is_") and not tagname.startswith("produces_"):
                continue
            if getattr(b, tagname, False):
                report.tag_counts[tagname] = report.tag_counts.get(tagname, 0) + 1

    return report


# Invariants §9 (items). ``is_science_pack`` est un raffinage de ``is_tool``
# (les science packs SONT des objets de type ``tool``) : implication, pas
# orthogonalité.
ITEM_INVARIANTS = (
    ("is_science_pack", lambda i: i.is_tool,
     "science-pack non tagué is_tool (raffinage impossible)"),
    ("is_environmental", lambda i: not i.is_virtual_item,
     "item à la fois environnemental et virtuel (orthogonalité)"),
    ("is_module", lambda i: not (i.is_capsule_throwable or i.is_virtual_item),
     "module tagué capsule/virtuel (types disjoints)"),
    ("is_capsule_throwable", lambda i: not i.is_virtual_item,
     "capsule lançable taguée virtuelle (types disjoints)"),
    ("is_gun", lambda i: not i.is_virtual_item,
     "arme taguée virtuelle (types disjoints)"),
)


def audit_item_tags(db: VanillaDB) -> AuditReport:
    """Audite les tags §9 des items : orthogonalité + craftabilité. Un item
    environnemental (récolté à la main) ou virtuel (blueprint/planner) NE DOIT
    PAS avoir de recette vanilla le produisant — sinon le générateur créerait
    un fake cycle (recette → item « du monde »)."""
    report = AuditReport()

    # Recettes produisant chaque item (type+name), une seule fois par item.
    produced: dict[str, set[str]] = {}
    for r in db.recipes.values():
        for ptype, pname, _amount in r.products:
            if ptype == "item":
                produced.setdefault(pname, set()).add(r.name)

    for iname, i in db.items.items():
        report.items_checked += 1

        for tag, pred, msg in ITEM_INVARIANTS:
            if getattr(i, tag, False) and not pred(i):
                report.item_violations.append(f"{iname} ({tag}) : {msg}")

        if i.is_environmental and iname in produced:
            report.uncraftable_violations.append(
                f"{iname} : environnemental mais recette le produisant : "
                f"{', '.join(sorted(produced[iname]))}"
            )
            report.item_violations.append(
                f"{iname} : environnemental produit par une recette (cycle)"
            )
        if i.is_virtual_item and iname in produced:
            report.item_violations.append(
                f"{iname} : virtuel mais recette le produisant : "
                f"{', '.join(sorted(produced[iname]))}"
            )

        for tagname in dir(i):
            if not tagname.startswith("is_") or tagname in ("name",):
                continue
            if getattr(i, tagname, False):
                report.item_tag_counts[tagname] = report.item_tag_counts.get(tagname, 0) + 1

    return report


def summarize_tags(db: VanillaDB, report: AuditReport) -> str:
    lines = [
        f"Bâtiments audités : {report.buildings_checked}",
        f"Tags distincts activés : {len(report.tag_counts)}",
        "Répartition (bâtiments) :",
    ]
    for tag in sorted(report.tag_counts, key=lambda t: -report.tag_counts[t]):
        lines.append(f"  {tag}: {report.tag_counts[tag]}")

    lines.append("")
    lines.append(f"Items audités : {report.items_checked}")
    lines.append(f"Tags items activés : {len(report.item_tag_counts)}")
    for tag in sorted(report.item_tag_counts, key=lambda t: -report.item_tag_counts[t]):
        lines.append(f"  {tag}: {report.item_tag_counts[tag]}")

    for label, lst in (
        ("Sans rôle fonctionnel", report.untagged),
        ("Recettes cachées non routées", report.unrouted_hidden_recipes),
        ("Items environnementaux produits par une recette", report.uncraftable_violations),
    ):
        if lst:
            lines.append(f"{label} : {', '.join(lst)}")

    all_violations = report.violations + report.item_violations
    if all_violations:
        lines.append("V I O L A T I O N S :")
        lines += [f"  - {v}" for v in all_violations]
    else:
        lines.append("AUCUNE violation — tous les tags (bâtiments §1-8 + items §9) sont cohérents")
    return "\n".join(lines)