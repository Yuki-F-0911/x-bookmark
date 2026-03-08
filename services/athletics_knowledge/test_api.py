# test_api.py
"""Unit tests for the FastAPI API endpoint in athletics_knowledge service."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Import the FastAPI app
from api import app

class TestAPI(unittest.TestCase):
    @patch('api.fetch_data')
    @patch('api.generate_article')
    def test_get_article(self, mock_generate_article, mock_fetch_data):
        # Mock the data fetching and article generation
        mock_fetch_data.return_value = {"tweets": [], "scholar": [], "news": []}
        mock_generate_article.return_value = "# Sample Article"
        client = TestClient(app)
        response = client.get("/articles", params={"topic": "marathon"})
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertIn("article", json_data)
        self.assertEqual(json_data["article"], "# Sample Article")

if __name__ == '__main__':
    unittest.main()
