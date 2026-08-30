from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import GAMES_DIR, ROOT, load_games, load_json, normalize_text, write_json
from .import_steam_games import clean_title, slugify


def import_seed(entries: list[dict[str, Any]], source_ref: str) -> dict[str, int]:
    games = load_games()
    by_id = {game["id"]: game for game in games}
    alias_owner = {
        alias["normalized"]: game
        for game in games
        for alias in game.get("aliases") or []
    }
    created = updated = skipped = 0

    for entry in entries:
        ja = clean_title(str(entry.get("ja") or "")) or None
        en = clean_title(str(entry.get("en") or "")) or None
        primary = clean_title(str(entry.get("primary") or ja or en or ""))
        raw_aliases = [primary, ja, en, *(entry.get("aliases") or [])]
        aliases: dict[str, str] = {}
        for value in raw_aliases:
            title = clean_title(str(value or ""))
            if title:
                aliases.setdefault(normalize_text(title), title)
        if not primary or not aliases:
            skipped += 1
            continue

        owners = {
            alias_owner[normalized]["id"]
            for normalized in aliases
            if normalized in alias_owner
        }
        owner = by_id[next(iter(owners))] if len(owners) == 1 else None
        if len(owners) > 1:
            skipped += 1
            continue

        if owner is not None:
            changed = False
            for normalized, title in aliases.items():
                if normalized in alias_owner:
                    continue
                owner["aliases"].append(
                    {
                        "text": title,
                        "normalized": normalized,
                        "kind": "official",
                        "source": "console_classics_seed",
                    }
                )
                alias_owner[normalized] = owner
                changed = True
            if not owner["titles"].get("ja") and ja:
                owner["titles"]["ja"] = ja
                changed = True
            if not owner["titles"].get("en") and en:
                owner["titles"]["en"] = en
                changed = True
            if changed:
                write_json(GAMES_DIR / f"{owner['id']}.json", owner)
                updated += 1
            else:
                skipped += 1
            continue

        requested_id = str(entry.get("id") or "")
        game_id = requested_id or slugify(en or primary)
        if not game_id:
            skipped += 1
            continue
        if game_id in by_id:
            game_id = f"{game_id}-console"
        game = {
            "schema_version": 1,
            "id": game_id,
            "status": "active",
            "titles": {"primary": primary, "ja": ja, "en": en},
            "aliases": [
                {
                    "text": title,
                    "normalized": normalized,
                    "kind": "official",
                    "source": "console_classics_seed",
                }
                for normalized, title in aliases.items()
            ],
            "releases": [],
            "companies": [],
            "platforms": list(entry.get("platforms") or []),
            "external_ids": {},
            "sales_observations": [],
            "verification": {
                "status": "seed_unverified",
                "checked_at": None,
                "sources": [{"type": "curated_seed", "ref": source_ref}],
            },
        }
        write_json(GAMES_DIR / f"{game_id}.json", game)
        by_id[game_id] = game
        for normalized in aliases:
            alias_owner[normalized] = game
        created += 1

    return {"created": created, "updated": updated, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a reviewed initial game-title seed")
    parser.add_argument(
        "seed",
        type=Path,
        nargs="?",
        default=ROOT / "data" / "seeds" / "console-classics.json",
    )
    args = parser.parse_args()
    seed_path = args.seed.resolve()
    payload = load_json(seed_path)
    stats = import_seed(
        payload["games"],
        str(seed_path.relative_to(ROOT)).replace("\\", "/"),
    )
    print(json.dumps({"status": "ok", "input": len(payload["games"]), **stats}, ensure_ascii=False))


if __name__ == "__main__":
    main()
