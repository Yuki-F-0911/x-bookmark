# api.py
"""FastAPI endpoint for Paper Reviewer & Zotero Automator service.

Provides:
- GET `/search` to find papers via arXiv
- POST `/review` to generate a review and optionally save to Zotero
"""
from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Any

from fetch_papers import fetch_papers
from review_engine import generate_review
from zotero_integration import save_to_zotero

app = FastAPI(title="AI Academic Paper Reviewer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/search")
async def search_papers(query: str = Query(..., description="Search topic"),
                        max_results: int = Query(5, description="Number of results")) -> List[Dict]:
    """Search for academic papers."""
    results = fetch_papers(query, max_results)
    if not results:
        raise HTTPException(status_code=404, detail="No papers found.")
    return results

@app.post("/review")
async def review_paper(payload: Dict = Body(...)) -> Dict[str, Any]:
    """Generate a review for a paper and optionally save to Zotero.
    
    Expected payload:
    {
        "paper": { "title": "...", "abstract": "...", "url": "..." },
        "save_to_zotero": true/false
    }
    """
    paper_data = payload.get("paper")
    if not paper_data:
        raise HTTPException(status_code=400, detail="Missing 'paper' data.")

    review_md = generate_review(paper_data)
    
    response = {
        "paper": paper_data,
        "review": review_md
    }
    
    if payload.get("save_to_zotero"):
        zotero_status = save_to_zotero(paper_data, review_md)
        response["zotero_sync"] = zotero_status
        
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
