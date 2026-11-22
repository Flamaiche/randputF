"""Testeur de dump randputF : contrôler, rejouer, mesurer et rendre.

Les noms ci-dessous sont stables et servent de référence à la CLI, aux tests
et à la documentation :

- ``acquisition`` : lit le dump fourni par l'exporter ;
- ``controle`` : ``validate_seed`` — cycles, invariants et unicité des
  déblocages ;
- ``rejeu`` : ``play`` — partie simulée depuis les faits du dump ;
- ``mesure`` : complexité, difficulté et partie simulée ;
- ``rapport`` : trois fichiers HTML préfixés par le nom canonique de la source.

Aucune graine n'est tirée ici : l'état testé vient du dump, ou d'un mod déjà
assemblé quand la CLI fournit explicitement son état.
"""

from __future__ import annotations

import html as _html
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from tool.audit.difficulty import compute_difficulty
from tool.audit.fields import classify_dump_fields
from tool.exporters.dump_html import write_dump_html
from tool.exporters.mod_seed import build_vanilla_seed
from tool.exporters.report import write_full_report
from tool.exporters.seed_graph import write_seed_graph_html
from tool.replay.player import play
from tool.validator.solver import validate_seed

STAGES = ("acquisition", "controle", "rejeu", "mesure", "rapport")
STAGE_LABELS = {
    "acquisition": "Acquisition du dump",
    "controle": "Contrôle de l'état",
    "rejeu": "Rejeu joueur",
    "mesure": "Mesure de la difficulté",
    "rapport": "Rapport HTML",
}
SECTIONS = (
    "controles",
    "couverture-dump",
    "profil-difficulte",
    "complexite-courbes",
    "difficulte",
    "partie-simulee",
)
_AUTO_ETA = object()
_COMPLEXITY_STEP_RE = re.compile(
    r"·\s*(\d+)/(\d+)(?:\s*techs)?\s*·\s*([\d ]+)\s*étapes"
)


def _parse_complexity_detail(detail: str) -> tuple[int, int, int] | None:
    match = _COMPLEXITY_STEP_RE.search(detail)
    if match is None:
        return None
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3).replace(" ", "")),
    )


def _format_eta(seconds: float) -> str:
    value = max(0, int(round(seconds)))
    if value < 600:
        return f"{value}s"
    minutes, sec = divmod(value, 60)
    if minutes < 60:
        return f"{minutes}m{sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _step_eta(
    current: int,
    total: int,
    steps: int,
    samples: list[int],
    rate: float,
    last_update: float,
    now: float,
) -> float | None:
    if (
        not samples
        or steps <= 0
        or current <= 0
        or current >= total
        or rate <= 0
        or now - last_update > 5.0
    ):
        return None
    recent = [sample for sample in samples[-8:] if sample > 0]
    if not recent:
        return None
    return sum(recent) * (total - current) / len(recent) / rate


