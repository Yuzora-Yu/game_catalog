from __future__ import annotations

import argparse
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from .core import GAMES_DIR, load_games, normalize_text, write_json

SEARCH_URL = "https://store.steampowered.com/search/results/"
ROW_PATTERN = re.compile(
    r'<a[^>]+data-ds-appid="(?P<appid>\d+)"[^>]*>.*?'
    r'<span class="title">(?P<title>.*?)</span>',
    re.DOTALL,
)
TRADEMARKS = str.maketrans("", "", "®™©")
NON_GAME_SUFFIX = re.compile(
    r"(?:\bdemo\b|\bplaytest\b|\bsoundtrack\b|\bbenchmark\b|\bserver\b)",
    re.IGNORECASE,
)


def clean_title(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", "", value))
    value = unicodedata.normalize("NFKC", value.translate(TRADEMARKS))
    value = re.sub(r"[\s\u3000]+", " ", value).strip()
    if value.startswith("「") and value.endswith("」"):
        value = value[1:-1].strip()
    return value


def localized_title(value: str, english: str) -> str:
    value = clean_title(value)
    parts = [part.strip() for part in value.split(" / ", 1)]
    if len(parts) == 2 and normalize_text(parts[0]) == normalize_text(english):
        return parts[1]
    return value


def parse_search_rows(payload: str) -> dict[int, str]:
    return {
        int(match.group("appid")): clean_title(match.group("title"))
        for match in ROW_PATTERN.finditer(payload)
        if clean_title(match.group("title"))
    }


def fetch_page(
    start: int,
    count: int,
    language: str,
    tag: int | None = None,
) -> dict[int, str]:
    params: dict[str, Any] = {
        "query": "",
        "start": start,
        "count": count,
        "filter": "topsellers",
        "infinite": 1,
        "category1": 998,
        "cc": "JP",
        "l": language,
    }
    if tag is not None:
        params["tags"] = tag
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{SEARCH_URL}?{query}",
        headers={
            "User-Agent": (
                "Yuzora-Game-Catalog/0.2 "
                "(https://github.com/Yuzora-Yu/game_catalog; catalog maintenance)"
            )
        },
    )
    body: dict[str, Any] | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 503} or attempt == 4:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if retry_after else min(30.0, 2.0**attempt)
            time.sleep(max(1.0, delay))
    if body is None:
        raise RuntimeError("Steam catalog request retry loop exhausted")
    return parse_search_rows(str(body.get("results_html") or ""))


def fetch_games(
    limit: int,
    page_size: int = 100,
    tag: int | None = None,
) -> list[dict[str, Any]]:
    games: dict[int, dict[str, Any]] = {}
    for start in range(0, limit, page_size):
        count = min(page_size, limit - start)
        english = fetch_page(start, count, "english", tag)
        time.sleep(0.5)
        japanese = fetch_page(start, count, "japanese", tag)
        for appid, en_title in english.items():
            ja_title = localized_title(japanese.get(appid, ""), en_title) or None
            games[appid] = {"appid": appid, "en": en_title, "ja": ja_title}
        time.sleep(0.5)
    return list(games.values())


def slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.casefold()).strip("-")
    return slug


def safe_title(title: str) -> bool:
    normalized = normalize_text(title)
    searchable = re.sub(r"[^a-z0-9\u3040-\u30ff\u3400-\u9fff]", "", normalized)
    contains_japanese = bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", searchable))
    minimum_length = 3 if contains_japanese else 4
    return len(searchable) >= minimum_length and not NON_GAME_SUFFIX.search(normalized)


def alias_entry(title: str, appid: int) -> dict[str, str]:
    return {
        "text": title,
        "normalized": normalize_text(title),
        "kind": "official",
        "source": f"steam_store:{appid}",
    }


