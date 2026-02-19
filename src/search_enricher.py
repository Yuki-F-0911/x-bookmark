"""
Web検索によるブックマーク補足情報取得モジュール。

X API検索の代替として DuckDuckGo Search（無料・APIキー不要）を使用。
Claude Haiku でキーワード抽出 → DuckDuckGo で関連情報を検索 → 補足説明に活用。
"""

import json
import re
import time
from typing import Optional
from anthropic import Anthropic
from .models import Bookmark, WebResult
from .utils import get_logger, with_retry

logger = get_logger(__name__)

# DuckDuckGo の検索結果を1ブックマークあたり何件取得するか
MAX_WEB_RESULTS = 3
# キーワード抽出数
MAX_KEYWORDS = 3
# 検索間隔（DuckDuckGo へのリクエスト過多を避けるため）
SEARCH_INTERVAL_SEC = 1.5


def extract_keywords(
    anthropic_client: Anthropic,
    bookmark_text: str,
    max_keywords: int = MAX_KEYWORDS,
) -> list[str]:
    """
    Claude Haiku を使ってブックマークのテキストから検索キーワードを抽出する。

    Args:
        anthropic_client: Anthropic クライアント
        bookmark_text: ブックマークのツイート本文
        max_keywords: 抽出するキーワード数

    Returns:
        キーワードのリスト（最大 max_keywords 件）
    """
    prompt = f"""以下のツイートから、Web検索に使う日本語または英語のキーワードを{max_keywords}個抽出してください。
固有名詞・技術用語・サービス名・人名を優先してください。
JSON配列のみで返してください（説明不要）。

例: ["Claude API", "生成AI", "Anthropic"]

ツイート:
{bookmark_text[:500]}

キーワード:"""

    try:
        response = anthropic_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # JSON パース
        try:
            # ```json ... ``` ブロックに包まれている場合の処理
            if "```" in text:
                text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
            keywords = json.loads(text)
            if isinstance(keywords, list):
                return [str(k).strip() for k in keywords[:max_keywords] if k]
        except json.JSONDecodeError:
            pass

        # フォールバック: カンマ区切りで分割
        cleaned = re.sub(r'[\[\]"\'`]', "", text)
        return [k.strip() for k in re.split(r"[,、\n]", cleaned) if k.strip()][:max_keywords]

    except Exception as e:
        logger.warning(f"キーワード抽出に失敗: {e}")
        return []


def search_duckduckgo(
    query: str,
    max_results: int = MAX_WEB_RESULTS,
    region: str = "jp-jp",
) -> list[WebResult]:
    """
    DuckDuckGo でWeb検索を実行する。

    Args:
        query: 検索クエリ
        max_results: 取得件数
        region: 地域設定（jp-jp = 日本語）

    Returns:
        WebResult のリスト
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo-search がインストールされていません: pip install duckduckgo-search")
        return []

    results: list[WebResult] = []
    try:
        with DDGS() as ddgs:
            search_results = ddgs.text(
                query,
                region=region,
                safesearch="moderate",
                max_results=max_results,
            )
            for r in search_results:
                results.append(WebResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                ))
    except Exception as e:
        logger.warning(f"DuckDuckGo 検索エラー (query='{query}'): {e}")

    return results


def search_xcom_via_web(
    keywords: list[str],
    max_results: int = MAX_WEB_RESULTS,
) -> list[WebResult]:
    """
    site:x.com 指定でX上の関連投稿をWeb検索する。
    """
    if not keywords:
        return []
    query = " ".join(keywords[:2]) + " site:x.com"
    return search_duckduckgo(query, max_results=max_results, region="jp-jp")


def enrich_bookmark(
    anthropic_client: Anthropic,
    bookmark: Bookmark,
    use_x_search: bool = True,
) -> tuple[list[str], list[WebResult]]:
    """
    1件のブックマークに対してキーワード抽出 + Web検索を実行する。

    Args:
        anthropic_client: Anthropic クライアント
        bookmark: ブックマーク
        use_x_search: True なら x.com 絞り込み検索も試みる

    Returns:
        (keywords, web_results)
    """
    # キーワード抽出
    keywords = extract_keywords(anthropic_client, bookmark.text)
    if not keywords:
        logger.info(f"キーワード抽出結果なし (id={bookmark.id})")
        return [], []

    logger.info(f"キーワード: {keywords} (id={bookmark.id})")

    # 一般Web検索
    query = " ".join(keywords)
    web_results = search_duckduckgo(query, max_results=MAX_WEB_RESULTS)

    # 結果が少なければ X.com 絞り込みも試みる
    if use_x_search and len(web_results) < 2:
        x_results = search_xcom_via_web(keywords, max_results=2)
        web_results.extend(x_results)
        web_results = web_results[:MAX_WEB_RESULTS]

    time.sleep(SEARCH_INTERVAL_SEC)  # レート制限回避
    return keywords, web_results


def enrich_all_bookmarks(
    anthropic_client: Anthropic,
    bookmarks: list[Bookmark],
) -> dict[str, tuple[list[str], list[WebResult]]]:
    """
    全ブックマークのエンリッチメントを逐次実行する。

    Returns:
        {tweet_id: (keywords, web_results)} の辞書
    """
    results: dict[str, tuple[list[str], list[WebResult]]] = {}
    total = len(bookmarks)

    for i, bookmark in enumerate(bookmarks, 1):
        logger.info(f"エンリッチメント中... ({i}/{total})")
        try:
            keywords, web_results = enrich_bookmark(anthropic_client, bookmark)
            results[bookmark.id] = (keywords, web_results)
        except Exception as e:
            logger.warning(f"エンリッチメント失敗 (id={bookmark.id}): {e}")
            results[bookmark.id] = ([], [])

    return results