class Progress:
    """Progression console par étape, sans dépendance externe."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        enabled: bool = True,
        refresh: float = 0.5,
    ) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.enabled = enabled
        self.refresh = refresh
        self._tty = bool(getattr(self.stream, "isatty", lambda: False)())
        self._started = time.monotonic()
        self._stage_started = self._started
        self._stage_index = 0
        self._percent = 0
        self._detail = "préparation"
        self._finished = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._width = 0
        self._last_signature = None
        self._eta_percent: int | None = None
        self._eta_value: float | None = None
        self._eta_override: float | None | object = _AUTO_ETA
        self._source: Callable[
            [], tuple[int, str | None] | tuple[int, str | None, float | None] | int
        ] | None = None

    @property
    def stage(self) -> str | None:
        """Retourne l'étape courante, ou `None` après la fin."""
        if self._finished or self._stage_index >= len(STAGES):
            return None
        return STAGES[self._stage_index]

    @property
    def percent(self) -> int:
        """Retourne le pourcentage de l'étape courante."""
        return self._percent

    def start(self) -> None:
        """Affiche l'état initial et lance le rafraîchissement périodique."""
        if self.enabled:
            self._render()
            self._launch()

    def enter(self, stage: str, detail: str = "") -> None:
        """Passe à une étape, après avoir affiché la précédente à 100 %."""
        if not self.enabled:
            return
        if self._finished:
            self._finished = False
            self._stop.clear()
            self._thread = None
        current = STAGES[self._stage_index]
        if current != stage:
            self.update(
                100, f"{STAGE_LABELS[current]} terminée"
            )
            self._source = None
        self._stage_index = STAGES.index(stage)
        self._stage_started = time.monotonic()
        self._eta_percent = None
        self._eta_value = None
        self._eta_override = _AUTO_ETA
        self._percent = 0
        self._detail = detail or STAGE_LABELS[stage]
        self._render()
        self._launch()

    def update(
        self,
        percent: int,
        detail: str | None = None,
        eta: float | None | object = _AUTO_ETA,
    ) -> None:
        """Met à jour le pourcentage de l'étape courante."""
        if not self.enabled:
            return
        self._percent = max(0, min(100, int(percent)))
        if detail is not None:
            self._detail = detail
        self._eta_override = eta
        self._render()
        self._launch()

    def watch(
        self,
        source: Callable[
            [], tuple[int, str | None] | tuple[int, str | None, float | None] | int
        ] | None,
    ) -> None:
        """Relit les informations de l'étape à chaque affichage."""
        self._source = source

    def complete(self, detail: str | None = None) -> None:
        """Marque l'étape courante comme terminée."""
        self.update(100, detail or f"{STAGE_LABELS[STAGES[self._stage_index]]} terminée")

    def finish(self, detail: str = "terminé") -> None:
        """Affiche 100 % de la dernière étape puis arrête le rafraîchissement."""
        if not self.enabled or self._finished:
            return
        self._source = None
        self._percent = 100
        self._detail = detail
        self._render()
        self._finished = True
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.refresh + 0.1)
        if self._tty:
            self.stream.write("\n")
        self.stream.flush()

    def _launch(self) -> None:
        if (
            not self.enabled
            or not self._tty
            or self._finished
            or self.refresh <= 0
            or self._thread is not None
        ):
            return
        self._thread = threading.Thread(target=self._tick, daemon=True)
        self._thread.start()

    def _tick(self) -> None:
        while not self._stop.wait(self.refresh):
            self._render()

    def _render(self) -> None:
        if self._source is not None:
            info = self._source()
            if isinstance(info, tuple):
                if len(info) == 3:
                    value, detail, eta = info
                    self._eta_override = eta
                else:
                    value, detail = info
                if detail is not None:
                    self._detail = detail
            else:
                value = info
            self._percent = max(0, min(100, int(value)))
        now = time.monotonic()
        elapsed_stage = now - self._stage_started
        percent = self._percent
        filled = percent // 5
        bar = "█" * filled + "░" * (20 - filled)
        stage = STAGES[self._stage_index]
        step = f"{self._stage_index + 1}/{len(STAGES)}"
        signature = (stage, self._percent, self._detail)
        if not self._tty and signature == self._last_signature:
            return
        self._last_signature = signature
        if percent >= 100:
            remaining = "terminé"
        elif self._eta_override is not _AUTO_ETA:
            if self._eta_override is None:
                remaining = "fin étape —"
            else:
                remaining = f"fin étape ~{_format_eta(float(self._eta_override))}"
        elif not percent:
            remaining = "fin étape —"
        else:
            if self._eta_percent != percent:
                self._eta_percent = percent
                self._eta_value = elapsed_stage * (100 - percent) / percent
            if self._eta_value is None:
                remaining = "fin étape —"
            else:
                remaining = f"fin étape ~{_format_eta(self._eta_value)}"
        text = (
            f"{STAGE_LABELS[stage]} [{bar}] {percent:3d}% {step} — "
            f"{self._detail} · {elapsed_stage:5.1f}s · {remaining}"
        )
        if self._tty:
            clear = " " * max(0, self._width - len(text))
            self.stream.write(f"\r{text}{clear}")
            self._width = len(text)
        else:
            self.stream.write(f"{text}\n")
        self.stream.flush()


