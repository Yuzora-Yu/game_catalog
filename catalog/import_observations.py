from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from .core import OBSERVATIONS_PATH, load_json, normalize_text, write_json

MAX_STREAMS = 5
MAX_CHANNEL_IDS = 100


def _merge_streams(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_video: dict[str, dict[str, Any]] = {}
    for stream in [*old, *new]:
        key = str(stream.get("video_id") or stream.get("url") or "")
        if key:
            by_video[key] = stream
    return sorted(
        by_video.values(),
        key=lambda row: str(row.get("observed_at") or ""),
        reverse=True,
    )[:MAX_STREAMS]


def _earliest(*values: Any) -> Any:
    return min(filter(None, values), default=None)


def _latest(*values: Any) -> Any:
    return max(filter(None, values), default=None)


def _inside_legacy_window(observed_at: Any, windows: list[dict[str, Any]]) -> bool:
    timestamp = str(observed_at or "")
    if not timestamp:
        return False
    return any(
        str(window.get("from") or "") <= timestamp <= str(window.get("to") or "")
        for window in windows
        if window.get("from") and window.get("to")
    )


def _v2_increments(
    current: dict[str, Any], bundle: dict[str, Any]
) -> tuple[list[str], Counter[str], Counter[str]]:
    snapshot_counts = bundle.get("snapshot_counts")
    if not isinstance(snapshot_counts, dict):
        raise ValueError("schema_version 2 bundle requires snapshot_counts")

    imported = set(current.get("imported_snapshot_ids") or [])
    legacy_windows = list(current.get("legacy_imported_windows") or [])
    game_counts: Counter[str] = Counter()
    alias_counts: Counter[str] = Counter()
    seen_ids: list[str] = []
    for snapshot_id, contribution in snapshot_counts.items():
        snapshot_id = str(snapshot_id)
        if not snapshot_id:
            raise ValueError("snapshot ID must not be empty")
        seen_ids.append(snapshot_id)
        if snapshot_id in imported or _inside_legacy_window(
            contribution.get("observed_at"), legacy_windows
        ):
            continue
        for game_id, count in (contribution.get("games") or {}).items():
            game_counts[str(game_id)] += int(count)
        for alias, count in (contribution.get("aliases") or {}).items():
            alias_counts[normalize_text(str(alias))] += int(count)

    expected_games = Counter(
        {
            str(game_id): int(entry.get("observation_count") or 0)
            for game_id, entry in (bundle.get("games") or {}).items()
        }
    )
    expected_aliases = Counter(
        {
            normalize_text(str(alias)): int(entry.get("observation_count") or 0)
            for alias, entry in (bundle.get("aliases") or {}).items()
        }
    )
    total_games: Counter[str] = Counter()
    total_aliases: Counter[str] = Counter()
    for contribution in snapshot_counts.values():
        total_games.update(
            {str(key): int(value) for key, value in (contribution.get("games") or {}).items()}
        )
        total_aliases.update(
            {
                normalize_text(str(key)): int(value)
                for key, value in (contribution.get("aliases") or {}).items()
            }
        )
    if total_games != expected_games or total_aliases != expected_aliases:
        raise ValueError("snapshot_counts do not match bundle aggregates")
    return seen_ids, game_counts, alias_counts


def merge_bundle(current: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    schema_version = bundle.get("schema_version")
    if schema_version not in {1, 2} or bundle.get("source") != "stream_pulse":
        raise ValueError("Unsupported observation bundle")
    bundle_id = str(bundle.get("bundle_id") or bundle.get("generated_at") or "")
    imported = list(current.get("imported_bundles") or [])
    if bundle_id and bundle_id in imported:
        return current
    if schema_version == 2:
        snapshot_ids, game_increments, alias_increments = _v2_increments(current, bundle)
    else:
        snapshot_ids = []
        game_increments = Counter(
            {
                str(game_id): int(entry.get("observation_count") or 0)
                for game_id, entry in (bundle.get("games") or {}).items()
            }
        )
        alias_increments = Counter(
            {
                normalize_text(str(alias)): int(entry.get("observation_count") or 0)
                for alias, entry in (bundle.get("aliases") or {}).items()
            }
        )
    merged = {
        "schema_version": 1,
        "source": "stream_pulse",
        "updated_at": bundle.get("generated_at"),
        "imported_bundles": [*imported, bundle_id][-104:] if bundle_id else imported,
        "imported_snapshot_ids": sorted(
            set(current.get("imported_snapshot_ids") or []) | set(snapshot_ids)
        ),
        "legacy_imported_windows": list(current.get("legacy_imported_windows") or []),
        "games": dict(current.get("games") or {}),
        "aliases": dict(current.get("aliases") or {}),
    }
    for game_id, incoming in (bundle.get("games") or {}).items():
        increment = game_increments.get(str(game_id), 0)
        if increment <= 0:
            continue
        previous = merged["games"].get(game_id, {})
        merged["games"][game_id] = {
            "first_seen": _earliest(
                previous.get("first_seen"),
                incoming.get("first_seen"),
            ),
            "last_seen": _latest(
                previous.get("last_seen"),
                incoming.get("last_seen"),
            ),
            "observation_count": (
                int(previous.get("observation_count") or 0)
                + increment
            ),
            "latest_streams": _merge_streams(
                previous.get("latest_streams") or [],
                incoming.get("latest_streams") or [],
            ),
        }
    for raw_alias, incoming in (bundle.get("aliases") or {}).items():
        alias = normalize_text(raw_alias)
        if not alias:
            continue
        increment = alias_increments.get(alias, 0)
        if increment <= 0:
            continue
        previous = merged["aliases"].get(alias, {})
        candidate_ids = sorted(
            set(previous.get("candidate_game_ids") or [])
            | set(incoming.get("candidate_game_ids") or [])
        )
        channels = sorted(
            set(previous.get("channel_ids") or [])
            | set(incoming.get("channel_ids") or [])
        )[-MAX_CHANNEL_IDS:]
        merged["aliases"][alias] = {
            "display": incoming.get("display") or previous.get("display") or raw_alias,
            "candidate_game_ids": candidate_ids,
            "first_seen": _earliest(
                previous.get("first_seen"),
                incoming.get("first_seen"),
            ),
            "last_seen": _latest(
                previous.get("last_seen"),
                incoming.get("last_seen"),
            ),
            "observation_count": (
                int(previous.get("observation_count") or 0)
                + increment
            ),
            "channel_ids": channels,
            "channel_count": len(channels),
            "latest_streams": _merge_streams(
                previous.get("latest_streams") or [],
                incoming.get("latest_streams") or [],
            ),
            "status": incoming.get("status") or previous.get("status") or "candidate",
        }
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge a compact stream_pulse observation bundle"
    )
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, default=OBSERVATIONS_PATH)
    args = parser.parse_args()
    if args.output.exists():
        current = load_json(args.output)
    else:
        current = {
            "schema_version": 1,
            "source": "stream_pulse",
            "games": {},
            "aliases": {},
            "imported_bundles": [],
            "imported_snapshot_ids": [],
            "legacy_imported_windows": [],
        }
    merged = merge_bundle(current, load_json(args.bundle))
    write_json(args.output, merged)
    print(f"merged {len(merged['games'])} games and {len(merged['aliases'])} aliases")


if __name__ == "__main__":
    main()
