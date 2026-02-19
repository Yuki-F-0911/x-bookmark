"""
Slack Incoming Webhook に Block Kit 形式でメッセージを送信するモジュール。
"""

import requests
from collections import defaultdict
from datetime import datetime
from .models import EnrichedBookmark, WebResult, DigestResult
from .utils import get_logger

logger = get_logger(__name__)

SLACK_TIMEOUT = 10  # 秒
MAX_BLOCKS_PER_MESSAGE = 50  # Slack Block Kit の上限

# カテゴリ別絵文字マップ
CATEGORY_EMOJI: dict[str, str] = {
    "AI・テック": "🤖",
    "ビジネス・経営": "💼",
    "マーケティング": "📣",
    "スポーツ・健康": "🏃",
    "学習・教育": "📖",
    "ニュース・社会": "📰",
    "エンタメ・カルチャー": "🎭",
    "その他": "📌",
}


def _emoji(category: str) -> str:
    return CATEGORY_EMOJI.get(category, "📌")


def _truncate(text: str, max_len: int = 200) -> str:
    """テキストを指定文字数に切り詰める"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _build_bookmark_block(bm: EnrichedBookmark) -> dict:
    """
    1件のブックマークを Slack Section ブロックに変換する。

    形式:
    *<URL|@username>* (👍 123)
    要約テキスト
    > _補足情報_
    🔗 関連: [タイトル](url)
    """
    # ヘッダー行: リンク + いいね数
    like_str = ""
    if bm.bookmark.like_count > 0:
        like_str = f" 👍 {bm.bookmark.like_count:,}"

    header = f"*<{bm.bookmark.url}|@{bm.bookmark.author_username}>*{like_str}"

    # 要約本文
    summary = _truncate(bm.summary, 300)

    # 補足情報（blockquote形式）
    enrichment = ""
    if bm.enrichment_summary:
        enrichment = f"\n> _{_truncate(bm.enrichment_summary, 200)}_"

    # 関連Webリンク（最大2件）
    web_links = ""
    if bm.web_results:
        links = []
        for wr in bm.web_results[:2]:
            if wr.url and wr.title:
                links.append(f"<{wr.url}|{_truncate(wr.title, 50)}>")
        if links:
            web_links = "\n🔗 関連: " + " / ".join(links)

    text = f"{header}\n{summary}{enrichment}{web_links}"

    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": text[:3000],  # Slack の text 上限: 3000文字
        },
    }


def _build_category_blocks(
    category: str,
    bookmarks: list[EnrichedBookmark],
) -> list[dict]:
    """カテゴリのヘッダー + ブックマーク一覧のブロックを生成する"""
    emoji = _emoji(category)
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {category}（{len(bookmarks)}件）",
                "emoji": True,
            },
        }
    ]
    for bm in bookmarks:
        blocks.append(_build_bookmark_block(bm))
    blocks.append({"type": "divider"})
    return blocks


def build_digest_blocks(result: DigestResult) -> list[dict]:
    """
    DigestResult 全体を Block Kit ブロックのリストに変換する。

    構造:
      - ヘッダー（日付・件数）
      - divider
      - カテゴリ別セクション（件数順）
      - フッター
    """
    # 日付文字列（ゼロ埋めなし）
    dt = result.date
    date_str = f"{dt.year}年{dt.month}月{dt.day}日"

    total_tokens = (
        result.token_usage.get("input_tokens", 0)
        + result.token_usage.get("output_tokens", 0)
    )

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📚 今日のX Bookmark Digest（{date_str}）",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"*合計 {result.total_count} 件* ｜ "
                        f"モデル: {result.model_used} ｜ "
                        f"トークン: {total_tokens:,}"
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]

    # カテゴリ別にグループ化して件数順にソート
    by_category: defaultdict[str, list[EnrichedBookmark]] = defaultdict(list)
    for bm in result.bookmarks:
        by_category[bm.category].append(bm)

    sorted_categories = sorted(
        by_category.items(),
        key=lambda x: len(x[1]),
        reverse=True,
    )

    for category, bms in sorted_categories:
        blocks.extend(_build_category_blocks(category, bms))

    # フッター
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": "_X Bookmark Digest ｜ Powered by Claude & DuckDuckGo_",
            }
        ],
    })

    return blocks


def _send_payload(webhook_url: str, payload: dict) -> None:
    """Slack Incoming Webhook にペイロードを送信する"""
    response = requests.post(
        webhook_url,
        json=payload,
        timeout=SLACK_TIMEOUT,
    )
    response.raise_for_status()


def send_to_slack(webhook_url: str, result: DigestResult) -> bool:
    """
    Slack にダイジェストを送信する。
    50ブロックを超える場合は分割送信する。

    Args:
        webhook_url: Slack Incoming Webhook URL
        result: DigestResult

    Returns:
        bool: 送信成功なら True

    Raises:
        requests.HTTPError: Slack API エラー
    """
    blocks = build_digest_blocks(result)
    fallback_text = (
        f"X Bookmark Digest {result.date.year}/{result.date.month}/{result.date.day} "
        f"（{result.total_count}件）"
    )

    if len(blocks) <= MAX_BLOCKS_PER_MESSAGE:
        _send_payload(webhook_url, {
            "blocks": blocks,
            "text": fallback_text,
        })
    else:
        # 分割送信
        logger.info(f"ブロック数 {len(blocks)} が上限を超えるため分割送信します")
        chunk_size = MAX_BLOCKS_PER_MESSAGE - 2  # 余裕をもたせる
        chunks = [blocks[i:i + chunk_size] for i in range(0, len(blocks), chunk_size)]
        for idx, chunk in enumerate(chunks):
            part_text = fallback_text + (f"（{idx + 1}/{len(chunks)}）" if len(chunks) > 1 else "")
            _send_payload(webhook_url, {
                "blocks": chunk,
                "text": part_text,
            })

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