@dataclass
class CheckReport:
    """Résultat des étapes ``controle`` et ``rejeu`` du testeur."""

    issues: list[str] = field(default_factory=list)
    victory: bool = False
    blocker: str | None = None
    researched: int = 0
    total_techs: int = 0
    skipped: bool = False

    @property
    def ok(self) -> bool:
        """Indique si l'état passe le contrôle et le rejeu."""
        return not self.skipped and not self.issues and self.victory

    def as_dict(self) -> dict[str, Any]:
        """Retourne le résultat sous forme de dict pour le rapport HTML."""
        return {
            "ok": self.ok,
            "issues": list(self.issues),
            "victory": self.victory,
            "blocker": self.blocker,
            "researched": self.researched,
            "total_techs": self.total_techs,
            "skipped": self.skipped,
        }


@dataclass
class TesterReport:
    """Résultat complet d'un passage du testeur."""

    check: CheckReport
    dump_html: Path | None
    graph_html: Path | None
    report_html: Path | None
    difficulty_total: float | None
    coverage: dict
    cache_hit: bool = False
    cache_written: bool = False
    skipped: frozenset[str] = field(default_factory=frozenset)


def check_state(
    db: Any,
    state: dict,
    progress: Progress | None = None,
    *,
    skip: frozenset[str] = frozenset(),
) -> CheckReport:
    """Exécute le contrôle statique puis le rejeu sur un état issu du dump."""
    if "checks" in skip:
        if progress is not None:
            progress.enter("controle", "contrôles ignorés")
            progress.update(100, "contrôles ignorés")
            progress.enter("rejeu", "rejeu ignoré")
            progress.update(100, "rejeu ignoré")
        return CheckReport(skipped=True)

    if progress is not None:
        progress.enter("controle", "validation des invariants")

    validation_state = {"percent": 0}

    def on_validate(percent: int) -> None:
        validation_state["percent"] = percent
        if progress is not None:
            progress.update(percent, "validation des invariants")

    if progress is not None:
        progress.watch(
            lambda: (validation_state["percent"], "validation des invariants")
        )
    issues = validate_seed(state, on_validate)
    if progress is not None:
        progress.enter("rejeu", "partie simulée")

    total_techs = len(state.get("technologies") or [])
    started = time.monotonic()
    replay_state = {
        "percent": 0,
        "detail": f"partie simulée · 0/{total_techs} techs",
        "researched": 0,
        "total": total_techs,
        "started": started,
        "last_change": started,
    }

    def on_play(percent: int, researched: int, total: int) -> None:
        replay_state["percent"] = percent
        replay_state["detail"] = f"partie simulée · {researched}/{total} techs"
        replay_state["researched"] = researched
        replay_state["total"] = total
        replay_state["last_change"] = time.monotonic()
        if progress is not None:
            progress.update(percent, replay_state["detail"])

    def replay_info() -> tuple[int, str, float | None]:
        now = time.monotonic()
        researched = replay_state["researched"]
        total = replay_state["total"]
        eta = None
        if researched and now - replay_state["last_change"] <= 5.0:
            eta = (now - replay_state["started"]) * (total - researched) / researched
        return replay_state["percent"], replay_state["detail"], eta

    if progress is not None:
        progress.watch(replay_info)
    replay = play(db, state, on_play)
    return CheckReport(
        issues=list(issues),
        victory=bool(replay.victory),
        blocker=str(replay.blocker) if replay.blocker else None,
        researched=int(replay.researched),
        total_techs=int(replay.total_techs),
    )


