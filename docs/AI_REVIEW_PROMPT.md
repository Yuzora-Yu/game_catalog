# AI review prompt

このrepositoryはゲーム実体マスタです。推測でmasterを埋めないでください。

入力:
- `data/review/wikidata-proposals.json`: Wikidata検索候補
- `dist/review-queue.json`: stream_pulseで観測された未解決alias
- `data/games/*.json`: 既存ゲーム

作業:
1. 未解決aliasが既存ゲームの略称・表記ゆれか、新規ゲームか、ゲーム以外かを判定する。
2. 既存ゲームなら `aliases[]` に `kind=stream_observed` として追加候補を作る。
3. 新規ゲームなら、公式サイトまたは信頼できる一次情報を優先して正式名称、発売日、開発/発売会社、機種、Wikidata IDを調査する。
4. Wikidata候補は同名作品・シリーズ・DLC・リメイクを区別する。確信できないものは変更せず `needs_review` とする。
5. 売上は一次資料で時点・範囲・指標が分かる場合だけ `sales_observations[]` に追加する。
6. すべての外部情報に出典URLを残す。

禁止:
- 観測回数が多いという理由だけで未知語を新規ゲームにする。
- AIの内部知識だけを根拠に `verified` にする。
- シリーズ名を個別ゲームへ、DLCを本編へ無条件に統合する。
