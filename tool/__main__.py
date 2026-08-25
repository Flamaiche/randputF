"""randputF external generator CLI."""

import argparse
import json
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from tool.common.db import VanillaDB
from tool.common.demo import build_demo_db
from tool.exporters.mod_seed import write_seed_files
from tool.generator.pipeline import generate_seed
from tool.parsers.vanilla import load_db_from_dump, summarize_db
from tool.validator.solver import validate_seed

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
MOD_SOURCE = Path(__file__).resolve().parent.parent / "mod"
FACTORIO_MODS = Path.home() / ".var/app/com.valvesoftware.Steam/.factorio/mods"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _load_config() -> dict:
    if not CONFIG_PATH.exists() or yaml is None:
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_db(demo: bool, dump_path: Path) -> VanillaDB:
    if demo:
        return build_demo_db()
    if not dump_path.exists():
        print(
            f"Vanilla dump introuvable: {dump_path}\n"
            "Genere-le avec le mod compagnon 'exporter' (voir README section Mise en route),\n"
            "ou lance la pipeline en mode demo: randputf generate --demo"
        )
        sys.exit(1)
    return load_db_from_dump(json.loads(dump_path.read_text(encoding="utf-8")))


def _build_mod(seed: dict, dest: Path) -> Path:
    """Assemble le mod complet dans un .zip dans dest. Retourne le chemin du zip."""
    import tempfile
    import zipfile

    mod_name = "randputF_0.1.0"
    zip_path = dest / f"{mod_name}.zip"
    dest.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / mod_name
        tmp_path.mkdir()

        for item in MOD_SOURCE.iterdir():
            if item.name == "seed" or item.is_symlink():
                continue
            target = tmp_path / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

        write_seed_files(seed, tmp_path / "seed")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in tmp_path.rglob("*"):
                if file.is_file():
                    zf.write(file, f"{mod_name}/{file.relative_to(tmp_path)}")

    return zip_path


def _install_mod(seed: dict) -> None:
    """Cree le zip et le copie dans le dossier Factorio mods + met a jour mod-list.json."""
    mod_name = "randputF_0.1.0"
    dest = FACTORIO_MODS / mod_name

    # Supprimer l'ancien zip ou dossier
    if dest.is_symlink() or dest.exists():
        if dest.is_dir() and not dest.is_symlink():
            shutil.rmtree(dest)
        else:
            dest.unlink()

    zip_path = _build_mod(seed, FACTORIO_MODS)

    mod_list = FACTORIO_MODS / "mod-list.json"
    if mod_list.exists():
        data = json.loads(mod_list.read_text(encoding="utf-8"))
    else:
        data = {"mods": [{"name": "base", "enabled": True}]}

    names = {m["name"] for m in data["mods"]}
    if mod_name not in names:
        data["mods"].append({"name": mod_name, "enabled": True})
    else:
        for m in data["mods"]:
            if m["name"] == mod_name:
                m["enabled"] = True
    for m in data["mods"]:
        if m["name"] == "randputf-exporter":
            m["enabled"] = False

    mod_list.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def cmd_parse(args: argparse.Namespace) -> None:
    db = _load_db(args.demo, Path(args.dump))
    print(summarize_db(db))


def cmd_generate(args: argparse.Namespace) -> None:
    db = _load_db(args.demo, Path(args.dump))

    if args.seed is not None:
        db.seed_value = args.seed
    else:
        cfg = _load_config()
        db.seed_value = cfg.get("seed", 0)

    seed = generate_seed(db)
    issues = validate_seed(seed)
    if issues:
        for issue in issues:
            print(f"[INVALIDE] {issue}")
        sys.exit(2)

    if args.install:
        _install_mod(seed)
        mod_name = "randputF_0.1.0"
        print(f"Seed {db.seed_value} valide, mod installe dans {FACTORIO_MODS}/{mod_name}.zip")
    else:
        out_dir = Path(args.out) if args.out else OUTPUT_DIR
        zip_path = _build_mod(seed, out_dir)
        print(f"Seed {db.seed_value} valide, mod assemblé dans {zip_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="randputf", description="Generateur de seeds randputF")
    sub = parser.add_subparsers(dest="command", required=True)

    p_parse = sub.add_parser("parse", help="Charge et resume la base vanilla")
    p_parse.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_parse.add_argument("--dump", default="data/vanilla_dump.json")
    p_parse.set_defaults(func=cmd_parse)

    p_gen = sub.add_parser("generate", help="Genere, valide puis exporte une seed dans le mod")
    p_gen.add_argument("--demo", action="store_true", help="Utilise une base synthetique")
    p_gen.add_argument("--dump", default="data/vanilla_dump.json")
    p_gen.add_argument("--out", default=None, help="Dossier de sortie (defaut: output/randputF_0.1.0)")
    p_gen.add_argument("--seed", type=int, default=None, help="Seed (defaut: lit config/settings.yaml)")
    p_gen.add_argument("--install", action="store_true", help="Installe le mod directement dans Factorio")
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
