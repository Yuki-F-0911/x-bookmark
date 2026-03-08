# test_review_engine.py
import unittest
from review_engine import generate_review

class TestReviewEngine(unittest.TestCase):
    def test_generate_review(self):
        sample_paper = {
            "title": "A Mock Study on AI",
            "authors": ["Mock Author"],
            "published": "2024-01-01T00:00:00Z",
            "abstract": "This is a short abstract for testing purposes.",
            "url": "http://example.com/mock"
        }
        review = generate_review(sample_paper)
        self.assertIn("# 論文レビュー: A Mock Study on AI", review)
        self.assertIn("Mock Author", review)
        self.assertIn("2024", review)
        # Because abstract is short (<500 chars), grade should be C based on our simple heuristic
        self.assertIn("総合評価: C", review)

if __name__ == '__main__':
    unittest.main()
