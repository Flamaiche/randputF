"""Rapport « partie simulée » : minage, crafts, sous-produits, déclencheurs."""
from __future__ import annotations

import hashlib
import html as _html
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tool.common.version import VERSION
from tool.exporters.complexity_graph import analyze_playthrough, render_complexity_html
from tool.exporters.html_ui import (
    FOLD_TABLES_CSS,
    FOLD_TABLES_SCRIPT,
    TIP_HTML,
    UI_SCRIPT,
    th as _th,
)
from tool.exporters.mod_seed import build_vanilla_seed, tag_progression

_PLAYTHROUGH_CSS = '\n.scroll{overflow:auto;max-height:70vh;scrollbar-gutter:stable}\n.table-fold summary{cursor:pointer;color:var(--accent);font-weight:600;\n  margin-bottom:8px}\n.bar-wrap{margin-top:8px}\n.bar-row{display:flex;align-items:center;gap:10px;margin:5px 0}\n.bar-name{width:190px;flex:none;font-size:11px;color:var(--muted);\n  overflow-wrap:anywhere}\n.bar-bg{flex:1;height:10px;background:rgba(255,255,255,.08);\n  border-radius:5px;overflow:hidden}\n.bar-fill{height:100%;border-radius:5px}\n.bar-val{width:90px;flex:none;font-size:11px;text-align:right;\n  font-variant-numeric:tabular-nums}\n'


def _esc(value: Any) -> str:
    """Échappe une valeur pour une insertion HTML sûre.

    ``value`` est converti en chaîne puis échappé. Retourne le texte prêt à être inséré dans le document.
    """
    return _html.escape(str(value))


