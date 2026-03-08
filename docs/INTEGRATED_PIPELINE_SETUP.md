# 統合パイプライン - 完全セットアップガイド

## 📋 概要

このドキュメントは、手動ブックマークと自動取得記事の両方を処理する **統合パイプライン** のセットアップと運用方法です。

---

## 🎯 システムアーキテクチャ

```
【毎日午前9時】
└─ daily_business_themes_pipeline.py
   └─ bookmarks.json（手動ブックマーク）を処理
   └─ テーマリスト生成
   └─ 保存: note_themes/themes_YYYYMMDD.md

【毎日午前9時30分】（新規）
└─ integrated_daily_pipeline.py
   ├─ ステップ1: 手動ブックマーク（bookmarks.json）を読み込み
   ├─ ステップ2: 複数ソースから自動取得
   │   ├─ Slack x-bookmarks チャンネル
   │   ├─ Web検索（ビジネスキーワード）
   │   └─ 人気ニュースサイト（Product Hunt, Hacker News等）
   ├─ ステップ3: 両方をマージ
   ├─ ステップ4: テーマ分類・スコアリング
   └─ 保存: note_themes/themes_YYYYMMDD_integrated.md
```

---

## 🔧 セットアップ手順

### 前提条件

- Python 3.10以上
- Windows PowerShell（管理者権限）
- 既存パイプラインがセットアップされていること

### 1️⃣ スクリプトの配置確認

以下のファイルが `C:\Users\yuki0\x-bookmark-digest\` に配置されていることを確認：

```
✓ auto_fetch_business_articles.py      （新規）
✓ integrated_daily_pipeline.py          （新規）
✓ extract_business_themes.py            （既存）
✓ bookmarks.json                        （既存）
```

### 2️⃣ テスト実行

```bash
cd C:\Users\yuki0\x-bookmark-digest

# 統合パイプラインのテスト実行
python integrated_daily_pipeline.py

# 成功すれば：
# [TIMESTAMP] [DONE] パイプライン完了
```

### 3️⃣ タスクスケジューラー登録

**PowerShell（管理者権限）で以下を実行：**

```powershell
# 既存パイプライン（午前9時）
$trigger1 = New-ScheduledTaskTrigger -Daily -At 09:00
$action1 = New-ScheduledTaskAction -Execute 'python.exe' `
  -Argument 'C:\Users\yuki0\x-bookmark-digest\daily_business_themes_pipeline.py' `
  -WorkingDirectory 'C:\Users\yuki0\x-bookmark-digest'
Register-ScheduledTask -TaskName "NaruseNoteThemesDaily" `
  -Trigger $trigger1 -Action $action1 -Force

# 統合パイプライン（午前9時30分）← 新規追加
$trigger2 = New-ScheduledTaskTrigger -Daily -At 09:30
$action2 = New-ScheduledTaskAction -Execute 'python.exe' `
  -Argument 'C:\Users\yuki0\x-bookmark-digest\integrated_daily_pipeline.py' `
  -WorkingDirectory 'C:\Users\yuki0\x-bookmark-digest'
Register-ScheduledTask -TaskName "NaruseNoteThemesIntegrated" `
  -Trigger $trigger2 -Action $action2 -Force
```

### 4️⃣ 設定確認

```powershell
# タスク一覧表示
Get-ScheduledTask -TaskName "NaroseNote*"

# 実行テスト
Start-ScheduledTask -TaskName "NaruseNoteThemesIntegrated"

# ログ確認
Get-Content C:\Users\yuki0\x-bookmark-digest\integrated_pipeline_logs.txt -Tail 20
```

---

## 📊 データソース詳細

### 🔹 ソース1: 手動ブックマーク
- **ファイル**: `bookmarks.json`
- **取得方法**: Chrome「X Bookmarks Exporter」エクステンション
- **更新頻度**: 不定期（ユーザーが手動でエクスポート）
- **データ数**: 通常20-50件/回

### 🔹 ソース2: Web検索（自動）
- **キーワード**: AI、経営戦略、起業、チームビルディング等
- **更新頻度**: 毎日（自動）
- **データ数**: キーワード数 × 検索結果
- **実装**: `fetch_business_topics_v2.py`経由

### 🔹 ソース3: Slack x-bookmarks
- **チャンネルID**: `C0AFGGGTY5D`
- **更新頻度**: Slack Botが毎日投稿
- **データ数**: 30-50件/日
- **実装**: Slack MCP連携

### 🔹 ソース4: 人気ニュースサイト
- **サイト**: Product Hunt, Hacker News, DEV.to
- **更新頻度**: 毎日（各サイト）
- **データ数**: 5-20件/サイト
- **実装**: RSS/API経由

---

## 📈 パイプラインの出力

### 📂 生成ファイル

```
note_themes/
├── themes_YYYYMMDD.md              （既存：手動ブックマークのみ）
├── themes_YYYYMMDD_integrated.md   （新規：統合版）
└── README.md
```

### 📊 コンテンツ例

```markdown
# 成瀬さんのnote題材候補 - 2026年03月02日（統合版）