def _write_graph_fallback(state: dict, path: Path, source: str) -> None:
    """Écrit une vue graphe textuelle quand Graphviz ne peut pas rendre le SVG."""
    techs = sorted(tech.get("id", "") for tech in state.get("technologies") or [])
    recipes = sorted(recipe.get("name", "") for recipe in state.get("recipes") or [])
    tech_html = "".join(f"<li>{_html.escape(name)}</li>" for name in techs[:1000])
    recipe_html = "".join(f"<li>{_html.escape(name)}</li>" for name in recipes[:1000])
    document = (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>{_html.escape(source)} — graphe</title>"
        "<style>body{font:14px system-ui,sans-serif;background:#16161d;color:#ddd;margin:24px}"
        "h1{font-size:20px}ul{columns:3;line-height:1.5}li{overflow-wrap:anywhere}</style></head><body>"
        f"<h1>{_html.escape(source)} — graphe (vue textuelle)</h1>"
        f"<p>Rendu SVG indisponible : {len(techs)} technologies, {len(recipes)} recettes.</p>"
        f"<h2>Technologies</h2><ul>{tech_html}</ul>"
        f"<h2>Recettes</h2><ul>{recipe_html}</ul></body></html>"
    )
    path.write_text(document, encoding="utf-8")


def _state_as_dump(dump: dict, state: dict) -> dict:
    view = dict(dump)
    meta = dict(dump.get("meta") or {})
    state_meta = state.get("meta") or {}
    for key in ("mod_label", "mod_label_full", "active_mods", "dump_file"):
        value = state_meta.get(key)
        if value is not None:
            meta[key] = value
    view["meta"] = meta
    view["mod_data"] = state
    for key in ("recipes", "technologies"):
        value = state.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            view[key] = {
                str(entry.get("name") or entry.get("id") or index): entry
                for index, entry in enumerate(value)
            }
        else:
            view[key] = value
    return view


