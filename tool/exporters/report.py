"""Rapport complet : complexité + difficulté + partie simulée."""
from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any

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

_TOC = '\n<nav class="toc" aria-label="Sommaire">\n  <div class="toc-title">Sommaire</div>\n  <a href="#complexite-courbes">Complexité — courbes</a>\n  <a href="#complexite-ateliers">Complexité — ateliers</a>\n  <a href="#complexite-detail-table">Détail par technologie</a>\n  <a href="#difficulte">Difficulté</a>\n  <a class="toc-sub" href="#difficulte-table">Tableau de difficulté</a>\n  <a href="#partie-simulee">Partie simulée</a>\n  <a class="toc-sub" href="#partie-simulee-table">Tableau par item</a>\n</nav>\n'

_TOC_SCRIPT = "\n<script>\n(function () {\n  function openTarget() {\n    var el = location.hash ? document.querySelector(location.hash) : null;\n    if (el && el.tagName === 'DETAILS') el.open = true;\n  }\n  window.addEventListener('hashchange', openTarget);\n  openTarget();\n})();\n</script>\n"


def _document_parts(document: str) -> tuple[str, str]:
    style = _STYLE_RE.search(document)
    body = _BODY_RE.search(document)
    if style is None or body is None:
        raise ValueError("document HTML sans <style> ou <body>")
    return style.group(1), body.group(1)


def _playthrough_section(report: dict) -> str:
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
) -> dict:
    meta = seed.get("meta") or {}
    if title is None:
        label = meta.get("seed", meta.get("generator_version", "?"))
        title = f"randputF seed {label}"
    complexity_doc = render_complexity_html(seed, db, title=title)
    _, complexity_body = _document_parts(complexity_doc)
    body = complexity_body
    if vanilla_seed is not None:
        difficulty_doc = render_difficulty_graph_html(
            seed, vanilla_seed, mod_label=mod_label, vanilla_label=vanilla_label
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
            f"{difficulty_table_html(seed, label='seed')}"
            "</div></details></section>"
        )
    playthrough = playthrough_report(
        dump,
        db,
        seed=seed,
        title=playthrough_title or f"{title} — partie simulée",
    )
    playthrough_section = _playthrough_section(playthrough)
    inserted = difficulty_section + playthrough_section
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
    return {
        "seed": seed,
        "analysis": playthrough["analysis"],
        "rows": playthrough["rows"],
        "progression": playthrough["progression"],
        "path": path,
    }
