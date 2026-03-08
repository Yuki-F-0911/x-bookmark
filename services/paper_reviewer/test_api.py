# test_api.py
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from api import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch('api.fetch_papers')
    def test_search_papers(self, mock_fetch):
        mock_fetch.return_value = [{"title": "Test Paper", "abstract": "Test Abstract"}]
        response = self.client.get("/search", params={"query": "test"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["title"], "Test Paper")

    @patch('api.generate_review')
    @patch('api.save_to_zotero')
    def test_review_paper(self, mock_zotero, mock_review):
        mock_review.return_value = "# Mock Review Content"
        mock_zotero.return_value = {"status": "success", "zotero_item_id": "MOCK_123"}
        
        payload = {
            "paper": {"title": "Test Paper", "abstract": "Test Abstract"},
            "save_to_zotero": True
        }
        response = self.client.post("/review", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("review", data)
        self.assertEqual(data["review"], "# Mock Review Content")
        self.assertIn("zotero_sync", data)
        self.assertEqual(data["zotero_sync"]["status"], "success")

if __name__ == '__main__':
    unittest.main()
