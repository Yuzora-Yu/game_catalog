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


if __name__ == "__main__":
    unittest.main()
