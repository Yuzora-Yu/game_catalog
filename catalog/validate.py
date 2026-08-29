from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .core import GAMES_DIR, ROOT, load_games, load_json, normalize_text

GAME_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
QID = re.compile(r"^Q\d+$")
DATE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
VALID_STATUS = {"active", "inactive", "merged", "hidden"}
VALID_VERIFY = {"seed_unverified", "partially_verified", "verified", "needs_review"}
VALID_ALIAS_KIND = {
    "official",
    "abbreviation",
    "community",
    "stream_observed",
    "hashtag",
    "romanization",
    "typo",
    "seed",
}
VALID_COMPANY_ROLE = {"developer", "publisher", "porting", "other"}


def validate_game(game: dict[str, Any], path: Path) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "id",
        "status",
        "titles",
        "aliases",
        "releases",
        "companies",
        "platforms",
        "external_ids",
        "sales_observations",
        "verification",
    }
    missing = required - game.keys()
    if missing:
        errors.append(f"{path}: missing keys: {sorted(missing)}")
        return errors
    if game["schema_version"] != 1:
        errors.append(f"{path}: schema_version must be 1")
    game_id = str(game["id"])
    if not GAME_ID.fullmatch(game_id):
        errors.append(f"{path}: invalid id {game_id!r}")
    if path.stem != game_id:
        errors.append(f"{path}: filename must match id ({game_id}.json)")
    if game["status"] not in VALID_STATUS:
        errors.append(f"{path}: invalid status {game['status']!r}")
    titles = game.get("titles") or {}
    if not isinstance(titles, dict) or not str(titles.get("primary") or "").strip():
        errors.append(f"{path}: titles.primary is required")
    for key in ("ja", "en"):
        if key not in titles:
            errors.append(f"{path}: titles.{key} must exist (nullable)")
    aliases = game.get("aliases")
    if not isinstance(aliases, list):
        errors.append(f"{path}: aliases must be a list")
    else:
        seen: set[str] = set()
        for index, alias in enumerate(aliases):
            if not isinstance(alias, dict):
                errors.append(f"{path}: aliases[{index}] must be an object")
                continue
            text = str(alias.get("text") or "")
            normalized = str(alias.get("normalized") or "")
            if normalize_text(text) != normalized:
                errors.append(
                    f"{path}: alias normalization mismatch: {text!r} -> {normalized!r}"
                )
            if normalized in seen:
                errors.append(f"{path}: duplicate alias {normalized!r}")
            seen.add(normalized)
            if alias.get("kind") not in VALID_ALIAS_KIND:
                errors.append(f"{path}: invalid alias kind {alias.get('kind')!r}")
            if not alias.get("source"):
                errors.append(f"{path}: alias {text!r} missing source")
            variants = alias.get("variants") or []
            if not isinstance(variants, list):
                errors.append(f"{path}: alias {text!r} variants must be a list")
            elif any(normalize_text(str(value)) != normalized for value in variants):
                errors.append(f"{path}: alias {text!r} has incompatible variants")
    for index, release in enumerate(game.get("releases") or []):
        if not isinstance(release, dict) or not DATE.fullmatch(str(release.get("date") or "")):
            errors.append(f"{path}: releases[{index}] has invalid date")
    for index, company in enumerate(game.get("companies") or []):
        company_valid = (
            isinstance(company, dict)
            and company.get("role") in VALID_COMPANY_ROLE
            and bool(company.get("name"))
        )
        if not company_valid:
            errors.append(f"{path}: companies[{index}] is invalid")
    qid = (game.get("external_ids") or {}).get("wikidata")
    if qid is not None and not QID.fullmatch(str(qid)):
        errors.append(f"{path}: invalid Wikidata id {qid!r}")
    verification = game.get("verification") or {}
    if verification.get("status") not in VALID_VERIFY:
        errors.append(f"{path}: invalid verification status {verification.get('status')!r}")
    if not isinstance(verification.get("sources"), list):
        errors.append(f"{path}: verification.sources must be a list")
    return errors


def validate_observations(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{path}: missing observation store"]
    value = load_json(path)
    if value.get("schema_version") != 1:
        errors.append(f"{path}: schema_version must be 1")
    if value.get("source") != "stream_pulse":
        errors.append(f"{path}: source must be stream_pulse")
    if not isinstance(value.get("games"), dict):
        errors.append(f"{path}: games must be an object")
    if not isinstance(value.get("aliases"), dict):
        errors.append(f"{path}: aliases must be an object")
    return errors


def validate_catalog() -> list[str]:
    errors: list[str] = []
    games = load_games()
    ids: set[str] = set()
    alias_owners: dict[str, set[str]] = {}
    for path, game in zip(sorted(GAMES_DIR.glob("*.json")), games, strict=True):
        errors.extend(validate_game(game, path))
        game_id = str(game.get("id") or "")
        if game_id in ids:
            errors.append(f"duplicate game id: {game_id}")
        ids.add(game_id)
        for alias in game.get("aliases") or []:
            if isinstance(alias, dict):
                normalized = str(alias.get("normalized") or "")
                if normalized:
                    alias_owners.setdefault(normalized, set()).add(game_id)
    for alias, owners in sorted(alias_owners.items()):
        if len(owners) > 1:
            errors.append(f"alias collision {alias!r}: {sorted(owners)}")
    errors.extend(
        validate_observations(ROOT / "data" / "observations" / "stream_pulse.json")
    )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    errors = validate_catalog()
    if errors:
        print(json.dumps({"status": "error", "errors": errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    print(json.dumps({"status": "ok", "games": len(load_games())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
