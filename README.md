# GAME CATALOG / 歴代ゲーム辞典

`stream_pulse` の分類辞書を、ゲーム実体マスタと配信由来の観測データに分離するための参照リポジトリです。

## 役割

- `data/games/*.json`: ゲーム実体。正式名、発売日、会社、機種、外部ID、売上観測値など。
- `data/observations/stream_pulse.json`: 配信で観測した表記ゆれと直近配信。高頻度rawログそのものは置かない。
- `dist/game_master.json` / `dist/aliases.json`: `stream_pulse` がそのまま読める互換ビルド。
- `dist/review-queue.json`: 既存ゲームに紐付かなかった候補。
- `public/`: GitHub Pages 用の検索ページ。

初期データは `stream_pulse` の150ゲーム / 475 raw alias表記を移植しています。移植時点では外部ソースで正式情報を再確認していないため、全件 `seed_unverified` です。NFKCで同一になる表記は1検索キーにまとめ、元表記は `variants` に保持します。

## データ原則

1. **未知文字列と未知ゲームを分ける。** 配信で新しい語を見てもゲーム実体を自動生成しない。
2. **AIは提案まで。** Wikidata候補や新規ゲーム候補はレビュー用JSON/PRにし、masterへ自動確定しない。
3. **出典を持つ。** 正式情報を埋める時は `verification.sources` と各release/companyの `source_url` を残す。
4. **売上は観測値。** 世界/国内、出荷/実売、時点を潰さず `sales_observations[]` に追加する。
5. **配信rawは外部保管。** Gitには集約値と最新5配信だけを同期する。

## ローカル操作

```bash
python -m catalog.validate
python -m unittest discover -s tests -p "test_*.py"
python -m catalog.build
```

GitHub Pages用成果物は `public/` に生成されます。

## Wikidata候補の収集

候補取得は自動確定しません。

```bash
python -m catalog.enrich_wikidata --limit 50
```

`data/review/wikidata-proposals.json` を確認し、採用する対応だけ次の形式にします。

```json
{
  "minecraft": {
    "wikidata": "Q49740",
    "ja": "Minecraft",
    "en": "Minecraft"
  }
}
```

適用:

```bash
python -m catalog.apply_review data/review/wikidata-reviewed.json
python -m catalog.validate
python -m catalog.build
```

## Steam公式タイトルの一括追加

Steam公式ストアのゲームカテゴリ上位から、英語名・日本向け表示名・Steam App IDを
取り込みます。既存ゲームと正式名が一致した場合は別ゲームを作らず、正式名とIDを
補強します。短すぎる名前やDemo / Playtest等は分類事故を避けるため除外します。

```bash
python -m catalog.import_steam_games --limit 400
python -m catalog.import_steam_games --limit 800 --tag 492   # Indie
python -m catalog.import_steam_games --limit 620 --tag 4004  # Retro
python -m catalog.validate
python -m catalog.build
```

GitHub Actionsでも毎週火曜04:15（JST）に同じ処理を実行し、変更がある時だけ
通常上位・インディー・レトロの3群をまとめたレビュー用PRを作ります。
自動マージはしません。

## コンソール定番旧作の初期シード

Steamに載りにくいFC / SFC / Nintendo 64 / Game Boy / PlayStation /
Dreamcast / アーケードの定番旧作は、別の初期シードとして取り込みます。
Steam確認済みデータとは区別し、Wikidata等で後から確認できる状態にします。

```bash
python -m catalog.import_seed_games data/seeds/console-classics.json
python -m catalog.validate
python -m catalog.build
```

## stream_pulse からの同期

`stream_pulse` 側で直近168時間（7日間）のraw snapshotからコンパクトなbundleを生成し、このrepoへ週次PRで渡します。

```bash
python -m src.catalog_sync --output runtime/stream-pulse-observations.json
```

このrepo側では:

```bash
python -m catalog.import_observations incoming/stream_pulse/latest.json
python -m catalog.build
```

必要なGitHub設定は `docs/SETUP.md` を参照してください。
