# fetch_papers.py
"""Fetch academic papers using the arXiv API.

Provides a function `fetch_papers(query: str, max_results: int = 5) -> list[dict]`
that returns a list of dictionaries containing paper metadata (title, summary, authors,
published date, and link).
"""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict

def fetch_papers(query: str, max_results: int = 5) -> List[Dict]:
    """Fetch academic papers from arXiv based on a search query.

    Args:
        query: The search term (e.g., "language models", "glp-1").
        max_results: The maximum number of papers to retrieve.

    Returns:
        A list of dictionaries, where each dict represents a paper.
    """
    base_url = "http://export.arxiv.org/api/query?"
    # Simple query formulation to search all fields
    search_query = f"all:{urllib.parse.quote(query)}"
    
    url = f"{base_url}search_query={search_query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"

    try:
        response = urllib.request.urlopen(url)
        data = response.read()
        root = ET.fromstring(data)
    except Exception as e:
        print(f"Error fetching from arXiv: {e}")
        return []

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    papers = []

    for entry in root.findall("atom:entry", namespace):
        title = entry.find("atom:title", namespace).text.strip().replace("\n", " ") if entry.find("atom:title", namespace) is not None else "No Title"
        summary = entry.find("atom:summary", namespace).text.strip().replace("\n", " ") if entry.find("atom:summary", namespace) is not None else "No Summary"
        published = entry.find("atom:published", namespace).text if entry.find("atom:published", namespace) is not None else "Unknown Date"
        link = entry.find("atom:id", namespace).text if entry.find("atom:id", namespace) is not None else "No Link"
        
        authors = []
        for author in entry.findall("atom:author", namespace):
            name = author.find("atom:name", namespace).text if author.find("atom:name", namespace) is not None else "Unknown Author"
            authors.append(name)

        papers.append({
            "title": title,
            "abstract": summary,
            "published": published,
            "authors": authors,
            "url": link
        })

    return papers

if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = "machine learning"
    
    results = fetch_papers(query, max_results=3)
    print(json.dumps(results, indent=2, ensure_ascii=False))