def _fmt(value: Any) -> str:
    """Formate un nombre pour l'affichage.

    Les entiers sont séparés par des espaces ; les autres valeurs gardent au
    plus deux décimales utiles. Les valeurs non numériques sont renvoyées
    telles quelles.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}".replace(",", " ")
    return f"{number:,.2f}".replace(",", " ").rstrip("0").rstrip(".")


def _write(out: Any, text: str) -> None:
    """Écrit un document HTML vers un chemin, un fichier ouvert ou un objet chemin.

    Les dossiers parents sont créés au besoin. Cette souplesse permet aux
    appelants CLI d'écrire sur disque ou dans un flux de test.
    """
    if isinstance(out, Path):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return
    if hasattr(out, "write"):
        out.write(text)
        return
    path = Path(str(out))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _raw_resources(dump: dict) -> list[str]:
    """Ressources brutes : uniquement ce que le dump déclare.

    Gisements (``type == "resource"``), produits minables d'entités
    minables (arbres → bois) et fluides pompés (``pumped_fluid``).
    """
    entities = dump.get("entities") or {}
    raw: set[str] = set()
    for name, entry in entities.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("type") == "resource":
            raw.add(str(name))
        props = entry.get("mineable_properties")
        if isinstance(props, dict):
            for product in props.get("products") or []:
                product_name = (
                    product.get("name") if isinstance(product, dict) else product
                )
                if product_name:
                    raw.add(str(product_name))
        pumped = entry.get("pumped_fluid")
        if pumped:
            raw.add(str(pumped))
        for fluid in entry.get("pumped_fluids") or ():
            raw.add(str(fluid))
    return sorted(raw)


def _universe(dump: dict, seed: dict, analysis: dict) -> dict[str, str]:
    """Classe les noms du dump en items, fluides ou ressources.

    ``dump`` fournit les items/fluides, ``seed`` les ressources brutes et ``analysis`` les données de complexité. Retourne ``{nom: type}`` pour l'affichage et les filtres.
    """
    fluids = {str(name) for name in dump.get("fluids") or {}}
    kinds: dict[str, str] = {}
    for name in dump.get("items") or {}:
        kinds[str(name)] = "item"
    for name in fluids:
        kinds[name] = "fluide"
    for name in (seed.get("pools") or {}).get("raw_resources") or []:
        kinds.setdefault(
            str(name), "fluide" if str(name) in fluids else "ressource"
        )
    for recipe in seed.get("recipes") or []:
        for key in ("ingredients", "results"):
            for entry in recipe.get(key) or []:
                if not isinstance(entry, dict) or not entry.get("name"):
                    continue
                name = str(entry["name"])
                kinds.setdefault(
                    name, "fluide" if name in fluids else "item"
                )
    for name in analysis.get("item_stats") or {}:
        kinds.setdefault(
            str(name), "fluide" if str(name) in fluids else "item"
        )
    for name, entry in (dump.get("entities") or {}).items():
        if isinstance(entry, dict) and entry.get("type") == "resource":
            kinds.setdefault(str(name), "ressource")
    return kinds


def _rows(dump: dict, seed: dict, analysis: dict) -> list[dict]:
    """Construit une ligne par item, fluide ou ressource brute.

    Chaque ligne reprend les volumes, temps, énergie et tags calculés par
    l'analyse, puis les trie par volume simulé décroissant (produit +
    consommé) pour mettre en avant les éléments dominants.
    """
    stats = analysis.get("item_stats") or {}
    kinds = _universe(dump or {}, seed, analysis)
    rows: list[dict] = []
    for name, kind in kinds.items():
        values = stats.get(name) or {}
        rows.append(
            {
                "name": name,
                "kind": kind,
                "mined": values.get("mined", 0),
                "mining_seconds": values.get("mining_seconds", 0),
                "produced": values.get("produced", 0),
                "consumed": values.get("consumed", 0),
                "crafts": values.get("crafts", 0),
                "craft_seconds": values.get("craft_seconds", 0),
                "power_kw": values.get("power_kw", 0),
                "energy_kj": values.get("energy_kj", 0),
                "external": values.get("external", 0),
                "tags": _item_tags(name, dump, seed),
            }
        )
    rows.sort(key=lambda row: (-(row["produced"] + row["consumed"]), row["name"]))
    return rows


def _stat(label: str, value: str, cls: str = "", hint: str = "") -> str:
    """Génère une tuile du bandeau de statistiques.

    ``cls`` choisit la couleur de la valeur et ``hint`` ajoute une infobulle
    discrète sous celle-ci.
    """
    hint_html = f'<div class="hint">{_esc(hint)}</div>' if hint else ""
    return (
        f'<div class="stat"><div class="lab">{_esc(label)}</div>'
        f'<div class="val {cls}">{_esc(value)}</div>{hint_html}</div>'
    )


def _item_tags(name: str, dump: dict, seed: dict | None = None) -> str:
    """Résume les tags d'un item ou d'un fluide pour le tableau.

    Les informations viennent uniquement du dump et, si elle est fournie, de
    la seed : type d'affichage, sous-groupe, rôle « science » ou
    « progression » et valeur de carburant pour les fluides.
    """
    items = dump.get("items", {})
    fluids = dump.get("fluids", {})
    entry = items.get(name) or fluids.get(name)
    if not isinstance(entry, dict):
        return "—"
    parts = [_esc(entry.get("display_type") or entry.get("type")) or ""]
    # Rôles de progression posés sur le seed (faits du dump + fermeture de
    # l'analyse) : « science » = consommé par les recherches/lab,
    # « progression » = dans la chaîne qui fait avancer le jeu.
    seed_entry = None
    if isinstance(seed, dict):
        for section in ("items", "fluids"):
            candidate = (seed.get(section) or {}).get(name)
            if isinstance(candidate, dict):
                seed_entry = candidate
                break
    if seed_entry is not None:
        if seed_entry.get("is_science_pack"):
            parts.append("science")
        if seed_entry.get("is_progression"):
            parts.append("progression")
    subgroup = entry.get("subgroup")
    if subgroup:
        parts.append(_esc(subgroup))
    if name in fluids:
        fv = entry.get("fuel_value")
        if fv:
            parts.append(_esc(fv))
    if any(parts):
        return " / ".join(p for p in parts if p)
    return "—"


def _bar_list(title: str, pairs: list[tuple[str, float]], color: str) -> str:
    """Génère un classement en barres horizontales.

    ``pairs`` contient les noms et volumes à afficher ; les barres sont
    normalisées sur la plus grande valeur pour rester lisibles.
    """
    if not pairs:
        return f'<h3>{_esc(title)}</h3><p class="muted">Aucune donnée.</p>'
    top = max(value for _name, value in pairs) or 1
    items: list[str] = []
    for name, value in pairs:
        width = max(2.0, value / top * 100)
        items.append(
            f'<div class="bar-row" data-tip="{_esc(name)} : {_esc(_fmt(value))}">'
            f'<div class="bar-name">{_esc(name)}</div>'
            f'<div class="bar-bg"><div class="bar-fill" style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="bar-val">{_esc(_fmt(value))}</div></div>'
        )
    return f'<h3>{_esc(title)}</h3><div class="bar-wrap">' + "".join(items) + "</div>"


def _tags(items: list[str], empty: str) -> str:
    """Affiche une liste de valeurs en badges HTML.

    ``empty`` est le texte affiché quand la liste est vide, ce qui évite les
    sections muettes dans le rapport.
    """
    if not items:
        return f'<span class="muted">{_esc(empty)}</span>'
    return "".join(f'<span class="tag">{_esc(item)}</span>' for item in items)


def _info_sections(seed: dict, analysis: dict) -> str:
    """Assemble les blocs d'information secondaires du rapport.

    On y trouve les bâtiments utilisés, les ressources brutes disponibles et
    non utilisées, ainsi que les recettes encore verrouillées à la fin de la
    simulation.
    """
    buildings = analysis.get("buildings") or []
    raws = analysis.get("raw_resources") or []
    unused = analysis.get("unused_raw_resources") or []
    locked = analysis.get("locked_recipes") or []
    raw_html = _tags(raws, "Aucune ressource brute.")
    if unused:
        raw_html += (
            '<div class="muted">Non utilisées : '
            + ", ".join(_esc(name) for name in unused)
            + "</div>"
        )
    return (
        f'<div class="two"><div><h3>Bâtiments</h3>{_tags(buildings, "Aucun bâtiment crafté.")}</div>'
        f'<div><h3>Ressources brutes</h3>{raw_html}</div></div>'
        f'<div class="bar-wrap"><h3>Recettes avant déblocage</h3>{_tags(locked, "Aucune : tout est débloqué.")}</div>'
    )


def _table(rows: list[dict]) -> str:
    """Construit le tableau détaillé par item et fluide.

    La colonne « Externe » n'apparaît que si au moins une fourniture hors
    chaîne existe. Les cellules numériques portent leur valeur brute pour que
    le tri JavaScript reste exact.
    """
    has_external = any(row.get("external", 0) > 0 for row in rows)
    head_parts = [
        _th("Item / fluide", "name", "text", "Nom de l'item ou du fluide."),
        _th("Type", "kind", "text", "Item, fluide ou ressource brute."),
        _th("Miné", "mined", "num", "Quantité extraite du sol."),
        _th("Minage (s)", "mining_seconds", "num", "Temps de minage simulé."),
        _th(
            "Produit",
            "produced",
            "num",
            "Quantité produite (craft, minage ou fourniture externe).",
        ),
        _th(
            "Consommé",
            "consumed",
            "num",
            "Quantité consommée (crafts, recherche, lancement).",
        ),
        _th("Crafts", "crafts", "num", "Crafts dont cet item est la cible."),
        _th("Temps craft (s)", "craft_seconds", "num", "Temps machine cumulé."),
        _th(
            "Puissance (kW)",
            "power_kw",
            "num",
            "Puissance du bâtiment qui produit l'item (energy_usage × 0,06).",
        ),
        _th(
            "Énergie (kJ)",
            "energy_kj",
            "num",
            "Énergie consommée : puissance × temps de craft ou de minage.",
        ),
    ]
    if has_external:
        head_parts.append(
            _th(
                "Externe",
                "external",
                "num",
                "Fourni hors chaîne (pompage, récolte, orbite).",
            )
        )
    head_parts.append(
        _th("Tags", "tags", "text", "Tags associés à l'item dans le mod.")
    )
    head = "".join(head_parts)
    body: list[str] = []
    for row in rows:
        if has_external:
            external_td = (
                f"<td class='num' data-key='external' data-value='{row['external']}'>"
                f"{_esc(_fmt(row['external']))}</td>"
            )
        else:
            external_td = ""
        body.append(
            "".join(
                [
                    f"<tr><td data-key='name'>{_esc(row['name'])}</td>",
                    f"<td data-key='kind'>{_esc(row['kind'])}</td>",
                    f"<td class='num' data-key='mined' data-value='{row['mined']}'>{_esc(_fmt(row['mined']))}</td>",
                    f"<td class='num' data-key='mining_seconds' data-value='{row['mining_seconds']}'>{_esc(_fmt(row['mining_seconds']))}</td>",
                    f"<td class='num' data-key='produced' data-value='{row['produced']}'>{_esc(_fmt(row['produced']))}</td>",
                    f"<td class='num' data-key='consumed' data-value='{row['consumed']}'>{_esc(_fmt(row['consumed']))}</td>",
                    f"<td class='num' data-key='crafts' data-value='{row['crafts']}'>{_esc(_fmt(row['crafts']))}</td>",
                    f"<td class='num' data-key='craft_seconds' data-value='{row['craft_seconds']}'>{_esc(_fmt(row['craft_seconds']))}</td>",
                    f"<td class='num' data-key='power_kw' data-value='{row['power_kw']}'>{_esc(_fmt(row['power_kw']))}</td>",
                    f"<td class='num' data-key='energy_kj' data-value='{row['energy_kj']}'>{_esc(_fmt(row['energy_kj']))}</td>",
                ]
            )
            + external_td
            + f"<td class='num' data-key='tags'>{_esc(row['tags'])}</td></tr>"
        )
    return (
        "<div class='scroll'><table data-table data-default-sort='[{\"key\":\"produced\",\"dir\":-1}]'><thead><tr>"
        + head
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _fragments(seed: dict, analysis: dict, rows: list[dict]) -> dict:
    """Prépare les fragments HTML du rapport de partie simulée.

    Le résultat contient le bandeau, les barres de volumes, le tableau
    détaillé et l'éventuelle note sur les items inconnus. Les données brutes
    (analyse, lignes, seed, progression) y sont jointes pour les appelants.
    """
    header_stats = "".join(
        [
            _stat("Crafts", _fmt(analysis.get("total_crafts", 0)), "acc"),
            _stat("Produit", _fmt(analysis.get("total_produced", 0)), "ok"),
            _stat("Consommé", _fmt(analysis.get("total_consumed", 0)), "warn"),
            _stat(
                "Ressources brutes",
                _fmt(analysis.get("total_raw", 0)),
                "acc",
                "minées au total",
            ),
            _stat(
                "Temps de minage",
                _fmt(analysis.get("mining_seconds", 0)) + " s",
                "acc",
            ),
            _stat(
                "Temps de craft",
                _fmt(analysis.get("total_craft_seconds", 0)) + " s",
                "acc",
            ),
            _stat(
                "Bâtiments",
                _fmt(len(analysis.get("buildings") or [])),
                "ok",
            ),
        ]
    )
    produced = [
        (row["name"], row["produced"]) for row in rows if row["produced"] > 0
    ][:12]
    consumed = [
        (row["name"], row["consumed"]) for row in rows if row["consumed"] > 0
    ][:12]
    bars = (
        '<div class="two"><div>'
        + _bar_list("Produits (volume)", produced, "var(--ok)")
        + '</div><div>'
        + _bar_list("Consommés (volume)", consumed, "var(--warn)")
        + "</div></div>"
        + _info_sections(seed, analysis)
    )
    unknown = analysis.get("unknown_items") or []
    if unknown:
        unknown_note = (
            '<div class="note">Items sans recette ni gisement : '
            + ", ".join(_esc(name) for name in unknown)
            + "</div>"
        )
    else:
        unknown_note = ""
    return {
        "header_stats": header_stats,
        "bars": bars,
        "table": _table(rows),
        "unknown_note": unknown_note,
        "analysis": analysis,
        "rows": rows,
    }


_CACHE_SECTION = "randputf_cache"
_CACHE_ID = "playthrough_v1"
_CACHE_REQUIRED = ("item_stats", "buildings", "complexity_stats")


def _playthrough_cache_digest(seed: dict, dump: dict | None) -> str:
    payload = {
        "id": _CACHE_ID,
        "version": VERSION,
        "seed": seed,
        "dump": {key: value for key, value in (dump or {}).items() if key != _CACHE_SECTION},
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _valid_cached_analysis(analysis: Any) -> bool:
    if not isinstance(analysis, dict):
        return False
    if any(key not in analysis for key in _CACHE_REQUIRED):
        return False
    return isinstance(analysis["item_stats"], dict) and isinstance(
        analysis["complexity_stats"], dict
    )


def read_playthrough_cache(dump: dict | None, seed: dict) -> dict | None:
    """Retourne l'analyse simulée persistée si elle correspond encore à la seed."""
    if not isinstance(dump, dict):
        return None
    entry = (dump.get(_CACHE_SECTION) or {}).get(_CACHE_ID)
    if not isinstance(entry, dict):
        return None
    if entry.get("version") != VERSION:
        return None
    if entry.get("digest") != _playthrough_cache_digest(seed, dump):
        return None
    analysis = entry.get("analysis")
    return analysis if _valid_cached_analysis(analysis) else None


