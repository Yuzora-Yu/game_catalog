# セットアップ

## 0. 役割

- `game_catalog`: ゲーム実体マスタ、alias、配信観測の集約、GitHub Pages。
- `stream_pulse`: YouTube観測センサー。週1回、直近7日間の観測を `game_catalog` へPRで送る。
- `GAME_CATALOG_TOKEN`: `stream_pulse` Actions が `game_catalog` にbranch push / PR作成するためだけの連携用token。

## 1. game_catalog を新規GitHub repositoryへpush

想定名: `Yuzora-Yu/game_catalog`。

初回pushで `.github/workflows/**` も追加するため、HTTPS + PATでpushする場合は、その「初回pushに使う認証」側にworkflowファイルを更新できる権限が必要です。これは後述の `GAME_CATALOG_TOKEN` とは別物です。

## 2. game_catalog のActions設定

GitHubの `game_catalog` → Settings → Actions → General → Workflow permissions で、ActionsがbranchをpushしPull Requestを作成できる状態にします。

特に `Allow GitHub Actions to create and approve pull requests` を有効にします。

## 3. game_catalog のPages設定

Settings → Pages → Build and deployment → Source を `GitHub Actions` にします。

`.github/workflows/pages.yml` が `public/` をdeployします。

## 4. stream_pulse に連携用資格情報を追加

`stream_pulse` の Settings → Secrets and variables → Actions。

Repository secret:

- `GAME_CATALOG_TOKEN`: `game_catalog` のみを対象にする fine-grained PAT。最低限 Contents: Read and write / Pull requests: Read and write。

Repository variable:

- `GAME_CATALOG_REPO`: `Yuzora-Yu/game_catalog`

既存のR2資格情報も `catalog-sync.yml` が利用します。

- Secret `R2_ACCOUNT_ID`
- Secret `R2_ACCESS_KEY_ID`
- Secret `R2_SECRET_ACCESS_KEY`
- Variable `R2_BUCKET`

## 5. stream_pulse のActions設定

`stream_pulse` → Settings → Actions → General → Workflow permissions で `Allow GitHub Actions to create and approve pull requests` を有効にします。`catalog-refresh.yml` がstream_pulse自身に更新PRを作るために必要です。

## 6. 動作確認順

1. `game_catalog` の Actions → `Quality gate` → Run workflow。
2. `game_catalog` の Actions → `Deploy catalog to GitHub Pages` → Run workflow。
3. `stream_pulse` の Actions → `Refresh compiled game catalog` → Run workflow。初期状態では差分なしでも正常です。ここでcross-repo checkoutが成功すればtoken設定は概ねOKです。
4. `stream_pulse` の Actions → `Sync observations to game_catalog` → Run workflow。R2の直近7日間からbundleを作り、`game_catalog` にPRを作ります。
5. 作成された `game_catalog` PRを確認してmerge。
6. merge後にPages/Qualityが通ることを確認。
7. `game_catalog` の Actions → `Weekly Wikidata review proposals` → Run workflow。候補PRだけ作られます。

## 7. 週次Wikidata候補PR

`.github/workflows/wikidata-review.yml` は候補だけを生成します。自動でゲームファイルを書き換えません。

## 8. AIレビュー

`docs/AI_REVIEW_PROMPT.md` の指示で `data/review/wikidata-proposals.json` と `dist/review-queue.json` をレビューし、確信度の高い対応だけ `data/review/wikidata-reviewed.json` またはゲームJSONへの変更としてPRにします。
