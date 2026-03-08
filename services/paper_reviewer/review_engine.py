# review_engine.py
"""Generate a structured academic paper review.

Provides a function `generate_review(paper_data: dict) -> str` that converts
paper metadata into a formatted Markdown review following a 6-step framework.
"""
from typing import Dict, List

def generate_review(paper_data: Dict) -> str:
    """Generate a structured Markdown review for a single paper.

    Args:
        paper_data: A dictionary containing paper metadata ('title', 'abstract', 'authors', etc.).

    Returns:
        A Markdown string representing the structured review.
    """
    title = paper_data.get('title', 'Unknown Title')
    authors = ", ".join(paper_data.get('authors', ['Unknown']))
    year = paper_data.get('published', 'Unknown Year')[:4] if paper_data.get('published') != 'Unknown Date' else 'Unknown Year'
    url = paper_data.get('url', 'No URL provided')
    abstract = paper_data.get('abstract', 'No abstract available.')

    # Simple placeholder logic to simulate AI review generation based on 6-step framework
    # In a real application, this would call Anthropic's Claude API with a detailed prompt.
    strength1 = "A clear and focused research objective stated in the abstract."
    strength2 = "Methodology appears well-suited for the defined scope."
    limit1 = "Specific limitations or potential confounding variables are not explicitly detailed in the abstract alone."
    limit2 = "Long-term practical applicability requires further empirical validation."
    practice_implication = "Provides a foundational theoretical basis that could inform future experimental designs or policy frameworks."
    
    # Simple heuristic for grade based on abstract length
    grade = "B" if len(abstract) > 500 else "C"
    
    # Executive summary (simulated)
    exec_summary = f"This paper explores key concepts related to its core topic. The authors present significant findings that contribute to the current understanding of the field, highlighting potential avenues for future research."

    review_md = f"""# 論文レビュー: {title}

## 基本情報
- 著者: {authors}
- 発表年: {year}
- リンク: {url}

## エグゼクティブサマリー（3文以内）
{exec_summary}

## 研究の強み
1. {strength1}
2. {strength2}

## 研究の限界
1. {limit1}
2. {limit2}

## 実践への示唆
{practice_implication}

## 総合評価: {grade}
"""
    return review_md

def generate_reviews_for_papers(papers: List[Dict]) -> List[str]:
    """Generate reviews for a list of papers."""
    return [generate_review(paper) for paper in papers]

if __name__ == "__main__":
    sample_paper = {
        "title": "A Study on Artificial Intelligence",
        "authors": ["John Doe", "Jane Smith"],
        "published": "2024-03-01T12:00:00Z",
        "abstract": "This study comprehensively analyzes the impact of artificial intelligence on modern society, focusing on economic and ethical dimensions. We propose a new framework for evaluating AI safety.",
        "url": "http://arxiv.org/abs/1234.5678"
    }
    print(generate_review(sample_paper))
