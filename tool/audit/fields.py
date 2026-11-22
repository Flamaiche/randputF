"""Classifie les champs présents dans un dump selon leur exploitation."""
from __future__ import annotations

from collections import Counter
from typing import Any

CONSUMED = "Consommé"
PARTIAL = "Partiel"
TODO = "À consommer"
COSMETIC = "Cosmétique"

_SECTIONS = (
    "meta",
    "inventory",
    "tiles",
    "items",
    "fluids",
    "entities",
    "recipes",
    "technologies",
    "mod_data",
)

_CLASSIFICATION: dict[tuple[str, str], tuple[str, str]] = {
    ("meta", "game_version"): (CONSUMED,         "Version affichée et fournie au titre."),
    ("meta", "game_version_numeric"): (CONSUMED, "Graine de base de la VanillaDB."),
    ("meta", "schema_version"): (CONSUMED, "Version du format contrôlée à l'acquisition."),
    ("meta", "exporter_version"): (CONSUMED, "Version de l'exporteur affichée."),
    ("meta", "active_mods"): (CONSUMED, "Liste des mods affichée et utilisée comme source."),
    ("meta", "mod_label"): (CONSUMED, "Nom de source dans la CLI et les rapports."),
    ("meta", "mod_label_full"): (CONSUMED, "Libellé long de source."),
    ("meta", "dump_file"): (CONSUMED, "Chemin d'origine rappelé par la CLI."),
    ("meta", "seed"): (CONSUMED, "Identifiant conservé dans la seed exportée."),

    ("tiles", "collision_layers"): (CONSUMED, "Couches de tuiles résolues en fluides de lac."),
    ("tiles", "fluid"): (CONSUMED, "Fluide produit par une tuile de lac."),
    ("tiles", "name"): (COSMETIC, "Nom de tuile affiché."),
    ("tiles", "type"): (COSMETIC, "Type de prototype affiché."),

    ("items", "type"): (CONSUMED, "Type d'item (munitions, outils, science…)."),
    ("items", "subgroup"): (PARTIAL, "Sous-groupe utilisé par l'heuristique environnementale seulement."),
    ("items", "place_result"): (CONSUMED, "Lien item → bâtiment."),
    ("items", "fuel_value"): (CONSUMED, "Choix et puissance du combustible."),
    ("items", "fuel_categories"): (CONSUMED, "Compatibilité combustible/bâtiment."),
    ("items", "fuel_category"): (CONSUMED, "Repli des dumps à catégorie unique."),
    ("items", "burnt_result"): (CONSUMED, "Résidu obtenable dès que le combustible l'est."),
    ("items", "stack_size"): (CONSUMED, "Stackabilité réelle des recettes."),
    ("items", "ammo_category"): (CONSUMED, "Catégorie de munitions."),
    ("items", "rocket_launch_products"): (CONSUMED, "Produits et quantités de lancement exploités."),
    ("items", "used_by_labs"): (CONSUMED, "Source supplémentaire de packs de science."),
    ("items", "science_capacity"): (CONSUMED, "Capacité minimale requise pour un pack de lab."),
    ("items", "main_product"): (TODO, "Produit principal d'item non exploité."),
    ("items", "display_type"): (COSMETIC, "Affichage uniquement."),
    ("items", "order"): (COSMETIC, "Tri d'affichage uniquement."),
    ("items", "base_color"): (COSMETIC, "Couleur d'affichage."),
    ("items", "flow_color"): (COSMETIC, "Couleur d'affichage."),

    ("fluids", "type"): (CONSUMED, "Type de slot fluide."),
    ("fluids", "subgroup"): (PARTIAL, "Sous-groupe utilisé par l'heuristique environnementale seulement."),
    ("fluids", "fuel_value"): (CONSUMED, "Combustible fluide éventuel."),
    ("fluids", "default_temperature"): (CONSUMED, "Température par défaut conservée."),
    ("fluids", "rocket_launch_products"): (PARTIAL, "Produits de lancement exploités."),
    ("fluids", "max_temperature"): (COSMETIC, "Aucune dimension température dans le modèle."),
    ("fluids", "heat_capacity"): (COSMETIC, "Aucun bilan thermique dans le modèle."),
    ("fluids", "gas_temperature"): (COSMETIC, "Aucun bilan thermique dans le modèle."),
    ("fluids", "emissions_multiplier"): (COSMETIC, "Aucun modèle d'émissions."),
    ("fluids", "base_color"): (COSMETIC, "Couleur d'affichage."),
    ("fluids", "flow_color"): (COSMETIC, "Couleur d'affichage."),
    ("fluids", "visualization_color"): (COSMETIC, "Couleur d'affichage."),
    ("fluids", "display_type"): (COSMETIC, "Affichage uniquement."),
    ("fluids", "order"): (COSMETIC, "Tri d'affichage uniquement."),

    ("entities", "type"): (CONSUMED, "Type API utilisé par les tags capacitaires."),
    ("entities", "crafting_categories"): (CONSUMED, "Catégories de craft et chaîne de lancement."),
    ("entities", "resource_categories"): (CONSUMED, "Milieu d'extraction."),
    ("entities", "crafting_speed"): (CONSUMED, "Cadence des ateliers."),
    ("entities", "productivity"): (CONSUMED, "Productivité des ateliers."),
    ("entities", "energy_source"): (CONSUMED, "Type, catégories de carburant et buffer lus."),
    ("entities", "energy_source.buffer_capacity"): (CONSUMED, "Stockage d'énergie générique et métadonnée du bâtiment."),
    ("entities", "fluidboxes"): (CONSUMED, "Filtres input/output distincts convertis en recettes."),
    ("entities", "fluidboxes.detail"): (CONSUMED, "Filtres détaillés et production_type exploités."),
    ("entities", "tile_buildability_rules"): (PARTIAL, "required_tiles résolus en fluide ; tuiles collisionnelles ignorées."),
    ("entities", "mineable_properties"): (CONSUMED, "Produits, temps et fluide requis normalisés dans la seed."),
    ("entities", "mineable_products"): (CONSUMED, "Ressources brutes du graphe."),
    ("entities", "mineable_time"): (CONSUMED, "Temps d'extraction conservé."),
    ("entities", "required_fluid"): (CONSUMED, "Fluide requis par l'extraction."),
    ("entities", "fluid_amount"): (CONSUMED, "Quantité de fluide requise."),
    ("entities", "resource_category"): (CONSUMED, "Catégorie de forage inférée."),
    ("entities", "pumped_fluid"): (CONSUMED, "Fluide de lac résolu."),
    ("entities", "pumped_fluids"): (CONSUMED, "Ensemble des fluides de lac."),
    ("entities", "rocket_parts_required"): (CONSUMED, "Silos détectés via la catégorie rocket-building."),
    ("entities", "lab_inputs"): (CONSUMED, "Packs de science et bâtiments de recherche."),
    ("entities", "target_temperature"): (CONSUMED, "Atelier à température cible."),
    ("entities", "has_heat_output"): (CONSUMED, "Producteur de chaleur."),
    ("entities", "max_power_output"): (CONSUMED, "Producteur d'électricité."),
    ("entities", "supply_area_distance"): (CONSUMED, "Pylônes électriques."),
    ("entities", "guns"): (CONSUMED, "Armes montées exclues des armes à pied."),
    ("entities", "auto_select"): (CONSUMED, "Machine sans sélecteur de recette."),
    ("entities", "ingredient_count"): (CONSUMED, "Nombre d'emplacements d'ingrédients."),
    ("entities", "items_to_place_this"): (CONSUMED, "Lien bâtiment → item de construction."),
    ("entities", "energy_usage"): (CONSUMED, "Puissance du bâtiment lue par le rapport de complexité."),
    ("entities", "mining_speed"): (CONSUMED, "Cadence de foreuse lue par le rapport de complexité."),
    ("entities", "selection_box"): (COSMETIC, "Géométrie d'affichage."),
    ("entities", "order"): (COSMETIC, "Tri d'affichage."),

    ("recipes", "category"): (CONSUMED, "Atelier de référence et chaîne de fusée."),
    ("recipes", "ingredients"): (CONSUMED, "Coûts de craft."),
    ("recipes", "products"): (CONSUMED, "Produits exploités ; amount absent normalisé à 1."),
    ("recipes", "results"): (CONSUMED, "Alias de products normalisé."),
    ("recipes", "enabled"): (CONSUMED, "Recettes actives au chargement."),
    ("recipes", "hidden"): (CONSUMED, "Prototypes neutralisés ou recettes cachées actives."),
    ("recipes", "energy"): (CONSUMED, "Temps de craft."),
    ("recipes", "crafting_categories"): (CONSUMED, "Catégories conservées dans la seed."),
    ("recipes", "crafting_speed"): (CONSUMED, "Vitesse de craft conservée."),
    ("recipes", "main_product"): (CONSUMED, "Produit principal prioritaire pour la pièce de fusée et conservé dans la seed."),
    ("recipes", "order"): (COSMETIC, "Tri d'affichage."),

    ("technologies", "unit"): (CONSUMED, "Coût de recherche."),
    ("technologies", "prerequisites"): (CONSUMED, "Ordre topologique."),
    ("technologies", "effects"): (CONSUMED, "Déblocages de recettes et bâtiments."),
    ("technologies", "research_trigger"): (CONSUMED, "Déclencheurs item/entité/fluide/orbite exploités."),
    ("technologies", "research_unit_count_formula"): (PARTIAL, "Formule conservée dans la seed ; techs finies via unit.count."),
    ("technologies", "enabled"): (CONSUMED, "Technologies actives."),
    ("technologies", "hidden"): (CONSUMED, "Technologies neutralisées exclues."),
    ("technologies", "order"): (COSMETIC, "Tri reconstruit depuis les prérequis."),

    ("mod_data", "name"): (COSMETIC, "Nom du bloc de données affiché."),
    ("mod_data", "data_type"): (CONSUMED, "Registre canonique des lacs reconnu par forme."),
    ("mod_data", "data"): (PARTIAL, "Mapping tuile → fluide exploité ; autres registres affichés."),
    ("mod_data", "data.source"): (CONSUMED, "Tuile source du registre de lacs."),
    ("mod_data", "data.results"): (CONSUMED, "Tuiles de lac résultantes."),
    ("mod_data", "data.fluids"): (CONSUMED, "Fluides associés aux tuiles de lac."),
    ("mod_data", "data.farm_buildings"): (COSMETIC, "Contrat affiché dans le navigateur, sans effet générique."),
    ("mod_data", "data.digosaurus"): (COSMETIC, "Payload affiché dans le navigateur, sans contrat générique."),
    ("mod_data", "data.creatures"): (COSMETIC, "Liens de collecte affichés, sans contrat générique."),
    ("mod_data", "data.dig_sites"): (COSMETIC, "Géométrie de carte sans effet sur le graphe."),
    ("mod_data", "data.recipe_gui"): (COSMETIC, "Étiquettes UI et icônes."),
}


