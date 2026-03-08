# generate_article.py
"""Generate a premium article from fetched athletics data.

Uses the `fetch_athletics_data.fetch_data` function to obtain raw data and then
formats it into a Markdown article suitable for publishing.
"""
from typing import Dict

def generate_article(data: Dict) -> str:
    """Convert fetched data into a formatted Markdown article.

    Args:
        data: Dictionary with keys `tweets`, `scholar`, and `news`.
    Returns:
        A Markdown string representing the article.
    """
    # Placeholder implementation – replace with actual prompt/template logic.
    article_parts = []
    article_parts.append("# Athletics Knowledge Digest\n")
    article_parts.append("## 最近のツイート\n")
    for tweet in data.get("tweets", []):
        article_parts.append(f"- {tweet.get('text', '')}\n")
    article_parts.append("\n## 関連論文\n")
    for paper in data.get("scholar", []):
        title = paper.get('title', 'No title')
        url = paper.get('url', '')
        article_parts.append(f"- [{title}]({url})\n")
    article_parts.append("\n## ニュース記事\n")
    for news in data.get("news", []):
        title = news.get('title', 'No title')
        link = news.get('url', '')
        article_parts.append(f"- [{title}]({link})\n")
    return "".join(article_parts)

if __name__ == "__main__":
    import json, sys
    if len(sys.argv) != 2:
        print("Usage: python generate_article.py <topic>")
        sys.exit(1)
    from fetch_athletics_data import fetch_data
    topic = sys.argv[1]
    data = fetch_data(topic)
    article = generate_article(data)
    print(article)
