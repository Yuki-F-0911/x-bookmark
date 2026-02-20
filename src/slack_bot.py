"""
Slack Bot 応答モジュール
========================
Slackからメンション/質問を受け取り、
その日のダイジェストデータをコンテキストにClaudeが回答する。

GitHub Actions から呼び出される:
  python -m src.slack_bot --question "今日のAI系まとめて" --channel "C12345678" --thread "1234567890.123456"
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

import requests
from anthropic import Anthropic
from dotenv import load_dotenv

from .utils import get_logger

logger = get_logger(__name__)
JST = timezone(timedelta(hours=9))

# ダイジェストデータを保存するファイル（daily-digestワークフローが生成）
DIGEST_CACHE_FILE = os.environ.get("DIGEST_CACHE_FILE", "digest_cache.json")


def load_env() -> dict[str, str]:
    env_file = Path(".env")
    if env_file.exists():
        load_dotenv(env_file)
    keys = ["ANTHROPIC_API_KEY", "SLACK_BOT_TOKEN"]
    env = {}
    missing = []
    for key in keys:
        val = os.environ.get(key, "").strip()
        if not val:
            missing.append(key)
        else:
            env[key] = val
    if missing:
        raise EnvironmentError(f"環境変数が未設定: {', '.join(missing)}")
    return env


def load_digest_cache() -> dict | None:
    """最新のダイジェストキャッシュを読み込む"""
    path = Path(DIGEST_CACHE_FILE)
    if not path.exists():
        logger.warning(f"ダイジェストキャッシュが見つかりません: {path}")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"ダイジェストキャッシュの読み込み失敗: {e}")
        return None


def build_context_text(cache: dict) -> str:
    """ダイジェストキャッシュからClaudeへのコンテキスト文字列を生成"""
    lines = [
        f"=== X Bookmark Digest ({cache.get('date', '不明')}) ===",
        f"合計 {cache.get('total_count', 0)} 件のブックマークを処理しました。",
        "",
    ]
    for bm in cache.get("bookmarks", []):
        importance = bm.get("importance", "normal")
        category   = bm.get("category", "その他")
        summary    = bm.get("summary", "")
        author     = bm.get("author_username", "")
        url        = bm.get("url", "")
        likes      = bm.get("like_count", 0)
        keywords   = ", ".join(bm.get("keywords", []))
        enrichment = bm.get("enrichment_summary", "")

        lines.append(f"[{importance.upper()}][{category}] @{author} (👍{likes})")
        lines.append(f"  要約: {summary}")
        if keywords:
            lines.append(f"  キーワード: {keywords}")
        if enrichment:
            lines.append(f"  補足: {enrichment}")
        lines.append(f"  URL: {url}")
        lines.append("")

    return "\n".join(lines)


def ask_claude(client: Anthropic, question: str, context: str) -> str:
    """Claudeにダイジェストコンテキストを渡して質問に答えてもらう"""
    system_prompt = (
        "あなたはX（Twitter）ブックマークダイジェストアシスタントです。\n"
        "ユーザーがブックマークしたツイートの要約データが提供されます。\n"
        "日本語で簡潔に、かつ具体的に回答してください。\n"
        "回答はSlackのmrkdwn形式（*太字*, _斜体_, • リストなど）で書いてください。\n"
        "データにない情報については「ダイジェストには含まれていません」と正直に答えてください。"
    )
    user_message = (
        f"以下は本日のブックマークダイジェストです:\n\n"
        f"{context}\n\n"
        f"---\n"
        f"質問: {question}"
    )
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def post_slack_reply(token: str, channel: str, thread_ts: str, text: str) -> bool:
    """Slackのスレッドに返信する"""
    payload = {
        "channel": channel,
        "thread_ts": thread_ts,
        "text": text,
    }
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    data = resp.json()
    if not data.get("ok"):
        logger.error(f"Slack返信失敗: {data.get('error')}")
        return False
    logger.info("Slackへの返信が完了しました")
    return True


def run_bot(question: str, channel: str, thread_ts: str) -> None:
    env = load_env()
    client = Anthropic(api_key=env["ANTHROPIC_API_KEY"])

    # ダイジェストキャッシュを読み込む
    cache = load_digest_cache()
    if cache is None:
        reply = (
            ":warning: 本日のダイジェストデータが見つかりません。\n"
            "まず `bookmarks.json` をpushしてダイジェストを生成してください。"
        )
    else:
        logger.info(f"質問: {question}")
        context = build_context_text(cache)
        reply = ask_claude(client, question, context)
        logger.info(f"Claudeの回答: {reply[:100]}...")

    post_slack_reply(env["SLACK_BOT_TOKEN"], channel, thread_ts, reply)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Slack Bot: ダイジスト質問応答")
    parser.add_argument("--question",  required=True, help="Slackからの質問テキスト")
    parser.add_argument("--channel",   required=True, help="Slack チャンネルID")
    parser.add_argument("--thread",    required=True, help="Slack スレッドts（返信先）")
    args = parser.parse_args()

    try:
        run_bot(
            question=args.question,
            channel=args.channel,
            thread_ts=args.thread,
        )
    except Exception as e:
        logger.error(f"Bot実行エラー: {e}", exc_info=True)
        sys.exit(1)
