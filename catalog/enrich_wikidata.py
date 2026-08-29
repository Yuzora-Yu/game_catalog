from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .core import ROOT, load_games, write_json

API = "https://www.wikidata.org/w/api.php"
VIDEO_GAME_QID = "Q7889"


def request(params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    req = urllib.request.Request(
        f"{API}?{query}",
        headers={"User-Agent": "game-catalog/0.1 (GitHub data maintenance)"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def search(title: str, language: str) -> list[dict[str, Any]]:
    result = request(
        {
            "action": "wbsearchentities",
            "search": title,
            "language": language,
            "uselang": language,
            "limit": 5,
            "type": "item",
        }
    )
    return result.get("search") or []


def entities(ids: list[str]) -> dict[str, Any]:
    if not ids:
        return {}
    result = request(
        {
            "action": "wbgetentities",
            "ids": "|".join(ids),
            "props": "labels|descriptions|claims",
            "languages": "ja|en",
        }
    )
    return {
        entity["id"]: entity
        for entity in result.get("entities") or []
        if "id" in entity
    }


def claim_qids(entity: dict[str, Any], prop: str) -> list[str]:
    values: list[str] = []
    for claim in (entity.get("claims") or {}).get(prop) or []:
        value = (((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value"))
        if isinstance(value, dict) and value.get("id"):
            values.append(str(value["id"]))
    return values


def candidate_rows(game: dict[str, Any]) -> list[dict[str, Any]]:
    title = game["titles"]["primary"]
    search_rows: dict[str, dict[str, Any]] = {}
    for language in ("ja", "en"):
        for row in search(title, language):
            search_rows.setdefault(row["id"], row)
        time.sleep(0.05)
    details = entities(list(search_rows))
    rows: list[dict[str, Any]] = []
    for qid, search_row in search_rows.items():
        entity = details.get(qid, {})
        instance_of = claim_qids(entity, "P31")
        label_ja = ((entity.get("labels") or {}).get("ja") or {}).get("value")
        label_en = ((entity.get("labels") or {}).get("en") or {}).get("value")
        description_ja = ((entity.get("descriptions") or {}).get("ja") or {}).get("value")
        description_en = ((entity.get("descriptions") or {}).get("en") or {}).get("value")
        description_en_lower = str(description_en).lower()
        rows.append(
            {
                "qid": qid,
                "label_ja": label_ja,
                "label_en": label_en,
                "description_ja": description_ja,
                "description_en": description_en,
                "instance_of": instance_of,
                "looks_like_video_game": (
                    VIDEO_GAME_QID in instance_of
                    or "ゲーム" in str(description_ja)
                    or "video game" in description_en_lower
                ),
                "search_label": search_row.get("label"),
                "search_description": search_row.get("description"),
            }
        )
    rows.sort(key=lambda row: (not row["looks_like_video_game"], row["qid"]))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create review-only Wikidata candidate proposals; never edits game data"
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "review" / "wikidata-proposals.json",
    )
    args = parser.parse_args()
    proposals: list[dict[str, Any]] = []
    for game in load_games():
        if (game.get("external_ids") or {}).get("wikidata"):
            continue
        proposals.append(
            {
                "game_id": game["id"],
                "title": game["titles"]["primary"],
                "candidates": candidate_rows(game),
            }
        )
        if len(proposals) >= args.limit:
            break
    write_json(args.output, {"schema_version": 1, "proposals": proposals})
    print(
        json.dumps(
            {
                "status": "ok",
                "proposals": len(proposals),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
