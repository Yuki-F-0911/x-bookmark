# test_generate_article.py
"""Unit tests for generate_article module."""
import unittest
from generate_article import generate_article

class TestGenerateArticle(unittest.TestCase):
    def test_empty_data(self):
        data = {"tweets": [], "scholar": [], "news": []}
        article = generate_article(data)
        self.assertIn("# Athletics Knowledge Digest", article)
        self.assertIn("## 最近のツイート", article)
        self.assertIn("## 関連論文", article)
        self.assertIn("## ニュース記事", article)

    def test_with_data(self):
        data = {
            "tweets": [{"text": "Sample tweet"}],
            "scholar": [{"title": "Sample paper", "url": "http://example.com"}],
            "news": [{"title": "Sample news", "url": "http://news.com"}]
        }
        article = generate_article(data)
        self.assertIn("Sample tweet", article)
        self.assertIn("[Sample paper]", article)
        self.assertIn("[Sample news]", article)

if __name__ == "__main__":
    unittest.main()
