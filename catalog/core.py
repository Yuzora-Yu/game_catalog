from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GAMES_DIR = ROOT / "data" / "games"
OBSERVATIONS_PATH = ROOT / "data" / "observations" / "stream_pulse.json"


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").lower()
    value = re.sub(r"[\s\u3000]+", " ", value)
    return value.strip()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_games() -> list[dict[str, Any]]:
    return [load_json(path) for path in sorted(GAMES_DIR.glob("*.json"))]