def run_dump_test(
    db: Any,
    dump: dict,
    out_dir: Path,
    *,
    source: str = "dump",
    state: dict | None = None,
    baseline_seed: dict | None = None,
    title: str | None = None,
    out_name: str | None = None,
    progress: Progress | None = None,
    skip: frozenset[str] = frozenset(),
) -> TesterReport:
    """Teste un état déterministe et écrit les trois HTML dans `<out_dir>/<name>/`."""
    name = str(out_name or source)
    display_name = name
    out_dir = Path(out_dir) / name
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage = classify_dump_fields(dump)
    baseline = baseline_seed if baseline_seed is not None else build_vanilla_seed(dump)
    tested = state if state is not None else baseline
    dump_view = _state_as_dump(dump, state) if state is not None else dump
    if progress is not None:
        progress.update(100, "normalisation terminée")
    check = check_state(db, tested, progress, skip=skip)

    if progress is not None:
        progress.enter("mesure", "difficulté et rapport complet")
    game_version = (dump.get("meta") or {}).get("game_version", "inconnue")
    if title is None:
        title = f"randputF — test de {display_name} (Factorio {game_version})"
    report_state: dict[str, Any] = {
        "percent": 0,
        "detail": "",
        "current": 0,
        "total": 0,
        "steps": 0,
        "samples": [],
        "rate": 0.0,
        "last_update": time.monotonic(),
        "active": False,
    }

    def on_report(percent: int, detail: str) -> None:
        if progress is None:
            return
        now = time.monotonic()
        parsed = _parse_complexity_detail(detail)
        if parsed is None:
            report_state["active"] = False
        else:
            current, total, steps = parsed
            previous = report_state["current"]
            if previous and current > previous:
                report_state["samples"].append(report_state["steps"])
            if report_state["steps"] and steps > report_state["steps"]:
                delta = now - report_state["last_update"]
                if delta > 0:
                    rate = (steps - report_state["steps"]) / delta
                    old = report_state["rate"]
                    report_state["rate"] = rate if not old else 0.7 * rate + 0.3 * old
            report_state["current"] = current
            report_state["total"] = total
            report_state["steps"] = steps
            report_state["last_update"] = now
            report_state["active"] = True
        report_state["percent"] = percent
        report_state["detail"] = detail
        progress.update(percent, detail)

    def report_info() -> tuple[int, str, float | None]:
        now = time.monotonic()
        eta = None
        if report_state["active"]:
            eta = _step_eta(
                report_state["current"],
                report_state["total"],
                report_state["steps"],
                report_state["samples"],
                report_state["rate"],
                report_state["last_update"],
                now,
            )
        return report_state["percent"], report_state["detail"], eta

    if progress is not None:
        progress.watch(report_info)

    result: dict = {}
    cache_hit = False
    cache_written = False
    report_path: Path | None = None
    if "report-html" in skip:
        if progress is not None:
            progress.update(96, "rapport ignoré")
    else:
        report_path = out_dir / f"{name}.report.html"
        result = write_full_report(
            tested,
            report_path,
            db,
            vanilla_seed=baseline,
            dump=dump,
            title=title,
            playthrough_title=f"Partie simulée — {display_name}",
            mod_label=display_name,
            vanilla_label="vanilla",
            checks=check.as_dict(),
            dump_coverage=coverage,
            on_progress=on_report,
            skip=skip,
        )
        cache_hit = bool(result.get("cache_hit"))
        cache_written = bool(result.get("cache_written"))
        if progress is not None:
            progress.update(96, "rapport complet écrit")
    if (
        progress is not None
        and "report-html" in skip
        and "difficulty" in skip
    ):
        progress.update(0, "calculs ignorés")

    difficulty_total = result.get("difficulty_total")
    if difficulty_total is None and "difficulty" not in skip:
        def on_difficulty(percent: int) -> None:
            if progress is not None:
                progress.update(95 + percent * 5 // 100, "difficulté calculée")

        try:
            difficulty_total = float(
                compute_difficulty(tested, on_difficulty).total
            )
        except (ArithmeticError, KeyError, TypeError, ValueError):
            difficulty_total = None
    if progress is not None:
        progress.update(
            100,
            "difficulté ignorée" if "difficulty" in skip else "difficulté calculée",
        )

    if progress is not None:
        progress.enter("rapport", "graphe et navigateur HTML")
    if "dump-html" in skip:
        dump_path = None
        if progress is not None:
            progress.update(50, "navigateur ignoré")
    else:
        dump_path = write_dump_html(
            dump_view, out_dir / f"{name}.dump.html", label=display_name
        )
        if progress is not None:
            progress.update(50, "navigateur écrit")
    if "graph-html" in skip:
        graph_path = None
        if progress is not None:
            progress.update(100, "graphe ignoré")
    else:
        graph_html = out_dir / f"{name}.graph.html"
        try:
            write_seed_graph_html(tested, graph_html)
        except (OSError, subprocess.CalledProcessError):
            _write_graph_fallback(tested, graph_html, display_name)
            graph_path = graph_html
        else:
            graph_path = graph_html if graph_html.exists() else None
        if progress is not None:
            progress.update(100, "graphe écrit")

    if progress is not None:
        html_skipped = {"report-html", "dump-html", "graph-html"} <= set(skip)
        progress.finish("vues HTML ignorées" if html_skipped else "vues HTML écrites")
    return TesterReport(
        check=check,
        dump_html=dump_path,
        graph_html=graph_path,
        report_html=report_path,
        difficulty_total=difficulty_total,
        coverage=coverage,
        cache_hit=cache_hit,
        cache_written=cache_written,
        skipped=frozenset(skip),
    )


__all__ = [
    "STAGES",
    "STAGE_LABELS",
    "SECTIONS",
    "Progress",
    "CheckReport",
    "TesterReport",
    "check_state",
    "run_dump_test",
]
