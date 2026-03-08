# api.py
"""FastAPI endpoint for athletics knowledge service.

Provides a GET endpoint `/articles` that accepts a `topic` query parameter,
fetches data via `fetch_athletics_data.fetch_data`, generates an article
using `generate_article.generate_article`, and returns the Markdown content
as JSON.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict

app = FastAPI(title="Athletics Knowledge Service")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import local modules
from fetch_athletics_data import fetch_data
from generate_article import generate_article

@app.get("/articles")
async def get_article(topic: str = Query(..., description="Athletics topic to fetch data for")) -> Dict:
    """Fetch data for the given topic and return a generated article.

    Args:
        topic: The athletics-related topic (e.g., "marathon", "sprint").
    Returns:
        A JSON object with the markdown article under the key `article`.
    """
    try:
        data = fetch_data(topic)
        article_md = generate_article(data)
        return {"article": article_md}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
