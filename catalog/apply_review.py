from __future__ import annotations

import argparse
from pathlib import Path

from .core import GAMES_DIR, load_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply an explicitly reviewed Wikidata mapping file")
    parser.add_argument("review", type=Path, help="JSON object: {game_id: {wikidata, ja?, en?}}")
    args = parser.parse_args()
    mappings = load_json(args.review)
    changed = 0
    for game_id, mapping in mappings.items():
        path = GAMES_DIR / f"{game_id}.json"
        game = load_json(path)
        game.setdefault("external_ids", {})["wikidata"] = mapping["wikidata"]
        for locale in ("ja", "en"):
            if mapping.get(locale):
                game["titles"][locale] = mapping[locale]
        game["verification"]["status"] = "partially_verified"
        source = {"type": "wikidata", "ref": f"https://www.wikidata.org/wiki/{mapping['wikidata']}"}
        if source not in game["verification"]["sources"]:
            game["verification"]["sources"].append(source)
        write_json(path, game)
        changed += 1
    print(f"updated {changed} games")


if __name__ == "__main__":
    main()
