# test_fetch_athletics_data.py
"""Unit tests for fetch_athletics_data module."""
import unittest
from unittest.mock import patch
from fetch_athletics_data import fetch_data

class TestFetchAthleticsData(unittest.TestCase):
    @patch('fetch_athletics_data.fetch_tweets')
    @patch('fetch_athletics_data.fetch_scholar')
    @patch('fetch_athletics_data.fetch_news')
    def test_fetch_data(self, mock_news, mock_scholar, mock_tweets):
        mock_tweets.return_value = [{"text": "sample tweet"}]
        mock_scholar.return_value = [{"title": "sample paper", "url": "http://example.com"}]
        mock_news.return_value = [{"title": "sample news", "url": "http://news.com"}]
        result = fetch_data("marathon")
        self.assertIn('tweets', result)
        self.assertIn('scholar', result)
        self.assertIn('news', result)
        self.assertEqual(len(result['tweets']), 1)
        self.assertEqual(len(result['scholar']), 1)
        self.assertEqual(len(result['news']), 1)

if __name__ == '__main__':
    unittest.main()