def import_games(rows: list[dict[str, Any]], checked_at: str) -> dict[str, int]:
    games = load_games()
    by_id = {game["id"]: game for game in games}
    alias_owner = {
        alias["normalized"]: game
        for game in games
        for alias in game.get("aliases") or []
    }
    steam_owner = {
        int(game["external_ids"]["steam_app"]): game
        for game in games
        if (game.get("external_ids") or {}).get("steam_app") is not None
    }
    created = updated = skipped = 0

    for row in rows:
        appid = int(row["appid"])
        en_title = clean_title(str(row.get("en") or ""))
        ja_title = localized_title(str(row.get("ja") or ""), en_title) or None
        title_by_key: dict[str, str] = {}
        for title in (ja_title, en_title):
            if title and safe_title(title):
                title_by_key.setdefault(normalize_text(title), title)
        titles = list(title_by_key.values())
        if not titles:
            skipped += 1
            continue

        owner = steam_owner.get(appid)
        matched_owners = {
            alias_owner[normalize_text(title)]["id"]
            for title in titles
            if normalize_text(title) in alias_owner
        }
        if owner is None and len(matched_owners) == 1:
            owner = by_id[next(iter(matched_owners))]
        elif owner is None and len(matched_owners) > 1:
            skipped += 1
            continue

        if owner is not None:
            changed = False
            deduplicated_aliases: dict[str, dict[str, Any]] = {}
            for entry in owner["aliases"]:
                deduplicated_aliases.setdefault(entry["normalized"], entry)
            if len(deduplicated_aliases) != len(owner["aliases"]):
                owner["aliases"] = list(deduplicated_aliases.values())
                changed = True
            owner_aliases = {entry["normalized"] for entry in owner["aliases"]}
            for title in titles:
                normalized = normalize_text(title)
                if normalized not in alias_owner:
                    owner["aliases"].append(alias_entry(title, appid))
                    alias_owner[normalized] = owner
                    owner_aliases.add(normalized)
                    changed = True
            if owner["external_ids"].get("steam_app") is None:
                owner["external_ids"]["steam_app"] = appid
                changed = True
            if not owner["titles"].get("ja") and ja_title:
                owner["titles"]["ja"] = ja_title
                changed = True
            if not owner["titles"].get("en") and en_title:
                owner["titles"]["en"] = en_title
                changed = True
            if changed:
                write_json(GAMES_DIR / f"{owner['id']}.json", owner)
                updated += 1
            else:
                skipped += 1
            continue

        if any(normalize_text(title) in alias_owner for title in titles):
            skipped += 1
            continue
        game_id = slugify(en_title) or f"steam-{appid}"
        if game_id in by_id:
            game_id = f"{game_id}-{appid}"
        primary = ja_title if ja_title and safe_title(ja_title) else en_title
        source_url = f"https://store.steampowered.com/app/{appid}/"
        game = {
            "schema_version": 1,
            "id": game_id,
            "status": "active",
            "titles": {"primary": primary, "ja": ja_title, "en": en_title},
            "aliases": [alias_entry(title, appid) for title in titles],
            "releases": [],
            "companies": [],
            "platforms": ["PC (Steam)"],
            "external_ids": {"steam_app": appid},
            "sales_observations": [],
            "verification": {
                "status": "partially_verified",
                "checked_at": checked_at,
                "sources": [{"type": "steam_store", "ref": source_url}],
            },
        }
        write_json(GAMES_DIR / f"{game_id}.json", game)
        by_id[game_id] = game
        steam_owner[appid] = game
        for entry in game["aliases"]:
            alias_owner[entry["normalized"]] = game
        created += 1

    return {"created": created, "updated": updated, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import official titles from Steam's game-only top-seller catalog"
    )
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument(
        "--tag",
        type=int,
        help="Optional Steam tag ID, such as 492 (Indie) or 4004 (Retro)",
    )
    parser.add_argument(
        "--checked-at", default=datetime.now(UTC).date().isoformat()
    )
    args = parser.parse_args()
    rows = fetch_games(args.limit, tag=args.tag)
    stats = import_games(rows, args.checked_at)
    print(
        json.dumps(
            {"status": "ok", "tag": args.tag, "fetched": len(rows), **stats},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