def write_playthrough_cache(dump: dict | None, seed: dict, analysis: dict) -> bool:
    """Persiste l'analyse simulée dans le dump et indique si le dump a changé."""
    if not isinstance(dump, dict) or not _valid_cached_analysis(analysis):
        return False
    entry = {
        "version": VERSION,
        "digest": _playthrough_cache_digest(seed, dump),
        "analysis": analysis,
    }
    cache = dump.get(_CACHE_SECTION)
    if not isinstance(cache, dict):
        cache = {}
        dump[_CACHE_SECTION] = cache
    if cache.get(_CACHE_ID) == entry:
        return False
    cache[_CACHE_ID] = entry
    return True


def playthrough_report(
    dump: dict | None,
    db: Any = None,
    *,
    seed: dict | None = None,
    title: str | None = None,
    cache: bool = True,
    on_progress: Callable[[int, str], None] | None = None,
) -> dict:
    """Produit le rapport de partie simulée sous forme de fragments et de données.

    Si ``seed`` n'est pas fournie, elle est construite depuis le dump. La
    fonction réutilise l'analyse persistée dans le dump quand elle correspond
    encore à la seed, sinon elle simule la partie et persiste le résultat.
    ``on_progress`` reçoit un pourcentage et une action.
    """
    def emit(percent: int, detail: str) -> None:
        if on_progress is not None:
            on_progress(max(0, min(100, int(percent))), detail)

    emit(0, "préparation de la simulation")
    dump = dump or {}
    if seed is None:
        emit(2, "construction de la seed")
        seed = build_vanilla_seed(dump)
    cached = read_playthrough_cache(dump, seed) if cache else None
    cache_hit = cached is not None
    cache_written = False
    if cache_hit:
        emit(5, "simulation reprise du cache du dump")
        analysis = cached
    else:
        emit(5, "simulation de la partie")
        analysis = analyze_playthrough(
            seed,
            db,
            on_progress=lambda percent, detail: emit(
                5 + percent * 65 // 100, f"simulation de la partie — {detail}"
            ),
        )
        if cache:
            cache_written = write_playthrough_cache(dump, seed, analysis)
    emit(72, "progression des tags")
    progression = tag_progression(seed, analysis)
    emit(78, "lignes du tableau")
    rows = _rows(dump, seed, analysis)
    emit(86, "fragments HTML")
    fragments = _fragments(seed, analysis, rows)
    emit(100, "rapport de partie prêt")
    fragments["seed"] = seed
    fragments["title"] = title
    fragments["progression"] = progression
    fragments["complexity_stats"] = analysis.get("complexity_stats")
    fragments["cache_hit"] = cache_hit
    fragments["cache_written"] = cache_written
    return fragments


