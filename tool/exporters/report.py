"""Rapport complet : contrôles + complexité + difficulté + partie simulée."""
from __future__ import annotations

import html as _html
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tool.audit.difficulty import difficulty_series
from tool.audit.fields import classify_dump_fields
from tool.exporters.complexity_graph import _CSS as _COMPLEXITY_CSS
from tool.exporters.complexity_graph import render_complexity_html
from tool.exporters.difficulty_graph import (
    DIFFICULTY_CSS,
    difficulty_table_html,
    render_difficulty_graph_html,
)
from tool.exporters.vanilla_complexity import playthrough_report

_STYLE_RE = re.compile("<style>(.*?)</style>", re.DOTALL)
_BODY_RE = re.compile("<body>(.*?)</body>", re.DOTALL)
_FIRST_H1_RE = re.compile("<h1>.*?</h1>", re.DOTALL)
_REPORT_CSS = '\nbody{padding-right:250px}\n.report-section{margin-top:40px;padding-top:12px;border-top:1px solid #3a3a45}\n.report-section>h2{margin-top:0}\nsection{scroll-margin-top:18px}\ndetails.table-fold{scroll-margin-top:18px}\n.scroll{overflow:auto;max-height:70vh;scrollbar-gutter:stable}\n.flow{color:#8f8fa0;font-size:11px;max-width:260px}\ntd.num{white-space:nowrap}\n.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}\n.toc{position:fixed;top:16px;right:16px;width:214px;\n  max-height:calc(100vh - 32px);overflow:auto;background:#1d1d24;\n  border:1px solid #3a3a45;border-radius:10px;padding:12px;z-index:40;\n  font-size:12px}\n.toc-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;\n  color:#8f8fa0;margin:0 0 8px;padding:0 8px}\n.toc a{display:block;padding:5px 8px;border-radius:6px;color:#c9c9d6;\n  text-decoration:none;overflow-wrap:anywhere}\n.toc a:hover{background:rgba(111,111,230,.15);color:#fff}\n.toc .toc-sub{padding-left:20px;font-size:11px;color:#9a9aac}\n@media(max-width:1700px){\n  body{padding-right:0}\n  .toc{position:static;width:auto;max-height:none;margin:0 24px 18px}\n}\n@media(max-width:1000px){.two{grid-template-columns:1fr}}\n'

_TOC = '\n<nav class="toc" aria-label="Sommaire">\n  <div class="toc-title">Sommaire</div>\n  <a href="#controles">Contrôles</a>\n  <a href="#couverture-dump">Couverture du dump</a>\n  <a href="#complexite-courbes">Complexité — courbes</a>\n  <a href="#complexite-ateliers">Complexité — ateliers</a>\n  <a href="#complexite-detail-table">Détail par technologie</a>\n  <a href="#difficulte">Difficulté</a>\n  <a class="toc-sub" href="#difficulte-table">Tableau de difficulté</a>\n  <a href="#partie-simulee">Partie simulée</a>\n  <a class="toc-sub" href="#partie-simulee-table">Tableau par item</a>\n</nav>\n'

_FULL_REPORT_MAX_RECIPES = 10000

_TOC_LIGHT = (
    '<nav class="toc" aria-label="Sommaire">'
    '<div class="toc-title">Sommaire</div>'
    '<a href="#resume">Résumé</a>'
    '<a href="#controles">Contrôles</a>'
    '<a href="#couverture-dump">Couverture du dump</a>'
    '<a href="#difficulte">Difficulté</a>'
    "</nav>\n"
)

_TOC_SCRIPT = "\n<script>\n(function () {\n  function openTarget() {\n    var el = location.hash ? document.querySelector(location.hash) : null;\n    if (el && el.tagName === 'DETAILS') el.open = true;\n  }\n  window.addEventListener('hashchange', openTarget);\n  openTarget();\n})();\n</script>\n"


def _document_parts(document: str) -> tuple[str, str]:
    """Extrait le CSS et le corps d'un document HTML autonome.

    Lève ``ValueError`` si les balises ``<style>`` ou ``<body>`` manquent,
    afin qu'un rapport incomplet ne soit jamais assemblé silencieusement.
    """
    style = _STYLE_RE.search(document)
    body = _BODY_RE.search(document)
    if style is None or body is None:
        raise ValueError("document HTML sans <style> ou <body>")
    return style.group(1), body.group(1)


def _playthrough_section(report: dict) -> str:
    """Construit la section HTML « partie simulée » du rapport complet.

    ``report`` provient de :func:`tool.exporters.vanilla_complexity.playthrough_report`
    et fournit les fragments déjà rendus (bandeau, barres, tableau, notes).
    """
    return (
        "<section class='report-section' id='partie-simulee'><h2>Partie simulée — statistiques par item et fluide</h2>"
        "<div class='sub'>Inventaire porté d'une technologie à l'autre, items produits quand ils manquent (minage ou recette primaire), déclencheurs de recherche inclus.</div>"
        f"<div class='stats'>{report['header_stats']}</div>"
        f"{report['bars']}"
        "<details class='table-fold' id='partie-simulee-table'><summary>Tableau détaillé par item et fluide</summary>"
        f"{report['table']}"
        "</details><div class='note'>Trié par volume simulé (produit + consommé). « Externe » = fourni hors chaîne de craft (pompage, récolte, orbite) : produit mais sans recette ni gisement minable. Puissance = energy_usage × 0,06 ; énergie = puissance × temps.</div>"
        f"{report['unknown_note']}</section>"
    )