def _entries(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, list):
        return value
    return []


def _fields(dump: dict) -> list[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for section in _SECTIONS:
        value = dump.get(section)
        if not isinstance(value, dict):
            continue
        if section == "inventory":
            found.update((section, str(key)) for key in value)
            continue
        found.update((section, str(key)) for entry in _entries(value) if isinstance(entry, dict) for key in entry)
        if section == "mod_data":
            for entry in _entries(value):
                if isinstance(entry, dict) and isinstance(entry.get("data"), dict):
                    found.update(("mod_data", f"data.{key}") for key in entry["data"])
    for section in ("items", "fluids", "entities", "recipes", "technologies"):
        for entry in _entries(dump.get(section)):
            if not isinstance(entry, dict):
                continue
            source = entry.get("energy_source")
            if isinstance(source, dict) and "buffer_capacity" in source:
                found.add((section, "energy_source.buffer_capacity"))
            boxes = entry.get("fluidboxes")
            if isinstance(boxes, dict) and isinstance(boxes.get("detail"), dict):
                found.add((section, "fluidboxes.detail"))
    return sorted(found)


def classify_dump_fields(dump: dict) -> dict:
    """Retourne le classement des champs présents dans ``dump``."""
    fields: list[dict] = []
    for section, field in _fields(dump):
        if section == "inventory":
            status, reason = COSMETIC, "Table du navigateur HTML, sans effet sur le graphe."
        else:
            status, reason = _CLASSIFICATION.get(
                (section, field),
                (TODO, "Champ présent mais non classé : à examiner."),
            )
        fields.append(
            {
                "section": section,
                "field": field,
                "status": status,
                "reason": reason,
            }
        )
    counts = Counter(field["status"] for field in fields)
    return {
        "counts": {
            CONSUMED: counts[CONSUMED],
            PARTIAL: counts[PARTIAL],
            TODO: counts[TODO],
            COSMETIC: counts[COSMETIC],
        },
        "fields": fields,
    }


__all__ = ["CONSUMED", "PARTIAL", "TODO", "COSMETIC", "classify_dump_fields"]
