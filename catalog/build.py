from __future__ import annotations

import argparse
import json
import shutil
from typing import Any

from .core import OBSERVATIONS_PATH, ROOT, load_games, load_json, write_json
from .validate import validate_catalog

DIST = ROOT / "dist"
PUBLIC = ROOT / "public"
SITE = ROOT / "site"


def compiled_game(game: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    game_id = game["id"]
    activity = (observations.get("games") or {}).get(game_id)
    observed_aliases = [
        {"normalized": alias, **entry}
        for alias, entry in (observations.get("aliases") or {}).items()
        if game_id in (entry.get("candidate_game_ids") or [])
    ]
    observed_aliases.sort(
        key=lambda row: (row.get("last_seen") or "", row["normalized"]),
        reverse=True,
    )
    return {**game, "stream_activity": activity, "observed_aliases": observed_aliases}


def build() -> dict[str, Any]:
    errors = validate_catalog()
    if errors:
        raise RuntimeError("Catalog validation failed:\n" + "\n".join(errors))

    games = load_games()
    observations = load_json(OBSERVATIONS_PATH)
    compiled = [compiled_game(game, observations) for game in games]
    compiled.sort(key=lambda game: (str(game["titles"]["primary"]).casefold(), game["id"]))

    game_master = {
        game["id"]: {
            "display_name": game["titles"]["primary"],
            "status": game["status"],
        }
        for game in games
        if game["status"] != "merged"
    }
    aliases = {
        game["id"]: sorted({entry["normalized"] for entry in game["aliases"]})
        for game in games
        if game["status"] != "merged"
    }
    alias_index: dict[str, dict[str, Any]] = {}
    for game in games:
        for entry in game["aliases"]:
            alias_index[entry["normalized"]] = {
                "game_id": game["id"],
                "kind": entry["kind"],
                "source": entry["source"],
            }

    unresolved = [
        {"normalized": alias, **entry}
        for alias, entry in (observations.get("aliases") or {}).items()
        if not entry.get("candidate_game_ids")
    ]
    unresolved.sort(
        key=lambda row: (row.get("last_seen") or "", row.get("observation_count") or 0),
        reverse=True,
    )

    for directory in (DIST, PUBLIC):
        directory.mkdir(parents=True, exist_ok=True)
    write_json(DIST / "games.json", {"schema_version": 1, "games": compiled})
    write_json(DIST / "game_master.json", game_master)
    write_json(DIST / "aliases.json", aliases)
    write_json(DIST / "alias-index.json", alias_index)
    write_json(
        DIST / "review-queue.json",
        {"schema_version": 1, "unresolved_aliases": unresolved},
    )

    data_dir = PUBLIC / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("games.json", "alias-index.json", "review-queue.json"):
        shutil.copy2(DIST / filename, data_dir / filename)
    shutil.copy2(SITE / "index.html", PUBLIC / "index.html")
    shutil.copy2(SITE / "app.js", PUBLIC / "app.js")
    shutil.copy2(SITE / "styles.css", PUBLIC / "styles.css")

    return {
        "games": len(games),
        "aliases": len(alias_index),
        "unresolved_aliases": len(unresolved),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps({"status": "ok", **build()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
