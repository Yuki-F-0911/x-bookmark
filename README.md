# X Bookmark Daily Digest 🔖

Xのブックマークを毎日自動で要約してSlackに通知するサービスです。

- **ブックマーク取得**: Chrome拡張でエクスポートしたJSONを使用（X API不要・無料）
- **要約・カテゴリ分け**: Claude API（claude-sonnet-4-5）でバッチ処理
- **補足情報**: DuckDuckGo検索でキーワードの関連情報を自動収集（無料・APIキー不要）
- **Slack通知**: Block Kit 形式でリッチな通知
- **自動実行**: GitHub Actions（毎日JST 7:00 + bookmarks.json 更新時）

## コスト（月額）

| 項目 | 金額 |
|---|---|
| X API | **¥0**（ブラウザ拡張で代替） |
| Claude API | **約 $0.60/月**（約90円） |
| DuckDuckGo検索 | **¥0** |
| GitHub Actions | **¥0**（無料枠内） |

---

## セットアップ手順

### Step 1: リポジトリをクローン

```bash
git clone https://github.com/yourusername/x-bookmark-digest.git
cd x-bookmark-digest
```

### Step 2: Anthropic API キーを取得

1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. 「API Keys」→「Create Key」でAPIキーを作成
3. キーをメモしておく（`sk-ant-...`で始まる文字列）

### Step 3: Slack Incoming Webhook を設定

1. [Slack API](https://api.slack.com/apps) にアクセス
2. 「Create New App」→「From scratch」
3. アプリ名を入力（例: `X Bookmark Digest`）してワークスペースを選択
4. 「Incoming Webhooks」を有効化
5. 「Add New Webhook to Workspace」で通知先チャンネルを選択
6. 生成された Webhook URL をメモ（`https://hooks.slack.com/services/...`）

### Step 4: GitHub Secrets を設定

GitHubリポジトリの **Settings → Secrets and variables → Actions** で以下を追加:

| 名前 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | Step 2 で取得したAPIキー |
| `SLACK_WEBHOOK_URL` | Step 3 で取得したWebhook URL |

### Step 5: Chrome拡張をインストール

[X Bookmarks Exporter](https://chromewebstore.google.com/detail/x-bookmarks-exporter-expo/abgjpimjfnggkhnoehjndcociampccnm) をChromeに追加します。

---

## 毎日の使い方（1〜2分）

1. **Xを開く** → ブックマークページ（https://x.com/i/bookmarks）に移動
2. **拡張アイコンをクリック** → 「Export JSON」を選択
3. **ダウンロードされたファイルを** `bookmarks.json` にリネームしてリポジトリに配置

```bash
cp ~/Downloads/bookmarks_export.json ./bookmarks.json
git add bookmarks.json
git commit -m "update bookmarks"
git push
```

→ プッシュすると **GitHub Actions が自動起動** → Slack に通知が届きます！

---

## ローカルでのテスト

### 環境構築

```bash
pip install -r requirements.txt
cp .env.example .env
# .env を編集して実際のAPIキーを設定
```

### サンプルデータで動作確認

```bash
# サンプルデータで実行（Slack送信あり）
cp bookmarks_sample.json bookmarks.json
python -m src.main

# Slack送信をスキップしてコンソール確認のみ
python -m src.main --dry-run

# 全件処理（処理済みキャッシュを無視）
python -m src.main --no-cache
```

### テスト実行

```bash
pip install pytest
pytest tests/ -v
```

---

## Slackメッセージのイメージ

```
📚 今日のX Bookmark Digest（2026年2月19日）
合計 5 件 ｜ モデル: claude-sonnet-4-5 / claude-haiku-4-5 ｜ トークン: 3,420
━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI・テック（2件）

@AnthropicAI 👍 12,500
Claude 3.5 Sonnetがリリース。コーディング能力が大幅向上し、特にエージェント型タスクで圧倒的なパフォーマンスを発揮する。APIは即時利用可能。
> Anthropicの新モデル発表に対し、開発者コミュニティでは実装コストの低下を歓迎する声が多い。
🔗 関連: Claude 3.5 Sonnet Release Notes / Anthropic Blog

💼 ビジネス・経営（1件）
...
```

---

## ファイル構成

```
x-bookmark-digest/
├── src/
│   ├── main.py              # エントリポイント
│   ├── bookmark_loader.py   # JSON/CSVブックマーク読み込み
│   ├── search_enricher.py   # DuckDuckGo検索でキーワード補足
│   ├── summarizer.py        # Claude API 要約・カテゴリ分け
│   ├── slack_notifier.py    # Slack Block Kit 通知
│   ├── models.py            # データクラス
│   └── utils.py             # ロギング・リトライ
├── tests/                   # ユニットテスト
├── .github/
│   └── workflows/
│       └── daily-digest.yml # GitHub Actions 設定
├── bookmarks.json           # ← ここに毎日JSONを置く
├── bookmarks_sample.json    # サンプルデータ
├── processed_ids.json       # 処理済みIDキャッシュ（自動生成）
└── .env.example             # 環境変数テンプレート
```

---

## 対応しているブックマークエクスポート形式

- **X Bookmarks Exporter**（推奨）: JSON / CSV
- **twitter-web-exporter**: JSON
- カスタム形式: `id`, `text`, `user.screen_name` があれば概ね対応

---

## トラブルシューティング

### `bookmarks.json が見つかりません`
→ ブックマークをエクスポートしてリポジトリのルートに配置してください。

### Slack に通知が届かない
→ GitHub Secrets の `SLACK_WEBHOOK_URL` が正しく設定されているか確認してください。

### `anthropic.APIError`
→ `ANTHROPIC_API_KEY` が正しいか、残高があるか確認してください。

### 同じブックマークが何度も通知される
→ `processed_ids.json` が正しく保存されているか確認してください。
手動でリセットする場合: `processed_ids.json` を削除してください。