## 📊 統計
- 手動ブックマーク: 30件
- 自動取得記事: 25件
- 合計: 55件
- 高親和度（7以上）: 15件
- 中親和度（5-7）: 28件

## 🎯 高親和度の題材（7以上）
### 1. タイトル... ⭐9.5/10
  ...詳細...
```

---

## 🔄 フロー図

```
【毎日午前9時00分】
  ↓
daily_business_themes_pipeline.py
  ├─ bookmarks.json を読み込み
  ├─ extract_business_themes.py で処理
  └─ themes_YYYYMMDD.md を生成
  ↓
【毎日午前9時30分】
  ↓
integrated_daily_pipeline.py
  ├─ bookmarks.json を読み込み
  ├─ auto_fetch_business_articles.py で自動取得
  │  ├─ Slack x-bookmarks から取得
  │  ├─ Web検索で取得
  │  └─ ニュースサイトから取得
  ├─ 両方をマージ（重複除去）
  ├─ extract_business_themes.py で処理
  └─ themes_YYYYMMDD_integrated.md を生成
  ↓
【完成】
  ✅ 手動＋自動の統合テーマリスト
```

---

## 🛠 トラブルシューティング

| 問題 | 原因 | 対処法 |
|------|------|------|
| 統合パイプラインが実行されない | スクリプトが見つからない | ファイルパスを確認（上記参照） |
| 自動取得記事が0件 | Web検索機能が未統合 | `auto_fetch_business_articles.py` で実装待ち |
| テーマリストが生成されない | extract_business_themes.py が失敗 | ログ確認：`integrated_pipeline_logs.txt` |
| 重複記事が多い | ソース間で同じ記事が含まれている | デデュプロセスは自動実行中 |
| Slack取得が失敗 | Slack MCP未設定 | `~/.claude/.mcp.json` を確認 |

---

## 📅 定期実行スケジュール

| 実行時刻 | パイプライン | 用途 | 出力 |
|---------|-------------|------|------|
| 毎日9:00 | `daily_business_themes_pipeline.py` | 手動ブックマーク処理 | `themes_YYYYMMDD.md` |
| 毎日9:30 | `integrated_daily_pipeline.py` | 統合処理（新規） | `themes_YYYYMMDD_integrated.md` |

**時間差を設ける理由:**
- 重複処理を避ける
- それぞれ異なるソース構成
- ユーザーが柔軟にテーマ選択可能

---

## 🚀 実運用のポイント

### ✅ する
- ✓ 毎日テーマリストを確認（午前10時以降）
- ✓ 高親和度テーマを優先的にnote化
- ✓ 月1回ログをアーカイブ
- ✓ 定期的にキーワードを更新

### ❌ しない
- ✗ 手動でパイプラインを頻繁に実行
- ✗ テーマリストを削除（3ヶ月分は保持推奨）
- ✗ ブックマークと自動取得を二重計上

---

## 📝 カスタマイズ例

### ビジネスキーワードを追加

```bash
python auto_fetch_business_articles.py \
  --keywords "スタートアップ,営業戦略,カスタマーサクセス"
```

### 手動ブックマークのみ処理

```bash
python integrated_daily_pipeline.py --skip-auto
```

### 自動取得のみ処理

```bash
python integrated_daily_pipeline.py --skip-manual
```

---

## 📞 サポート情報

- **ログファイル**: `C:\Users\yuki0\x-bookmark-digest\integrated_pipeline_logs.txt`
- **テーマリスト**: `C:\Users\yuki0\WillForward\PersonalizeData\naruse\note_themes\`
- **マージデータ**: `C:\Users\yuki0\x-bookmark-digest\merged_sources_today.json`

---

## 🔮 今後の拡張予定

- [ ] Notion DBへの自動蓄積
- [ ] Claude APIを使った自動note記事生成
- [ ] Slack通知（新規高親和度テーマ検出時）
- [ ] テーマ分析レポート（月次）
- [ ] Twitter API v2統合（リアルタイム取得）
- [ ] Google News API統合

---

*最終更新: 2026年3月2日*
*統合パイプルv1.0*