def _checks_section(checks: dict | None) -> str:
    """Construit la section « contrôles du testeur » du rapport complet.

    `checks` porte les résultats de la validation statique et du rejeu. Quand
    il est absent (rapport vanilla), la section indique que les contrôles n'ont
    pas été exécutés, pour garder un sommaire stable.
    """
    if checks is None:
        return (
            "<section class='report-section' id='controles'>"
            "<h2>Contrôles du testeur</h2><p>Non exécutés pour ce rapport.</p></section>"
        )
    ok = bool(checks.get("ok"))
    status = "OK" if ok else "ÉCHEC"
    issues = checks.get("issues") or []
    issue_html = "".join(
        f"<li>{_html.escape(str(issue))}</li>" for issue in issues
    ) or "<li>Aucun problème détecté.</li>"
    replay = (
        f"<p>Rejeu : {'victoire' if checks.get('victory') else 'défaite'}"
        f" — {checks.get('researched', 0)}/{checks.get('total_techs', 0)} techs"
        f"{' — ' + _html.escape(str(checks['blocker'])) if checks.get('blocker') else ''}</p>"
    )
    return (
        "<section class='report-section' id='controles'><h2>Contrôles du testeur</h2>"
        f"<p><strong>{status}</strong> — contrôle de structure puis rejeu complet.</p>"
        f"{replay}<ul>{issue_html}</ul></section>"
    )


def _coverage_section(audit: dict | None) -> str:
    """Construit la section « couverture du dump » du rapport complet."""
    if not audit:
        return ""
    counts = audit.get("counts") or {}
    summary = " · ".join(
        f"{status} : {counts.get(status, 0)}"
        for status in ("Consommé", "Partiel", "À consommer", "Cosmétique")
    )
    rows = "".join(
        "<tr>"
        f"<td>{_html.escape(str(field['section']))}</td>"
        f"<td>{_html.escape(str(field['field']))}</td>"
        f"<td>{_html.escape(str(field['status']))}</td>"
        f"<td>{_html.escape(str(field['reason']))}</td>"
        "</tr>"
        for field in audit.get("fields") or []
    )
    return (
        "<section class='report-section' id='couverture-dump'><h2>Couverture du dump</h2>"
        f"<p><strong>{summary}</strong></p>"
        "<details class='table-fold' id='couverture-dump-table'><summary>Tableau des champs présents</summary>"
        f"<div class='scroll'><table><thead><tr><th>Section</th><th>Champ</th><th>État</th><th>Usage</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div></details></section>"
    )


def _summary_section(seed: dict, dump: dict | None) -> str:
    """Construit la section « résumé » d'un rapport sur un très gros dump."""
    meta = (seed.get("meta") or {})
    dump_meta = ((dump or {}).get("meta") or {})
    raw = (seed.get("pools") or {}).get("raw_resources") or []
    pairs = [
        ("Jeu", dump_meta.get("game_version", "inconnu")),
        ("Exporteur", dump_meta.get("exporter_version", "inconnu")),
        ("Source", dump_meta.get("mod_label") or meta.get("origin", "dump")),
        ("Technologies", len(seed.get("technologies") or [])),
        ("Recettes", len(seed.get("recipes") or [])),
        ("Items", len(seed.get("items") or {})),
        ("Fluides", len(seed.get("fluids") or {})),
        ("Ressources brutes", len(raw)),
    ]
    rows = "".join(
        f"<tr><th>{_html.escape(str(label))}</th><td>{_html.escape(str(value))}</td></tr>"
        for label, value in pairs
    )
    return (
        "<section class='report-section' id='resume'><h2>Résumé du dump testé</h2>"
        "<p>Vue réduite : courbes de complexité et partie simulée détaillée omises "
        "sur ce dump volumineux. Les contrôles, la couverture et la difficulté "
        "restent complets.</p>"
        f"<table><tbody>{rows}</tbody></table></section>"
    )


