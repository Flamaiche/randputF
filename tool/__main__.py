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
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    if yaml is not None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    # Fallback: parse le YAML a la main (seule la ligne factorio_mods compte)
    result = {}
    for line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key == "factorio_mods":
                result["factorio_mods"] = val
            elif key == "seed":
                try:
                    result["seed"] = int(val)
                except ValueError:
                    pass
    return result


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
    """Assemble le mod complet dans dest. Retourne le chemin du dossier."""
    mod_name = "randputF_0.1.0"
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


def _install_mod(seed: dict, mods_dir: Path) -> None:
    """Copie le mod dans le dossier Factorio mods + met a jour mod-list.json."""
    mod_name = "randputF_0.1.0"
    dest = mods_dir / mod_name

    if dest.is_symlink():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)

    _build_mod(seed, mods_dir)

    mod_list = mods_dir / "mod-list.json"
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
        cfg = _load_config()
        raw_path = cfg.get("factorio_mods", "")
        mods_dir = Path(raw_path).expanduser() if raw_path else Path()
        if mods_dir.exists() and mods_dir.is_dir():
            _install_mod(seed, mods_dir)
            print(f"Seed {db.seed_value} valide, mod installe dans {mods_dir}/")
        else:
            out_dir = OUTPUT_DIR
            mod_path = _build_mod(seed, out_dir)
            print(f"Dossier Factorio mods introuvable ({raw_path})")
            print(f"Seed {db.seed_value} valide, mod assemblé dans {mod_path}")
            print(f"Copie-le manuellement dans ton dossier mods Factorio.")
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
