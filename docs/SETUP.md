# セットアップ

## 1. game_catalog を新規GitHub repositoryへpush

想定名: `Yuzora-Yu/game_catalog`。GitHub Pages の Source は GitHub Actions を選択します。

## 2. stream_pulse に同期用資格情報を追加

`stream_pulse` の Actions secret:

- `GAME_CATALOG_TOKEN`: `game_catalog` の Contents: Read and write / Pull requests: Read and write を持つ fine-grained PAT、または同等権限のGitHub App token。

Actions variable:

- `GAME_CATALOG_REPO`: 例 `Yuzora-Yu/game_catalog`

既存のR2資格情報も `catalog-sync.yml` が利用します。

## 3. game_catalog の週次Wikidata候補PR

`.github/workflows/wikidata-review.yml` は候補だけを生成します。自動でゲームファイルを書き換えません。

## 4. AIレビュー

`docs/AI_REVIEW_PROMPT.md` の指示で `data/review/wikidata-proposals.json` と `dist/review-queue.json` をレビューし、確信度の高い対応だけ `data/review/wikidata-reviewed.json` またはゲームJSONへの変更としてPRにします。