def write_full_report(
    seed: dict,
    path: Path,
    db: Any = None,
    *,
    vanilla_seed: dict | None = None,
    dump: dict | None = None,
    title: str | None = None,
    playthrough_title: str | None = None,
    mod_label: str = "seed (mod)",
    vanilla_label: str = "vanilla",
    checks: dict | None = None,
    lightweight: bool | None = None,
    dump_coverage: dict | None = None,
    on_progress: Callable[[int, str], None] | None = None,
) -> dict:
    """Assemble et écrit le rapport HTML complet de la seed.

    Le document réunit quatre vues dans un seul fichier autonome : contrôles
    du testeur, complexité, difficulté comparée (si ``vanilla_seed`` est
    fourni) et partie simulée. Les documents HTML existants sont réutilisés
    pour ne maintenir qu'un seul jeu de styles et de scripts. ``on_progress``,
    s'il est fourni, reçoit un pourcentage et une action. Retourne les données
    de simulation, le total de difficulté et le chemin du fichier écrit.
    """
    def emit(percent: int, detail: str) -> None:
        if on_progress is not None:
            on_progress(max(0, min(100, int(percent))), detail)

    difficulty_total = None
    meta = seed.get("meta") or {}
    if title is None:
        label = meta.get("seed", meta.get("generator_version", "?"))
        title = f"randputF seed {label}"
    if lightweight is None:
        lightweight = len(seed.get("recipes") or []) > _FULL_REPORT_MAX_RECIPES
    if dump_coverage is None and dump is not None:
        dump_coverage = classify_dump_fields(dump)
    coverage_section = _coverage_section(dump_coverage)
    if lightweight:
        emit(5, "série de difficulté")
        series: list[dict] = []
        try:
            series = difficulty_series(
                seed,
                on_progress=lambda percent: emit(
                    5 + percent * 60 // 100, "série de difficulté"
                ),
            )
            difficulty_total = series[-1]["cumulative_total"] if series else None
            difficulty_html = difficulty_table_html(
                seed,
                label=mod_label,
                series=series,
                on_progress=lambda percent: emit(
                    65 + percent * 20 // 100, "tableau de difficulté"
                ),
            )
        except (ArithmeticError, KeyError, TypeError, ValueError):
            difficulty_total = None
            difficulty_html = '<p class="muted">Aucune donnée de difficulté.</p>'
        difficulty_section = (
            "<section class='report-section' id='difficulte'>"
            "<h2>Difficulté (ressources brutes)</h2>"
            "<details class='table-fold' id='difficulte-table'><summary>Tableau de difficulté</summary>"
            f"<div class='cols'>{difficulty_html}</div>"
            "</details></section>"
        )
        emit(88, "assemblage du rapport")
        body = (
            _TOC_LIGHT
            + _summary_section(seed, dump)
            + coverage_section
            + _checks_section(checks)
            + difficulty_section
            + _TOC_SCRIPT
        )
        style = f"{_COMPLEXITY_CSS}\n{DIFFICULTY_CSS}\n{_REPORT_CSS}"
        document = (
            "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{_html.escape(title)}</title><style>{style}</style></head><body>{body}</body></html>"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8")
        emit(95, "rapport complet écrit")
        return {
            "seed": seed,
            "analysis": {},
            "rows": [],
            "progression": {},
            "coverage": dump_coverage,
            "difficulty_total": difficulty_total,
            "path": path,
        }
    emit(15, "complexité")
    complexity_doc = render_complexity_html(seed, db, title=title)
    _, complexity_body = _document_parts(complexity_doc)
    body = complexity_body
    if vanilla_seed is not None:
        difficulty_doc = render_difficulty_graph_html(
            seed,
            vanilla_seed,
            mod_label=mod_label,
            vanilla_label=vanilla_label,
            on_progress=lambda percent: emit(
                20 + percent * 40 // 100, "difficulté comparée"
            ),
        )
        _, difficulty_body = _document_parts(difficulty_doc)
        difficulty_body = _FIRST_H1_RE.sub(
            "<h2>Difficulté comparée (ressources brutes)</h2>",
            difficulty_body,
            count=1,
        )
        difficulty_section = (
            f"<section class='report-section' id='difficulte'>{difficulty_body}</section>"
        )
    else:
        difficulty_section = (
            "<section class='report-section' id='difficulte'><h2>Difficulté (ressources brutes)</h2>"
            "<details class='table-fold' id='difficulte-table'><summary>Détail par technologie</summary><div class='cols'>"
            f"{difficulty_table_html(seed, label='seed', on_progress=lambda percent: emit(20 + percent * 40 // 100, 'tableau de difficulté'))}"
            "</div></details></section>"
        )
    emit(65, "partie simulée")
    playthrough = playthrough_report(
        dump,
        db,
        seed=seed,
        title=playthrough_title or f"{title} — partie simulée",
    )
    playthrough_section = _playthrough_section(playthrough)
    controls_section = _checks_section(checks)
    inserted = controls_section + coverage_section + difficulty_section + playthrough_section
    if "</main>" in body:
        body = body.replace("</main>", f"{inserted}</main>", 1)
    else:
        body += inserted
    if "</header>" in body:
        body = body.replace("</header>", f"</header>{_TOC}", 1)
    else:
        body = _TOC + body
    body += _TOC_SCRIPT
    style = f"{_COMPLEXITY_CSS}\n{DIFFICULTY_CSS}\n{_REPORT_CSS}"
    document = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_html.escape(title)}</title><style>{style}</style></head><body>{body}</body></html>"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    emit(95, "rapport complet écrit")
    return {
        "seed": seed,
        "analysis": playthrough["analysis"],
        "rows": playthrough["rows"],
        "progression": playthrough["progression"],
        "coverage": dump_coverage,
        "difficulty_total": difficulty_total,
        "path": path,
    }
