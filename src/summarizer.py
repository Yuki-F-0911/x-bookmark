"""
Claude API を使って要約・カテゴリ分け・補足要約を生成するモジュール。

出力トークン上限を超えないよう、CHUNK_SIZE 件ずつ分割してAPI呼び出しを行う。
"""

import json
import re
from anthropic import Anthropic
from .models import Bookmark, EnrichedBookmark, WebResult
from .utils import get_logger, with_retry

logger = get_logger(__name__)

# 要約生成モデル
SUMMARIZE_MODEL = "claude-sonnet-4-5"
# 補足要約モデル（軽量）
ENRICH_MODEL = "claude-haiku-4-5"

# 1回のAPIコールで処理するブックマーク件数
# 1件あたり出力約30トークン × 20件 = 約600トークン（余裕をもって設定）
CHUNK_SIZE = 20

# カテゴリ定義
DEFAULT_CATEGORIES = [
    "AI・テック",
    "ビジネス・経営",
    "マーケティング",
    "スポーツ・健康",
    "学習・教育",
    "ニュース・社会",
    "エンタメ・カルチャー",
    "その他",
]


@with_retry(max_retries=3, base_delay=5.0)
def _summarize_chunk(
    client: Anthropic,
    bookmarks: list[Bookmark],
    categories_str: str,
) -> tuple[list[dict], object]:
    """
    ブックマークのチャンク（最大 CHUNK_SIZE 件）を1回のAPIコールで要約する。
    """
    tweet_list = "\n\n".join(
        f"[ID:{bm.id}]\n@{bm.author_username} ({bm.author_name})\n{bm.text[:300]}"
        for bm in bookmarks
    )

    prompt = f"""以下のXブックマーク一覧を分析してください。

各ブックマークについて:
1. カテゴリを「{categories_str}」のいずれかに分類
2. 日本語で1〜2文の要約を生成（元の内容を忠実に要約すること）

JSONのみで返してください（前後の説明・マークダウン記号は不要）:
[
  {{
    "id": "ツイートID",
    "category": "カテゴリ名",
    "summary": "要約文"
  }}
]

ブックマーク一覧:
{tweet_list}"""

    response = client.messages.create(
        model=SUMMARIZE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    result_text = response.content[0].text.strip()

    # ```json ... ``` ブロックの除去
    if "```" in result_text:
        result_text = re.sub(r"```(?:json)?", "", result_text).strip().rstrip("`").strip()

    # JSON パース
    try:
        summaries = json.loads(result_text)
    except json.JSONDecodeError as e:
        # フォールバック: リスト部分だけ抽出
        match = re.search(r"\[.*?\]", result_text, re.DOTALL)
        if match:
            try:
                summaries = json.loads(match.group())
            except json.JSONDecodeError:
                # それでも失敗した場合はこのチャンクをデフォルト値で埋める
                logger.warning(f"チャンクのJSONパース失敗。デフォルト値を使用します。")
                summaries = [
                    {"id": bm.id, "category": "その他", "summary": bm.text[:80] + "…"}
                    for bm in bookmarks
                ]
        else:
            logger.warning(f"チャンクのJSONパース失敗。デフォルト値を使用します。")
            summaries = [
                {"id": bm.id, "category": "その他", "summary": bm.text[:80] + "…"}
                for bm in bookmarks
            ]

    return summaries, response.usage


def categorize_and_summarize(
    client: Anthropic,
    bookmarks: list[Bookmark],
    categories: list[str] = DEFAULT_CATEGORIES,
) -> tuple[list[dict], object]:
    """
    全ブックマークを CHUNK_SIZE 件ずつ分割して要約・カテゴリ分けを行う。

    Returns:
        (summaries, usage)
        summaries: [{"id": str, "category": str, "summary": str}, ...]
        usage: 合計トークン使用量（疑似オブジェクト）
    """
    categories_str = "・".join(categories)
    all_summaries: list[dict] = []
    total_input = 0
    total_output = 0

    # CHUNK_SIZE 件ずつ分割
    chunks = [bookmarks[i:i + CHUNK_SIZE] for i in range(0, len(bookmarks), CHUNK_SIZE)]
    logger.info(f"要約を {len(chunks)} チャンクに分割して処理します（{CHUNK_SIZE}件/チャンク）")

    for idx, chunk in enumerate(chunks, 1):
        logger.info(f"  チャンク {idx}/{len(chunks)} ({len(chunk)}件) を処理中...")
        summaries, usage = _summarize_chunk(client, chunk, categories_str)
        all_summaries.extend(summaries)
        total_input += usage.input_tokens
        total_output += usage.output_tokens

    logger.info(
        f"要約生成完了: {len(all_summaries)} 件 | "
        f"トークン合計: input={total_input}, output={total_output}"
    )

    # usage の合計を疑似オブジェクトで返す
    class _Usage:
        input_tokens = total_input
        output_tokens = total_output

    return all_summaries, _Usage()


@with_retry(max_retries=2, base_delay=3.0)
def summarize_enrichment(
    client: Anthropic,
    bookmark: Bookmark,
    web_results: list[WebResult],
) -> str:
    """
    Web検索結果から補足情報を1〜2文で生成する。

    Args:
        client: Anthropic クライアント
        bookmark: 元のブックマーク
        web_results: Web検索結果のリスト

    Returns:
        補足要約文字列（空の場合もある）
    """
    if not web_results:
        return ""

    # Web検索結果をテキスト化（各結果のタイトル + スニペット）
    results_text = "\n".join(
        f"- 【{r.title}】{r.snippet[:150]}"
        for r in web_results
        if r.title or r.snippet
    )

    if not results_text.strip():
        return ""

    prompt = f"""元のツイート:
{bookmark.text[:300]}

関連するWeb検索結果:
{results_text}

Web検索結果から読み取れる補足情報・背景・最新動向を、日本語で1〜2文にまとめてください。
「補足:」などのプレフィックスは不要です。情報がない場合は「（補足情報なし）」と返してください。"""

    response = client.messages.create(
        model=ENRICH_MODEL,
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    result = response.content[0].text.strip()
    if result == "（補足情報なし）":
        return ""
    return result


def build_enriched_bookmarks(
    client: Anthropic,
    bookmarks: list[Bookmark],
    enrichment_data: dict[str, tuple[list[str], list[WebResult]]],
) -> tuple[list[EnrichedBookmark], dict]:
    """
    要約 + エンリッチメントデータを統合して EnrichedBookmark リストを生成する。

    Args:
        client: Anthropic クライアント
        bookmarks: ブックマークのリスト
        enrichment_data: {tweet_id: (keywords, web_results)} の辞書

    Returns:
        (enriched_bookmarks, token_usage)
        token_usage: {"input_tokens": int, "output_tokens": int}
    """
    # バッチ要約生成
    logger.info(f"バッチ要約生成を開始: {len(bookmarks)} 件")
    summaries_raw, usage = categorize_and_summarize(client, bookmarks)

    # ID → 要約データのマップ
    summary_map: dict[str, dict] = {s["id"]: s for s in summaries_raw}

    enriched: list[EnrichedBookmark] = []
    for bookmark in bookmarks:
        summary_data = summary_map.get(bookmark.id, {})
        keywords, web_results = enrichment_data.get(bookmark.id, ([], []))

        # 補足要約生成（Web結果があれば）
        enrichment_summary = ""
        if web_results:
            try:
                enrichment_summary = summarize_enrichment(client, bookmark, web_results)
            except Exception as e:
                logger.warning(f"補足要約生成失敗 (id={bookmark.id}): {e}")

        enriched.append(EnrichedBookmark(
            bookmark=bookmark,
            category=summary_data.get("category", "その他"),
            summary=summary_data.get("summary", bookmark.text[:100] + "…"),
            keywords=keywords,
            web_results=web_results,
            enrichment_summary=enrichment_summary,
        ))

    token_usage = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }
    return enriched, token_usage
