// main.js
document.addEventListener('DOMContentLoaded', () => {
    const fetchBtn = document.getElementById('fetch-btn');
    const topicInput = document.getElementById('topic-input');
    const resultContainer = document.getElementById('result-container');
    const loader = document.getElementById('loader');
    const articleOutput = document.getElementById('article-output');

    // Make sure Marked.js is available
    if (typeof marked === 'undefined') {
        console.error("Marked.js is not loaded.");
    }

    fetchBtn.addEventListener('click', async () => {
        const topic = topicInput.value.trim();
        if (!topic) {
            alert("テーマを入力してください。");
            return;
        }

        // Show UI state
        resultContainer.style.display = 'block';
        loader.style.display = 'block';
        articleOutput.innerHTML = '';
        articleOutput.style.opacity = '0';
        fetchBtn.disabled = true;

        try {
            // Fetch from FastAPI endpoint
            const response = await fetch(`http://127.0.0.1:8000/articles?topic=${encodeURIComponent(topic)}`);
            
            if (!response.ok) {
                throw new Error(`サーバーエラー: ${response.status}`);
            }

            const data = await response.json();
            
            // Generate HTML from Markdown using marked
            const rawMarkdown = data.article || "# No Data";
            const htmlContent = marked.parse(rawMarkdown);
            
            // Display result
            articleOutput.innerHTML = htmlContent;
        } catch (error) {
            console.error("Error fetching article:", error);
            articleOutput.innerHTML = `<p style="color: #ef4444;">エラーが発生しました: ${error.message}</p>`;
        } finally {
            loader.style.display = 'none';
            articleOutput.style.opacity = '1';
            fetchBtn.disabled = false;
        }
    });
});
