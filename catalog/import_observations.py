from __future__ import annotations

import argparse
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


def merge_bundle(current: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("schema_version") != 1 or bundle.get("source") != "stream_pulse":
        raise ValueError("Unsupported observation bundle")
    bundle_id = str(bundle.get("bundle_id") or bundle.get("generated_at") or "")
    imported = list(current.get("imported_bundles") or [])
    if bundle_id and bundle_id in imported:
        return current
    merged = {
        "schema_version": 1,
        "source": "stream_pulse",
        "updated_at": bundle.get("generated_at"),
        "imported_bundles": [*imported, bundle_id][-104:] if bundle_id else imported,
        "games": dict(current.get("games") or {}),
        "aliases": dict(current.get("aliases") or {}),
    }
    for game_id, incoming in (bundle.get("games") or {}).items():
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
                + int(incoming.get("observation_count") or 0)
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
                + int(incoming.get("observation_count") or 0)
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
        }
    merged = merge_bundle(current, load_json(args.bundle))
    write_json(args.output, merged)
    print(f"merged {len(merged['games'])} games and {len(merged['aliases'])} aliases")


if __name__ == "__main__":
    main()
