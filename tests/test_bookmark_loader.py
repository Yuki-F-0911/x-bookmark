"""
bookmark_loader モジュールのユニットテスト
"""

import json
import os
import tempfile
import pytest
from src.bookmark_loader import (
    load_bookmarks,
    load_processed_ids,
    save_processed_ids,
    filter_new_bookmarks,
)
from src.models import Bookmark


def write_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


class TestLoadBookmarks:
    def test_load_standard_format(self, tmp_path):
        """X Bookmarks Exporter 標準形式の読み込みテスト"""
        sample = [
            {
                "id": "111",
                "text": "テストツイート1",
                "user": {"name": "テストユーザー", "screen_name": "testuser"},
                "created_at": "2026-02-19T03:00:00.000Z",
                "url": "https://x.com/testuser/status/111",
                "public_metrics": {"like_count": 100},
            }
        ]
        filepath = str(tmp_path / "bookmarks.json")
        write_json(sample, filepath)

        bookmarks = load_bookmarks(filepath)
        assert len(bookmarks) == 1
        assert bookmarks[0].id == "111"
        assert bookmarks[0].text == "テストツイート1"
        assert bookmarks[0].author_username == "testuser"

    def test_deduplication(self, tmp_path):
        """重複IDが除去されることを確認"""
        sample = [
            {"id": "111", "text": "A", "user": {"name": "U", "screen_name": "u"}},
            {"id": "111", "text": "B", "user": {"name": "U", "screen_name": "u"}},
        ]
        filepath = str(tmp_path / "bookmarks.json")
        write_json(sample, filepath)

        bookmarks = load_bookmarks(filepath)
        assert len(bookmarks) == 1
        assert bookmarks[0].text == "A"  # 最初のものが残る

    def test_file_not_found(self):
        """存在しないファイルで FileNotFoundError が発生することを確認"""
        with pytest.raises(FileNotFoundError):
            load_bookmarks("/nonexistent/bookmarks.json")


class TestProcessedIds:
    def test_save_and_load(self, tmp_path):
        """処理済みIDの保存・読み込みテスト"""
        filepath = str(tmp_path / "processed_ids.json")
        ids = {"111", "222", "333"}

        save_processed_ids(ids, filepath)
        loaded = load_processed_ids(filepath)

        assert ids == loaded

    def test_load_nonexistent(self, tmp_path):
        """存在しないファイルで空セットが返ることを確認"""
        filepath = str(tmp_path / "nonexistent.json")
        result = load_processed_ids(filepath)
        assert result == set()


class TestFilterNewBookmarks:
    def test_filter_processed(self):
        """処理済みIDが除外されることを確認"""
        bms = [
            Bookmark(id="1", text="A", author_name="U", author_username="u", url=""),
            Bookmark(id="2", text="B", author_name="U", author_username="u", url=""),
            Bookmark(id="3", text="C", author_name="U", author_username="u", url=""),
        ]
        processed = {"1", "3"}
        result = filter_new_bookmarks(bms, processed)
        assert len(result) == 1
        assert result[0].id == "2"

    def test_all_new(self):
        """処理済みIDがない場合は全件返す"""
        bms = [
            Bookmark(id="1", text="A", author_name="U", author_username="u", url=""),
        ]
        result = filter_new_bookmarks(bms, set())
        assert len(result) == 1
