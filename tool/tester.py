"""Testeur de dump randputF : contrôler, rejouer, mesurer et rendre.

Les noms ci-dessous sont stables et servent de référence à la CLI, aux tests
et à la documentation :

- ``acquisition`` : lit le dump fourni par l'exporter ;
- ``controle`` : ``validate_seed`` — cycles, invariants et unicité des
  déblocages ;
- ``rejeu`` : ``play`` — partie simulée depuis les faits du dump ;
- ``mesure`` : complexité, difficulté et partie simulée ;
- ``rapport`` : trois fichiers HTML préfixés par la source.

Aucune graine n'est tirée ici : l'état testé vient du dump, ou d'un mod déjà
assemblé quand la CLI fournit explicitement son état.
"""

from __future__ import annotations

import html as _html
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
SECTIONS = ("controles", "couverture-dump", "complexite-courbes", "difficulte", "partie-simulee")
_AUTO_ETA = object()


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
                remaining = f"fin étape ~{float(self._eta_override):.0f}s"
        elif not percent:
            remaining = "fin étape —"
        else:
            if self._eta_percent != percent:
                self._eta_percent = percent
                self._eta_value = elapsed_stage * (100 - percent) / percent
            if self._eta_value is None:
                remaining = "fin étape —"
            else:
                remaining = f"fin étape ~{self._eta_value:.0f}s"
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

    @property
    def ok(self) -> bool:
        """Indique si l'état passe le contrôle et le rejeu."""
        return not self.issues and self.victory

    def as_dict(self) -> dict[str, Any]:
        """Retourne le résultat sous forme de dict pour le rapport HTML."""
        return {
            "ok": self.ok,
            "issues": list(self.issues),
            "victory": self.victory,
            "blocker": self.blocker,
            "researched": self.researched,
            "total_techs": self.total_techs,
        }


@dataclass
class TesterReport:
    """Résultat complet d'un passage du testeur."""

    check: CheckReport
    dump_html: Path
    graph_html: Path | None
    report_html: Path
    difficulty_total: float | None
    coverage: dict


def check_state(
    db: Any, state: dict, progress: Progress | None = None
) -> CheckReport:
    """Exécute le contrôle statique puis le rejeu sur un état issu du dump."""
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


def run_dump_test(
    db: Any,
    dump: dict,
    out_dir: Path,
    *,
    source: str = "dump",
    state: dict | None = None,
    title: str | None = None,
    out_name: str | None = None,
    progress: Progress | None = None,
) -> TesterReport:
    """Teste un état déterministe et écrit les trois vues HTML dans `<out_dir>/<out_name>/`."""
    out_dir = Path(out_dir) / str(out_name or source)
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage = classify_dump_fields(dump)
    tested = state if state is not None else build_vanilla_seed(dump)
    if progress is not None:
        progress.update(100, "normalisation terminée")
    check = check_state(db, tested, progress)

    if progress is not None:
        progress.enter("mesure", "difficulté et rapport complet")
    game_version = (dump.get("meta") or {}).get("game_version", "inconnue")
    if title is None:
        title = f"randputF — test de {source} (Factorio {game_version})"
    def on_report(percent: int, detail: str) -> None:
        if progress is not None:
            progress.update(
                percent, detail, None if "étapes" in detail else _AUTO_ETA
            )

    result = write_full_report(
        tested,
        out_dir / f"{source}.report.html",
        db,
        vanilla_seed=tested,
        dump=dump,
        title=title,
        playthrough_title=f"Partie simulée — {source}",
        mod_label="état testé",
        vanilla_label="dump",
        checks=check.as_dict(),
        dump_coverage=coverage,
        on_progress=on_report,
    )
    if progress is not None:
        progress.update(96, "rapport complet écrit")

    difficulty_total = result.get("difficulty_total")
    if difficulty_total is None:
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
        progress.update(100, "difficulté calculée")

    if progress is not None:
        progress.enter("rapport", "graphe et navigateur HTML")
    dump_html = write_dump_html(dump, out_dir / f"{source}.dump.html")
    if progress is not None:
        progress.update(50, "navigateur écrit")
    graph_html = out_dir / f"{source}.graph.html"
    try:
        write_seed_graph_html(tested, graph_html)
    except (OSError, subprocess.CalledProcessError):
        _write_graph_fallback(tested, graph_html, source)
        graph_path = graph_html
    else:
        graph_path = graph_html if graph_html.exists() else None
    if progress is not None:
        progress.update(100, "graphe écrit")

    if progress is not None:
        progress.finish("vues HTML écrites")
    return TesterReport(
        check=check,
        dump_html=dump_html,
        graph_html=graph_path,
        report_html=Path(result["path"]),
        difficulty_total=difficulty_total,
        coverage=coverage,
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
