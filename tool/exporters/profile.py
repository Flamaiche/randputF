"""Rendu HTML du profil de difficulté multi-axes."""

from __future__ import annotations

import html as _html
from typing import Any

from tool.audit.profile import AXIS_LABELS, INDICATOR_LABELS

PROFILE_CSS = '\n.profile-note{color:#8f8fa0;font-size:11px;margin-top:10px}\n.profile-ratio{font-variant-numeric:tabular-nums}\ndetails.report-section.profile-section>summary.section-title{font-size:1.5em}\n'


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, int):
        return f"{value:_}".replace("_", " ")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _html.escape(str(value))
    if number.is_integer():
        return f"{int(number):_}".replace("_", " ")
    return f"{number:,.2f}".replace(",", " ").replace(".", ",")


def _ratio(ratio: float | None) -> str:
    if ratio is None:
        return "—"
    return f"×{_fmt(ratio)}"


def render_profile_html(profile: dict[str, Any]) -> str:
    """Retourne la section HTML du profil, prête à être insérée dans un rapport."""
    baseline = _html.escape(str(profile.get("baseline_label") or "référence"))
    score = profile.get("score")
    summary_rows = []
    detail_rows = []
    for key, axis in profile["axes"].items():
        label = AXIS_LABELS.get(key, key)
        ratio = _ratio(axis.get("ratio"))
        weight = profile.get("weights", {}).get(key)
        weight_text = f"{int(weight * 100)} %" if weight is not None else "—"
        summary_rows.append(
            "<tr>"
            f"<td data-tip-title='{_html.escape(label)}' data-tip='{_html.escape('Score global de cet axe, normalisé contre la référence.')}'>{_html.escape(label)}</td>"
            f"<td class='num'>{weight_text}</td>"
            f"<td class='num profile-ratio'>{ratio}</td>"
            "</tr>"
        )
        values = axis.get("values") or {}
        references = axis.get("reference") or {}
        raw_values = axis.get("raw_values") or {}
        raw_references = axis.get("reference_raw") or {}
        for indicator, value in values.items():
            reference = references.get(indicator) if references else None
            raw = raw_values.get(indicator)
            raw_reference = raw_references.get(indicator) if references else None
            indicator_ratio = None
            if reference is not None:
                try:
                    if float(reference) > 0:
                        indicator_ratio = float(value) / float(reference)
                except (TypeError, ValueError):
                    indicator_ratio = None
            detail_rows.append(
                "<tr>"
                f"<td>{_html.escape(label)}</td>"
                f"<td>{_html.escape(INDICATOR_LABELS.get(indicator, indicator))}</td>"
                f"<td class='num'>{_fmt(value)}"
                + (f"<br><span class='profile-note'>brut {_fmt(raw)}</span>" if raw is not None else "")
                + (
                    f"<br><span class='profile-note profile-ratio'>{_ratio(indicator_ratio)} {_html.escape(baseline)}</span>"
                    if indicator_ratio is not None
                    else ""
                )
                + "</td>"
                f"<td class='num'>{_fmt(reference) if references else '—'}"
                + (
                    f"<br><span class='profile-note'>brut {_fmt(raw_reference)}</span>"
                    if raw_reference is not None
                    else ""
                )
                + "</td>"
                f"<td class='num profile-ratio'>{_ratio(indicator_ratio)}</td>"
                "</tr>"
            )

    score_html = _ratio(score)
    unknown = profile.get("unknown") or []
    unknown_html = (
        "<p class='profile-note'>Terminals non résolus : "
        + _html.escape(", ".join(unknown[:12]))
        + ("…" if len(unknown) > 12 else "")
        + "</p>"
        if unknown
        else ""
    )
    return (
        "<details class='report-section profile-section' id='profil-difficulte' open>"
        "<summary class='section-title'>Profil de difficulté (multi-axes)</summary>"
        "<p class='profile-note'>Les rapports sont normalisés contre "
        f"{baseline} : 1,00 = même difficulté. Indice global pondéré : "
        f"{score_html}.</p>"
        "<div class='two'><div>"
        "<table><thead><tr><th data-tip-title='Axe' data-tip='Famille d’indicateurs de difficulté.'>Axe</th><th data-tip-title='Poids' data-tip='Part de l’axe dans l’indice global.'>Poids</th><th data-tip-title='Indice' data-tip='Rapport normalisé contre la référence (1,00 = même difficulté).'>Indice</th></tr></thead><tbody>"
        f"{''.join(summary_rows)}"
        "</tbody></table>"
        "</div><div>"
        "<p class='profile-note'>Chaque axe est la moyenne géométrique des rapports de ses "
        "indicateurs. Les volumes sont des estimations linéaires, pas un dépliage exact : "
        "ils servent à comparer des parties, pas à prédire un temps de jeu réel.</p>"
        f"{unknown_html}"
        "</div></div>"
        "<details class='table-fold' id='profil-difficulte-table'><summary>Tableau des indicateurs</summary>"
        "<div class='scroll'><table><thead><tr>"
        "<th data-tip-title='Axe' data-tip='Famille d’indicateurs.'>Axe</th>"
        "<th data-tip-title='Indicateur' data-tip='Mesure précise utilisée dans l’axe.'>Indicateur</th>"
        "<th data-tip-title='Valeur' data-tip='Valeur mesurée sur la seed/mod.'>Valeur</th>"
        "<th data-tip-title='Référence' data-tip='Valeur de la baseline de comparaison.'>Référence</th>"
        "<th data-tip-title='Ratio' data-tip='Valeur / référence (×1,00 = égal).'>Ratio</th>"
        f"</tr></thead><tbody>{''.join(detail_rows)}</tbody></table></div>"
        "</details></details>"
    )
