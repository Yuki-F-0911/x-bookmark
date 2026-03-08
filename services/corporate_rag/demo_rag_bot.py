#!/usr/bin/env python3
"""
社内RAGデモ用 Slack Botスクリプト

指定したNotionページ群を知識ベースとして、
Slackで質問されると文書に基づいた回答を返すデモBot。

使い方:
  # 環境変数設定
  export ANTHROPIC_API_KEY=sk-...
  export SLACK_BOT_TOKEN=xoxb-...
  export SLACK_APP_TOKEN=xapp-...

  # 起動
  python demo_rag_bot.py

  # デモ用: CLIモードで質問テスト
  python demo_rag_bot.py --cli
"""

import os
import sys
import io
import json
import argparse
from pathlib import Path
from datetime import datetime

from anthropic import Anthropic
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

# デモ用のサンプル社内文書
SAMPLE_KNOWLEDGE_BASE = """
## 社内規程

### 勤怠管理規程
- 始業時間: 9:00、終業時間: 18:00（フレックス制度あり、コアタイム10:00-15:00）
- 有給休暇: 入社6ヶ月後に10日付与。以降年1日加算、最大20日
- 残業申請: 事前に上長承認が必要。月45時間を超える場合は人事部への届出必須
- リモートワーク: 週3日まで可能。事前にSlackの#attendanceチャンネルに申告

### 経費精算規程
- 交通費: 実費精算（月末締め、翌月15日振込）
- 出張手当: 日帰り3,000円、宿泊8,000円
- 接待費: 1人5,000円まで（事前承認不要）。5,000円超は部長承認必要
- 経費申請期限: 発生月の翌月10日まで

### 情報セキュリティポリシー
- パスワード: 12文字以上、大文字小文字数字記号を含む。90日ごとに変更
- 個人端末: 業務利用禁止（BYOD不可）
- 外部ストレージ: USBメモリの使用禁止。クラウドストレージはGoogle Workspaceのみ
- 機密情報: 社外メールへの添付はDLP（情報漏洩防止）システムで自動チェック

### 採用プロセス
1. 書類選考（人事部、3営業日以内）
2. 一次面接（部門マネージャー、オンライン30分）
3. 二次面接（部長+人事部長、対面60分）
4. 最終面接（取締役、対面30分）
5. オファー面談（人事部、条件提示+質疑）

### 開発環境セットアップ
1. IT部門にSlackで#it-supportチャンネルでMac/Windowsの希望を伝える
2. 1Passwordチームに招待される → 各種サービスの認証情報を取得
3. GitHubのOrganizationに招待される → リポジトリにアクセス
4. 開発用AWSアカウントのIAMロールが発行される
5. VPN設定: GlobalProtectをインストール、設定ファイルはIT部門から配布
"""

RAG_SYSTEM_PROMPT = """あなたは社内アシスタントです。以下の社内文書のみに基づいて質問に回答してください。

## 重要なルール
1. 社内文書に記載されている情報のみで回答する
2. 文書に該当する情報がない場合は「申し訳ございませんが、その情報は社内文書に見つかりませんでした。担当部門にお問い合わせください。」と回答する
3. 推測や一般的な知識で補完しない
4. 回答の最後に「📄 参照: {該当セクション名}」を付記する
5. 簡潔かつ丁寧に回答する

## 社内文書
{knowledge_base}
"""


def answer_question(client: Anthropic, question: str, knowledge_base: str) -> str:
    """社内文書に基づいて質問に回答"""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=500,
        system=RAG_SYSTEM_PROMPT.format(knowledge_base=knowledge_base),
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text.strip()


def run_cli_demo():
    """CLIモードでデモを実行"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY を設定してください", file=sys.stderr)
        sys.exit(1)

    client = Anthropic(api_key=api_key)

    print("=" * 50)
    print("🤖 社内ブレイン デモ")
    print("社内規程について質問してください（'q'で終了）")
    print("=" * 50)

    demo_questions = [
        "リモートワークは週何日まで可能ですか？",
        "経費精算の申請期限はいつまでですか？",
        "採用プロセスは何段階ですか？",
        "パスワードの要件を教えてください",
        "新入社員の開発環境セットアップの手順は？",
    ]

    print("\n💡 デモ質問例:")
    for i, q in enumerate(demo_questions, 1):
        print(f"  {i}. {q}")
    print()

    while True:
        try:
            question = input("質問> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if question.lower() in ('q', 'quit', 'exit'):
            break

        if not question:
            continue

        # 数字入力の場合はデモ質問を使用
        if question.isdigit() and 1 <= int(question) <= len(demo_questions):
            question = demo_questions[int(question) - 1]
            print(f"  → {question}")

        print("\n🔍 検索中...\n")
        answer = answer_question(client, question, SAMPLE_KNOWLEDGE_BASE)
        print(f"📋 回答:\n{answer}\n")
        print("-" * 40)


def run_slack_bot():
    """Slack Botモードで起動"""
    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError:
        print("[ERROR] slack_bolt がインストールされていません", file=sys.stderr)
        print("  pip install slack-bolt", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
    slack_app_token = os.environ.get("SLACK_APP_TOKEN")

    if not all([api_key, slack_bot_token, slack_app_token]):
        print("[ERROR] 環境変数を設定してください:", file=sys.stderr)
        print("  ANTHROPIC_API_KEY, SLACK_BOT_TOKEN, SLACK_APP_TOKEN", file=sys.stderr)
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    app = App(token=slack_bot_token)

    @app.event("app_mention")
    def handle_mention(event, say):
        question = event.get("text", "").strip()
        # メンション部分を除去
        question = question.split(">", 1)[-1].strip() if ">" in question else question

        if not question:
            say("質問を入力してください。例: `@社内ブレイン リモートワークのルールは？`")
            return

        answer = answer_question(client, question, SAMPLE_KNOWLEDGE_BASE)
        say(answer)

    @app.event("message")
    def handle_dm(event, say):
        if event.get("channel_type") == "im":
            question = event.get("text", "").strip()
            if question:
                answer = answer_question(client, question, SAMPLE_KNOWLEDGE_BASE)
                say(answer)

    print("🤖 社内ブレイン Bot を起動しています...")
    handler = SocketModeHandler(app, slack_app_token)
    handler.start()


def main():
    parser = argparse.ArgumentParser(description="社内RAGデモBot")
    parser.add_argument("--cli", action="store_true", help="CLIモードで起動")
    args = parser.parse_args()

    if args.cli:
        run_cli_demo()
    else:
        run_slack_bot()


if __name__ == "__main__":
    main()
