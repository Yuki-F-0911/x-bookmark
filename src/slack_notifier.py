"""
Slack Incoming Webhook に Block Kit 形式でメッセージを送信するモジュール。

表示方針:
  - high importance  → 先頭にまとめて表示。要約 + Web補足 + リンク
  - normal importance → カテゴリ別にコンパクト表示
  - low importance   → 末尾に件数のみ（リンク一覧）
"""

import requests
from collections import defaultdict
from datetime import datetime
from .models import EnrichedBookmark, WebResult, DigestResult
from .utils import get_logger

logger = get_logger(__name__)

SLACK_TIMEOUT = 10
MAX_BLOCKS_PER_MESSAGE = 50

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
IMPORTANCE_LABEL = {"high": "🔴", "normal": "🔵", "low": "⚫"}


def _emoji(category: str) -> str:
    return CATEGORY_EMOJI.get(category, "📌")


def _truncate(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _build_high_block(bm: EnrichedBookmark) -> dict:
    """high importance 用の詳細ブロック"""
    like_str = f"  👍 {bm.bookmark.like_count:,}" if bm.bookmark.like_count > 0 else ""
    cat = f"{_emoji(bm.category)} {bm.category}"
    header = f"🔴 *<{bm.bookmark.url}|@{bm.bookmark.author_username}>*{like_str}  _{cat}_"
    summary = _truncate(bm.summary, 250)
    enrichment = f"\n> _{_truncate(bm.enrichment_summary, 180)}_" if bm.enrichment_summary else ""
    web_links = ""
    if bm.web_results:
        links = [f"<{r.url}|{_truncate(r.title, 40)}>" for r in bm.web_results[:2] if r.url and r.title]
        if links:
            web_links = "\n🔗 " + "  /  ".join(links)
    text = f"{header}\n{summary}{enrichment}{web_links}"
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}}


def _build_normal_block(bm: EnrichedBookmark) -> str:
    """normal importance 用の1行テキスト（複数件をまとめてsectionに入れる）"""
    like_str = f" 👍{bm.bookmark.like_count:,}" if bm.bookmark.like_count > 0 else ""
    summary = _truncate(bm.summary, 120)
    return f"• <{bm.bookmark.url}|@{bm.bookmark.author_username}>{like_str} — {summary}"


def build_digest_blocks(result: DigestResult) -> list[dict]:
    """
    DigestResult を Block Kit ブロックに変換する。

    構造:
      [ヘッダー]
      [🔴 重要 セクション] × high件数
      [カテゴリ別 normal セクション]
      [⚫ 内容薄 まとめ行]
      [フッター]
    """
    dt = result.date
    date_str = f"{dt.year}年{dt.month}月{dt.day}日"

    # 重要度で分類
    high_bms = [bm for bm in result.bookmarks if bm.importance == "high"]
    normal_bms = [bm for bm in result.bookmarks if bm.importance == "normal"]
    low_bms = [bm for bm in result.bookmarks if bm.importance == "low"]

    # サブヘッダー用のカウント文字列
    counts = []
    if high_bms:
        counts.append(f"🔴 重要 {len(high_bms)}件")
    if normal_bms:
        counts.append(f"🔵 通常 {len(normal_bms)}件")
    if low_bms:
        counts.append(f"⚫ 薄め {len(low_bms)}件")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📚 X Bookmark Digest｜{date_str}", "emoji": True},
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "  ".join(counts) + f"　計 {result.total_count}件"}],
        },
        {"type": "divider"},
    ]

    # ── 🔴 重要 ──
    if high_bms:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*🔴 重要ピックアップ*"},
        })
        for bm in high_bms:
            blocks.append(_build_high_block(bm))
        blocks.append({"type": "divider"})

    # ── 🔵 通常（カテゴリ別） ──
    if normal_bms:
        by_cat: defaultdict[str, list[EnrichedBookmark]] = defaultdict(list)
        for bm in normal_bms:
            by_cat[bm.category].append(bm)

        # カテゴリを件数順にソート
        sorted_cats = sorted(by_cat.items(), key=lambda x: len(x[1]), reverse=True)

        for category, bms in sorted_cats:
            # カテゴリ内でいいね数が多い順にソート
            bms_sorted = sorted(bms, key=lambda b: b.bookmark.like_count, reverse=True)
            lines = [_build_normal_block(bm) for bm in bms_sorted]
            cat_text = f"*{_emoji(category)} {category}*\n" + "\n".join(lines)
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": cat_text[:3000]}})

        blocks.append({"type": "divider"})

    # ── ⚫ 内容薄 ──
    if low_bms:
        links = [f"<{bm.bookmark.url}|@{bm.bookmark.author_username}>" for bm in low_bms]
        low_text = f"*⚫ 内容薄・本文なし（{len(low_bms)}件）*\n" + "  ".join(links)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": low_text[:3000]}})
        blocks.append({"type": "divider"})

    # フッター
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "_X Bookmark Digest ｜ Powered by Claude_"}],
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
