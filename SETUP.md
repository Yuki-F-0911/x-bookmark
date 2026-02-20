# セットアップガイド

## 全体の流れ

```
[Chrome拡張] CSVエクスポート
    ↓ (Downloadsに保存)
[watcher.py] 自動検知 → git push
    ↓ (bookmarks.jsonのpushで起動)
[GitHub Actions: daily-digest]
    ↓ Claude API で要約・重要度判定
[Slack] ダイジェスト受信
    ↓ @bot にメンション
[Cloudflare Worker] 中継
    ↓ repository_dispatch
[GitHub Actions: slack-bot]
    ↓ Claude API でQ&A
[Slack] 返信受信
```

---

## ① 自動Push (watcher.py) のセットアップ

### 1. Gitの認証設定
```powershell
# GitHub PAT（Personal Access Token）でHTTPS認証
git config --global credential.helper manager
```
または `~/.ssh/config` でSSH鍵を設定済みであればそのままでOK。

### 2. watcher.pyの設定（環境変数で変更可能）
| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `WATCH_DIR` | `~/Downloads` | Chrome拡張がCSVを保存するフォルダ |
| `CSV_PATTERN` | `bookmarks*.csv` | 対象ファイルのパターン |
| `REPO_DIR` | スクリプトと同じフォルダ | このリポジトリのパス |

Chrome拡張が別のファイル名で保存する場合は `CSV_PATTERN` を変更してください。

### 3. Windowsタスクスケジューラへの登録
PowerShellを**管理者権限**で開き:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
cd C:\Users\yuki0\x-bookmark-digest
.\setup_task_scheduler.ps1
```

登録後、今すぐ起動する場合:
```powershell
Start-ScheduledTask -TaskName "XBookmarkWatcher"
```

ログの確認:
```powershell
Get-Content C:\Users\yuki0\x-bookmark-digest\watcher.log -Tail 20
```

---

## ② GitHub Secrets の設定

https://github.com/Yuki-F-0911/x-bookmark/settings/secrets/actions で以下を追加:

| Secret名 | 値 | 入手方法 |
|----------|---|---------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | https://console.anthropic.com/ |
| `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/...` | ③で取得（ダイジェスト送信用） |
| `SLACK_BOT_TOKEN` | `xoxb-...` | ③で取得（Bot返信用） |

---

## ③ Slack App のセットアップ

### 1. Slack Appを作成
1. https://api.slack.com/apps → **Create New App** → **From scratch**
2. App Name: `X Bookmark Digest Bot`、Workspace を選択

### 2. Bot Tokenを取得
1. **OAuth & Permissions** → **Scopes** → **Bot Token Scopes** に追加:
   - `app_mentions:read`（メンション読み取り）
   - `chat:write`（メッセージ投稿）
2. **Install to Workspace** → `xoxb-...` をコピー
3. GitHub Secret `SLACK_BOT_TOKEN` に設定

### 3. Event Subscriptions を設定（Cloudflare Worker後）
※ Worker URLが必要なため、⑤完了後に設定

---

## ④ Cloudflare Worker のデプロイ

### 1. Cloudflareアカウント作成
https://cloudflare.com/ （無料プランでOK）

### 2. Wranglerのインストールとデプロイ
```powershell
npm install -g wrangler
wrangler login

cd C:\Users\yuki0\x-bookmark-digest\slack_gateway
wrangler deploy
```

デプロイ後、URLが表示されます（例: `https://x-bookmark-slack-gateway.yourname.workers.dev`）

### 3. 環境変数の設定
Cloudflare Dashboard → Workers → `x-bookmark-slack-gateway` → Settings → Variables:

| 変数名 | 値 |
|--------|---|
| `SLACK_BOT_TOKEN` | `xoxb-...` |
| `SLACK_SIGNING_SECRET` | Slack App → Basic Information → Signing Secret |
| `GITHUB_TOKEN` | GitHub PAT（`repo` スコープ） |
| `GITHUB_REPO` | `Yuki-F-0911/x-bookmark` |

GitHub PATの作成: https://github.com/settings/tokens → **Fine-grained token** → `contents: read/write`, `actions: write`

---

## ⑤ Slack Event Subscriptions の設定

1. Slack App → **Event Subscriptions** → Enable
2. **Request URL**: `https://x-bookmark-slack-gateway.yourname.workers.dev`
3. **Subscribe to bot events** → `app_mention` を追加
4. **Save Changes**

---

## ⑥ BotをSlackチャンネルに追加

Slackで対象チャンネルを開き:
```
/invite @X Bookmark Digest Bot
```

---

## ⑦ 動作確認

### 自動Push確認
1. Chrome拡張でエクスポート
2. `watcher.log` に「✅ GitHubへのpushが完了」が出ることを確認
3. GitHub Actionsが自動起動することを確認

### Slack Bot確認
```
@X Bookmark Digest Bot 今日の重要なブックマークを3つ教えて
@X Bookmark Digest Bot AI関係のブックマークだけまとめて
@X Bookmark Digest Bot いいね数が多い順に5つ教えて
```

---

## トラブルシューティング

### watcher.py が動かない
```powershell
# 手動実行でエラー確認
python C:\Users\yuki0\x-bookmark-digest\watcher.py
```

### Slack Botが返信しない
1. GitHub Actions → `slack-bot` ワークフローのログを確認
2. `digest_cache.json` がリポジトリに存在するか確認（daily-digestを一度実行する必要あり）
3. Cloudflare Worker のログ確認: `wrangler tail`

### CSV_PATTERNの確認方法
Chrome拡張でエクスポートして実際のファイル名を確認し、`WATCH_DIR` 環境変数で設定:
```powershell
$env:CSV_PATTERN = "bookmarks*.csv"  # 実際のファイル名に合わせる
python watcher.py
```
