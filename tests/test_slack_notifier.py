"""
slack_notifier モジュールのユニットテスト
"""

from datetime import datetime, timezone, timedelta
from src.slack_notifier import build_digest_blocks, _truncate
from src.models import (
    Bookmark, EnrichedBookmark, WebResult, DigestResult
)

JST = timezone(timedelta(hours=9))


def make_enriched_bookmark(
    tweet_id="111",
    username="testuser",
    text="テストツイート",
    category="AI・テック",
    summary="テスト要約文",
    enrichment_summary="補足情報",
    like_count=100,
) -> EnrichedBookmark:
    bm = Bookmark(
        id=tweet_id,
        text=text,
        author_name="テスト",
        author_username=username,
        url=f"https://x.com/{username}/status/{tweet_id}",
        like_count=like_count,
    )
    return EnrichedBookmark(
        bookmark=bm,
        category=category,
        summary=summary,
        enrichment_summary=enrichment_summary,
        web_results=[
            WebResult(
                title="関連記事",
                url="https://example.com",
                snippet="スニペット",
            )
        ],
    )


def make_digest(bookmarks=None) -> DigestResult:
    if bookmarks is None:
        bookmarks = [make_enriched_bookmark()]
    return DigestResult(
        date=datetime(2026, 2, 19, 7, 0, tzinfo=JST),
        bookmarks=bookmarks,
        total_count=len(bookmarks),
        model_used="claude-sonnet-4-5 / claude-haiku-4-5",
        token_usage={"input_tokens": 1000, "output_tokens": 500},
    )


class TestBuildDigestBlocks:
    def test_returns_list_of_dicts(self):
        result = make_digest()
        blocks = build_digest_blocks(result)
        assert isinstance(blocks, list)
        assert all(isinstance(b, dict) for b in blocks)

    def test_has_header_block(self):
        blocks = build_digest_blocks(make_digest())
        headers = [b for b in blocks if b.get("type") == "header"]
        assert len(headers) >= 1
        # タイトルに日付が含まれることを確認
        first_header_text = headers[0]["text"]["text"]
        assert "2026" in first_header_text
        assert "Digest" in first_header_text

    def test_block_count_within_limit_for_small_input(self):
        """小規模入力（5件）でブロック数が上限50以内に収まることを確認"""
        bms = [make_enriched_bookmark(tweet_id=str(i)) for i in range(5)]
        result = make_digest(bms)
        blocks = build_digest_blocks(result)
        assert len(blocks) <= 50

    def test_includes_category_section(self):
        # normalのブックマークを使ってカテゴリが表示されることを確認
        bm = make_enriched_bookmark(category="AI・テック")
        bm.importance = "normal"
        blocks = build_digest_blocks(make_digest([bm]))
        # 新レイアウト: カテゴリはsectionのmrkdwnテキスト内に含まれる
        all_text = " ".join(
            b.get("text", {}).get("text", "") if isinstance(b.get("text"), dict)
            else str(b.get("text", ""))
            for b in blocks
        )
        assert "AI・テック" in all_text

    def test_high_importance_shown_first(self):
        """high importanceのブックマークが先頭セクションに表示されることを確認"""
        bm = make_enriched_bookmark(category="AI・テック")
        bm.importance = "high"
        blocks = build_digest_blocks(make_digest([bm]))
        # 重要ピックアップセクションが存在するか
        all_text = " ".join(
            b.get("text", {}).get("text", "") if isinstance(b.get("text"), dict)
            else ""
            for b in blocks
        )
        assert "重要ピックアップ" in all_text

    def test_low_importance_shown_as_summary(self):
        """low importanceのブックマークがまとめ行に表示されることを確認"""
        bm = make_enriched_bookmark()
        bm.importance = "low"
        blocks = build_digest_blocks(make_digest([bm]))
        all_text = " ".join(
            b.get("text", {}).get("text", "") if isinstance(b.get("text"), dict)
            else ""
            for b in blocks
        )
        assert "内容薄" in all_text


class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("短いテキスト", 100) == "短いテキスト"

    def test_long_text_truncated(self):
        long_text = "あ" * 300
        result = _truncate(long_text, 200)
        assert len(result) <= 200
        assert result.endswith("…")
