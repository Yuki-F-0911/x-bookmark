"""
Slack Incoming Webhook にブックマーク一覧を送信するモジュール。
"""

import requests
from datetime import datetime
from .models import Bookmark
from .utils import get_logger

logger = get_logger(__name__)

SLACK_TIMEOUT = 10
MAX_BLOCKS_PER_MESSAGE = 50


def _truncate(text: str, max_len: int = 150) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _build_bookmark_line(bm: Bookmark) -> str:
    """ブックマーク1件分のテキスト行"""
    like_str = f" 👍{bm.like_count:,}" if bm.like_count > 0 else ""
    text_preview = _truncate(bm.text, 120) if bm.text else "(本文なし)"
    return f"• <{bm.url}|@{bm.author_username}>{like_str} — {text_preview}"


def build_blocks(bookmarks: list[Bookmark], date: datetime) -> list[dict]:
    """ブックマーク一覧を Block Kit ブロックに変換する"""
    date_str = f"{date.year}年{date.month}月{date.day}日"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📚 X Bookmarks｜{date_str}",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"{len(bookmarks)}件の新規ブックマーク"}
            ],
        },
        {"type": "divider"},
    ]

    # いいね数の多い順にソート
    sorted_bms = sorted(bookmarks, key=lambda b: b.like_count, reverse=True)

    # 5件ずつまとめて1セクションにする（Block Kit制限対策）
    chunk_size = 5
    for i in range(0, len(sorted_bms), chunk_size):
        chunk = sorted_bms[i:i + chunk_size]
        lines = [_build_bookmark_line(bm) for bm in chunk]
        text = "\n".join(lines)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": text[:3000]},
        })

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "_X Bookmark Digest_"}],
    })

    return blocks


def _send_payload(webhook_url: str, payload: dict) -> None:
    """Slack Incoming Webhook にペイロードを送信する"""
    response = requests.post(webhook_url, json=payload, timeout=SLACK_TIMEOUT)
    response.raise_for_status()


def send_to_slack(webhook_url: str, bookmarks: list[Bookmark], date: datetime) -> bool:
    """
    Slack にブックマーク一覧を送信する。

    Returns:
        bool: 送信成功なら True
    """
    blocks = build_blocks(bookmarks, date)
    fallback_text = f"X Bookmarks {date.year}/{date.month}/{date.day}（{len(bookmarks)}件）"

    if len(blocks) <= MAX_BLOCKS_PER_MESSAGE:
        _send_payload(webhook_url, {"blocks": blocks, "text": fallback_text})
    else:
        logger.info(f"ブロック数 {len(blocks)} が上限を超えるため分割送信します")
        chunk_size = MAX_BLOCKS_PER_MESSAGE - 2
        chunks = [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
        for idx, chunk in enumerate(chunks):
            part_text = fallback_text + (f"（{idx + 1}/{len(chunks)}）" if len(chunks) > 1 else "")
            _send_payload(webhook_url, {"blocks": chunk, "text": part_text})

    logger.info("Slack への送信が完了しました")
    return True


def send_error_to_slack(webhook_url: str, error_message: str) -> None:
    """エラー通知を Slack に送信する"""
    payload = {
        "text": f":red_circle: *X Bookmark Digest エラー*\n```{error_message}```",
    }
    try:
        _send_payload(webhook_url, payload)
    except Exception as e:
        logger.error(f"Slack エラー通知の送信に失敗: {e}")
