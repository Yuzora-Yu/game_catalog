from __future__ import annotations

import json
import unittest
from pathlib import Path

from catalog.build import build
from catalog.import_observations import merge_bundle
from catalog.validate import validate_catalog


class CatalogTests(unittest.TestCase):
    def test_seed_catalog_is_valid(self) -> None:
        self.assertEqual([], validate_catalog())

    def test_build_keeps_stream_pulse_compatibility(self) -> None:
        stats = build()
        self.assertEqual(150, stats["games"])
        master = json.loads(Path("dist/game_master.json").read_text(encoding="utf-8"))
        aliases = json.loads(Path("dist/aliases.json").read_text(encoding="utf-8"))
        self.assertEqual("Minecraft", master["minecraft"]["display_name"])
        self.assertIn("マイクラ", aliases["minecraft"])

    def test_observation_merge_keeps_latest_streams(self) -> None:
        stream = {
            "video_id": "abc",
            "url": "https://www.youtube.com/watch?v=abc",
            "observed_at": "2026-08-29T00:00:00Z",
            "channel_id": "c1",
            "channel_title": "A",
        }
        bundle = {
            "schema_version": 1,
            "source": "stream_pulse",
            "generated_at": "2026-08-29T00:00:00Z",
            "window": {
                "from": "2026-08-28T00:00:00Z",
                "to": "2026-08-29T00:00:00Z",
            },
            "games": {
                "minecraft": {
                    "first_seen": "2026-08-29T00:00:00Z",
                    "last_seen": "2026-08-29T00:00:00Z",
                    "observation_count": 1,
                    "latest_streams": [stream],
                }
            },
            "aliases": {
                "マイクラ新呼称": {
                    "display": "マイクラ新呼称",
                    "candidate_game_ids": ["minecraft"],
                    "first_seen": "2026-08-29T00:00:00Z",
                    "last_seen": "2026-08-29T00:00:00Z",
                    "observation_count": 1,
                    "channel_ids": ["c1"],
                    "latest_streams": [stream],
                    "status": "candidate",
                }
            },
        }
        empty = {
            "schema_version": 1,
            "source": "stream_pulse",
            "games": {},
            "aliases": {},
        }
        merged = merge_bundle(empty, bundle)
        observed = merged["aliases"]["マイクラ新呼称"]
        self.assertEqual("minecraft", observed["candidate_game_ids"][0])
        self.assertEqual(
            "abc",
            merged["games"]["minecraft"]["latest_streams"][0]["video_id"],
        )

    def test_observation_bundle_is_idempotent(self) -> None:
        bundle = {
            "schema_version": 1,
            "source": "stream_pulse",
            "bundle_id": "stream_pulse:2026-08-28:2026-08-29",
            "generated_at": "2026-08-29T00:00:00Z",
            "window": {"from": "2026-08-28", "to": "2026-08-29"},
            "games": {
                "minecraft": {
                    "first_seen": "2026-08-29T00:00:00Z",
                    "last_seen": "2026-08-29T00:00:00Z",
                    "observation_count": 3,
                    "latest_streams": [],
                }
            },
            "aliases": {},
        }
        empty = {
            "schema_version": 1,
            "source": "stream_pulse",
            "games": {},
            "aliases": {},
            "imported_bundles": [],
        }
        once = merge_bundle(empty, bundle)
        twice = merge_bundle(once, bundle)
        self.assertEqual(3, twice["games"]["minecraft"]["observation_count"])

    def test_overlapping_v2_bundles_only_count_new_snapshots(self) -> None:
        def bundle(bundle_id: str, snapshot_ids: list[str]) -> dict:
            return {
                "schema_version": 2,
                "source": "stream_pulse",
                "bundle_id": bundle_id,
                "generated_at": "2026-08-30T00:00:00Z",
                "window": {
                    "from": "2026-08-29T00:00:00Z",
                    "to": "2026-08-29T01:00:00Z",
                },
                "snapshot_counts": {
                    snapshot_id: {
                        "observed_at": f"2026-08-29T0{index}:00:00Z",
                        "games": {"minecraft": 1},
                        "aliases": {"マイクラ新呼称": 1},
                    }
                    for index, snapshot_id in enumerate(snapshot_ids)
                },
                "games": {
                    "minecraft": {
                        "first_seen": "2026-08-29T00:00:00Z",
                        "last_seen": "2026-08-29T01:00:00Z",
                        "observation_count": len(snapshot_ids),
                        "latest_streams": [],
                    }
                },
                "aliases": {
                    "マイクラ新呼称": {
                        "display": "マイクラ新呼称",
                        "candidate_game_ids": ["minecraft"],
                        "first_seen": "2026-08-29T00:00:00Z",
                        "last_seen": "2026-08-29T01:00:00Z",
                        "observation_count": len(snapshot_ids),
                        "channel_ids": ["c1"],
                        "latest_streams": [],
                        "status": "candidate",
                    }
                },
            }

        empty = {
            "schema_version": 1,
            "source": "stream_pulse",
            "games": {},
            "aliases": {},
            "imported_bundles": [],
            "imported_snapshot_ids": [],
            "legacy_imported_windows": [],
        }
        first = merge_bundle(empty, bundle("bundle-1", ["snapshot-1", "snapshot-2"]))
        second = merge_bundle(first, bundle("bundle-2", ["snapshot-2", "snapshot-3"]))
        self.assertEqual(3, second["games"]["minecraft"]["observation_count"])
        self.assertEqual(3, second["aliases"]["マイクラ新呼称"]["observation_count"])
        self.assertEqual(
            ["snapshot-1", "snapshot-2", "snapshot-3"],
            second["imported_snapshot_ids"],
        )

    def test_v2_migration_skips_snapshots_inside_legacy_window(self) -> None:
        current = {
            "schema_version": 1,
            "source": "stream_pulse",
            "games": {
                "minecraft": {
                    "first_seen": "2026-08-29T00:00:00Z",
                    "last_seen": "2026-08-29T00:30:00Z",
                    "observation_count": 2,
                    "latest_streams": [],
                }
            },
            "aliases": {},
            "imported_bundles": ["legacy"],
            "imported_snapshot_ids": [],
            "legacy_imported_windows": [
                {"from": "2026-08-29T00:00:00Z", "to": "2026-08-29T00:30:00Z"}
            ],
        }
        incoming = {
            "schema_version": 2,
            "source": "stream_pulse",
            "bundle_id": "bundle-v2",
            "generated_at": "2026-08-29T01:00:00Z",
            "window": {
                "from": "2026-08-29T00:30:00Z",
                "to": "2026-08-29T01:00:00Z",
            },
            "snapshot_counts": {
                "old": {
                    "observed_at": "2026-08-29T00:30:00Z",
                    "games": {"minecraft": 1},
                    "aliases": {},
                },
                "new": {
                    "observed_at": "2026-08-29T01:00:00Z",
                    "games": {"minecraft": 1},
                    "aliases": {},
                },
            },
            "games": {
                "minecraft": {
                    "first_seen": "2026-08-29T00:30:00Z",
                    "last_seen": "2026-08-29T01:00:00Z",
                    "observation_count": 2,
                    "latest_streams": [],
                }
            },
            "aliases": {},
        }
        merged = merge_bundle(current, incoming)
        self.assertEqual(3, merged["games"]["minecraft"]["observation_count"])
        self.assertEqual(["new", "old"], merged["imported_snapshot_ids"])


if __name__ == "__main__":
    unittest.main()
