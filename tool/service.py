"""Orchestration partagée entre la CLI et l'interface graphique.

Pourquoi ce module existe
-------------------------
``tool/__main__.py`` appelait directement les générateurs. Une IG qui fait la
même chose en réécrivant l'orchestration produirait un mod *possiblement*
différent de celui de la CLI sur la même seed — et le témoin de
déterminisme, qui ne garantit que le contenu produit par la commande
``randputf``, cesserait de garantir quoi que ce soit pour le joueur qui passe
par l'IG. La logique est donc factorisée ici, et les deux points d'entrée
appellent le **même** code.

Différence de contrat avec la CLI
---------------------------------
La CLI se termine par ``sys.exit()``. Une IG, elle, ne peut pas se faire tuer
son propre processus quand un asset manque : la fenêtre doit afficher l'erreur
et rester ouverte. Ce module lève donc des exceptions, et ``tool/__main__.py``
les convertit en codes de sortie — le comportement observable de la CLI est
inchangé.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from tool.common import config as _cfg
from tool.common.assets import asset_path, repo_root
from tool.common.db import VanillaDB
from tool.common.demo import build_demo_db
from tool.common.version import MOD_NAME_VERSIONED
from tool.exporters.mod_seed import write_seed_files
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump
from tool.validator.solver import validate_seed

# Assets résolus en wheel (namespace packages embarqués) comme en dépôt.
MOD_SOURCE = asset_path("mod")
DUMP_PATH_DEFAULT = asset_path("data") / "vanilla_dump.json"
# Marqueur de checkout : ``pyproject.toml`` n'est jamais livré dans le wheel
# (il vit dans le ``.dist-info``), alors que ``mod/info.json`` existe dans les
# deux cas. Sans ce test, un install classique écrivait le mod généré dans
# ``site-packages/output`` — sale, et fatal si site-packages est en lecture
# seule (install système / PEP 668). Depuis un checkout on garde ``<repo>/output``.
_OUTPUT_REPO = (repo_root() / "pyproject.toml").exists()
OUTPUT_DIR = repo_root() / "output" if _OUTPUT_REPO else Path.cwd() / "output"

MAX_ATTEMPTS = 10


class RandputfError(Exception):
    """Erreur attendue, présentable telle quelle à un joueur."""


class DumpMissingError(RandputfError):
    """Le dump vanilla est introuvable."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Vanilla dump introuvable: {path}\n"
            "Le dump est embarque dans le paquet (data/vanilla_dump.json) : "
            "reinstalle randputf (pip install .) ou passe --dump <fichier>.\n"
            "Pour regenerer le dump depuis un checkout du depot, utilise le "
            "mod compagnon 'exporter' (README, section Systeme de dev)."
        )


class DumpInvalidError(RandputfError):
    """Le dump vanilla est illisible ou incohérent."""


class SeedUnplayableError(RandputfError):
    """Aucune graine dérivée n'a donné une seed jouable dans la limite fixée."""

    def __init__(self, base_seed: int, issues: list[str], seed_value: int) -> None:
        super().__init__(
            f"Seed {base_seed} non jouable apres {MAX_ATTEMPTS} tentatives "
            f"(derivee jusqu'a {seed_value})."
        )
        self.base_seed = base_seed
        self.issues = issues
        self.seed_value = seed_value


def load_config() -> dict:
    """Config de la run : defaults.yaml (source unique) + surcharges du fichier
    ``user.yaml`` (facultatif), VALIDÉS avant génération."""
    return _cfg.runtime_config()


def load_db(demo: bool = False, dump_path: Path | None = None) -> VanillaDB:
    """Charge la base vanilla. Lève ``DumpMissingError``/``DumpInvalidError``
    au lieu de quitter le processus — voir l'en-tête du module."""
    if demo:
        return build_demo_db()
    path = dump_path or DUMP_PATH_DEFAULT
    if not path.exists():
        raise DumpMissingError(path)
    try:
        return load_db_from_dump(json.loads(path.read_text(encoding="utf-8")))
    except ValueError as err:
        raise DumpInvalidError(str(err)) from err


def build_mod(seed: dict, dest: Path) -> Path:
    """Assemble le mod complet dans dest. Retourne le chemin du dossier."""
    mod_name = MOD_NAME_VERSIONED
    mod_dir = dest / mod_name
    dest.mkdir(parents=True, exist_ok=True)

    if mod_dir.exists():
        shutil.rmtree(mod_dir)
    mod_dir.mkdir()

    for item in MOD_SOURCE.iterdir():
        if item.name == "seed" or item.is_symlink():
            continue
        target = mod_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    write_seed_files(seed, mod_dir / "seed")
    return mod_dir


def install_mod(seed: dict, mods_dir: Path) -> None:
    """Copie le mod dans le dossier Factorio mods + met a jour mod-list.json."""
    mod_name = MOD_NAME_VERSIONED
    dest = mods_dir / mod_name

    if dest.is_symlink():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)

    build_mod(seed, mods_dir)

    info = json.loads((dest / "info.json").read_text(encoding="utf-8"))
    mod_list_name = info.get("name", mod_name)

    mod_list = mods_dir / "mod-list.json"
    if mod_list.exists():
        data = json.loads(mod_list.read_text(encoding="utf-8"))
    else:
        data = {"mods": [{"name": "base", "enabled": True}]}

    names = {m["name"] for m in data["mods"]}
    if mod_list_name not in names:
        data["mods"].append({"name": mod_list_name, "enabled": True})
    else:
        for m in data["mods"]:
            if m["name"] == mod_list_name:
                m["enabled"] = True
    for m in data["mods"]:
        if m["name"] == "randputf-exporter":
            m["enabled"] = False

    mod_list.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def current_seed() -> int:
    """Graine tirée de l'horloge (ms) : partie unique à chaque génération."""
    return int(time.time() * 1000)


def generate_with_retry(
    db: VanillaDB,
    cfg: dict,
    base_seed: int,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    on_attempt=None,
) -> tuple[dict, VanillaDB]:
    """Génère une seed, et réessaie avec des graines dérivées tant qu'elle est
    invalide. Retourne ``(seed, db)`` avec ``db.seed_value`` positionné sur la
    graine qui a **réussi** — indispensable : le mod installé doit porter la
    seed réellement utilisée, pas celle demandée.

    ``max_attempts`` est le nombre total de générations (la graine de base
    comprise), comme dans la CLI historique : on tente ``base`` puis
    ``base+1`` … ``base+max_attempts-1``, et on lève au-delà.
    """
    db.seed_value = base_seed
    seed = generate_seed(db, config=cfg)
    issues = validate_seed(seed)

    for attempt in range(1, max_attempts):
        if not issues:
            return seed, db
        if on_attempt is not None:
            on_attempt(attempt, base_seed + attempt, issues)
        db.seed_value = base_seed + attempt
        seed = generate_seed(db, config=cfg)
        issues = validate_seed(seed)

    if issues:
        raise SeedUnplayableError(base_seed, issues, db.seed_value)
    return seed, db