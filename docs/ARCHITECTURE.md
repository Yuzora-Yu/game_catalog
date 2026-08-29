# Architecture

## Boundary

`game_catalog` owns **game identity**. `stream_pulse` owns **stream observations**.

```text
YouTube Data API
      |
      v
stream_pulse -- private raw --> R2
      |
      | weekly compact bundle
      v
game_catalog incoming -> observation aggregate -> review queue
      |                                      |
      | compiled compatibility files         | AI / human review
      v                                      v
stream_pulse config <---------------- game master JSON
```

## Game identity

Stable key: `data/games/<game_id>.json` の `id`。

The stable ID is intentionally independent from Wikidata/IGDB IDs. External IDs can change or be absent, while stream history must retain the same internal key.

## Alias identity

Classification keys use the same NFKC + lowercase + whitespace normalization as `stream_pulse`. Multiple raw spellings that collapse to the same key are kept in `aliases[].variants`.

An observed alias is not automatically a canonical alias. It stays in `data/observations/stream_pulse.json` until reviewed.

## Observation retention

R2 remains the raw source of truth. Git stores only:

- first / last observation
- cumulative observation count
- bounded channel IDs for review support
- latest five distinct stream links
- unresolved alias candidates

Weekly bundles have deterministic `bundle_id` values so rerunning the same observation window is idempotent.

## Publication

`catalog.build` creates two output surfaces:

- machine compatibility: `dist/game_master.json`, `dist/aliases.json`, `dist/alias-index.json`
- human browsing: `public/` for GitHub Pages

The checked-in seed currently preserves the exact `stream_pulse` game master and equivalent normalized alias sets.
