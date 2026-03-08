// main.js
document.addEventListener('DOMContentLoaded', () => {
    const searchBtn = document.getElementById('search-btn');
    const queryInput = document.getElementById('query-input');
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');
    const resultsList = document.getElementById('results-list');
    const papersContainer = document.getElementById('papers-container');
    const reviewPanel = document.getElementById('review-panel');
    const reviewContent = document.getElementById('review-content');
    const backBtn = document.getElementById('back-btn');
    const zoteroBtn = document.getElementById('zotero-btn');
    const zoteroStatus = document.getElementById('zotero-status');

    const API_BASE = 'http://127.0.0.1:8001';
    let currentPaper = null;

    searchBtn.addEventListener('click', async () => {
        const query = queryInput.value.trim();
        if (!query) return alert("Search topic cannot be empty.");

        // UI updates
        reviewPanel.style.display = 'none';
        resultsList.style.display = 'none';
        loaderText.textContent = "Searching arXiv for papers...";
        loader.style.display = 'block';

        try {
            const res = await fetch(`${API_BASE}/search?query=${encodeURIComponent(query)}&max_results=5`);
            if (!res.ok) throw new Error("Failed to fetch papers.");
            const papers = await res.json();

            renderPapers(papers);
        } catch (e) {
            console.error(e);
            alert(e.message);
        } finally {
            loader.style.display = 'none';
        }
    });

    function renderPapers(papers) {
        papersContainer.innerHTML = '';
        if (papers.length === 0) {
            papersContainer.innerHTML = '<p>No formatting results found.</p>';
        } else {
            papers.forEach(paper => {
                const card = document.createElement('div');
                card.className = 'paper-card';
                card.innerHTML = `
                    <h3>${paper.title}</h3>
                    <div class="paper-meta">${paper.authors.join(', ')} • ${paper.published.substring(0, 10)}</div>
                    <div class="paper-abstract">${paper.abstract}</div>
                    <button class="review-btn">Generate AI Review</button>
                `;
                card.querySelector('.review-btn').addEventListener('click', () => loadReview(paper));
                papersContainer.appendChild(card);
            });
        }
        resultsList.style.display = 'block';
    }

    async function loadReview(paper) {
        currentPaper = paper;
        resultsList.style.display = 'none';
        loaderText.textContent = "AI is reviewing the paper with 6-stage framework...";
        loader.style.display = 'block';

        zoteroBtn.style.display = 'none';
        zoteroStatus.textContent = '';
        reviewContent.innerHTML = '';

        try {
            const res = await fetch(`${API_BASE}/review`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paper: paper, save_to_zotero: false })
            });
            if (!res.ok) throw new Error("Review generation failed.");

            const data = await res.json();
            reviewContent.innerHTML = marked.parse(data.review);

            reviewPanel.style.display = 'block';
            zoteroBtn.style.display = 'block';
        } catch (e) {
            console.error(e);
            alert(e.message);
            resultsList.style.display = 'block';
        } finally {
            loader.style.display = 'none';
        }
    }

    backBtn.addEventListener('click', () => {
        reviewPanel.style.display = 'none';
        resultsList.style.display = 'block';
    });

    zoteroBtn.addEventListener('click', async () => {
        zoteroBtn.disabled = true;
        zoteroBtn.textContent = "Saving...";

        try {
            const res = await fetch(`${API_BASE}/review`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ paper: currentPaper, save_to_zotero: true })
            });
            if (!res.ok) throw new Error("Zotero sync failed.");
            const data = await res.json();
            zoteroStatus.textContent = "✓ " + data.zotero_sync.message;
        } catch (e) {
            console.error(e);
            zoteroStatus.textContent = "✗ Error: " + e.message;
            zoteroStatus.style.color = '#ef4444';
        } finally {
            zoteroBtn.textContent = "Save to Zotero";
            zoteroBtn.disabled = false;
        }
    });
});