def write_playthrough_html(dump: dict, out: Any) -> dict:
    """Écrit un document HTML autonome de la partie simulée vanilla.

    La seed est dérivée du dump, la simulation est exécutée puis rendue avec
    les styles et scripts partagés. Retourne l'analyse, les lignes, la seed et
    la progression utilisées.
    """
    from tool.exporters.complexity_graph import _CSS as _BASE_CSS

    seed = build_vanilla_seed(dump)
    analysis = analyze_playthrough(seed)
    progression = tag_progression(seed, analysis)
    rows = _rows(dump, seed, analysis)
    fragments = _fragments(seed, analysis, rows)
    game_version = (dump.get("meta") or {}).get("game_version", "inconnue")
    title = f"Factorio vanilla {game_version} — partie simulée"
    document = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{_BASE_CSS}{_PLAYTHROUGH_CSS}{FOLD_TABLES_CSS}</style></head><body>{TIP_HTML}"
        f"<header><h1>{_esc(title)}</h1>"
        "<div class='sub'>Minage, crafts, sous-produits et déclencheurs simulés sans carte.</div>"
        f"<div class='stats'>{fragments['header_stats']}</div></header><main>"
        f"{fragments['bars']}"
        "<details class='table-fold' id='partie-simulee-table'><summary>Tableau détaillé par item et fluide</summary>"
        f"{fragments['table']}"
        "</details><div class='note'>Trié par volume simulé (produit + consommé). « Externe » = fourni hors chaîne de craft. Puissance = energy_usage × 0,06 ; énergie = puissance × temps.</div>"
        f"{fragments['unknown_note']}</main>{UI_SCRIPT}{FOLD_TABLES_SCRIPT}</body></html>"
    )
    _write(out, document)
    return {"analysis": analysis, "rows": rows, "seed": seed, "progression": progression}


def write_vanilla_complexity_html(dump: dict, out: Any) -> None:
    """Écrit le rapport de complexité de la seed vanilla dérivée du dump.

    Contrairement à :func:`write_playthrough_html`, aucune simulation de
    partie n'est lancée : seule la vue de complexité est produite.
    """
    seed = build_vanilla_seed(dump)
    game_version = (dump.get("meta") or {}).get("game_version", "inconnue")
    title = f"Factorio vanilla {game_version}"
    document = render_complexity_html(seed, title=title)
    _write(out, document)
