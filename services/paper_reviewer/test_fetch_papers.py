# test_fetch_papers.py
import unittest
from fetch_papers import fetch_papers

class TestFetchPapers(unittest.TestCase):
    def test_fetch_papers_returns_list(self):
        # We perform a real network request here to arXiv API for a simple test
        results = fetch_papers("machine learning", max_results=1)
        self.assertIsInstance(results, list)
        if results:
            self.assertIn("title", results[0])
            self.assertIn("abstract", results[0])
            self.assertIn("authors", results[0])

if __name__ == '__main__':
    unittest.main()
