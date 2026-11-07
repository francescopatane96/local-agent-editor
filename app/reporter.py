from datetime import datetime
from pathlib import Path
from html import escape

from app.database import get_articles

REPORT_DIR = Path("/app/data/reports")


def generate_report():

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    articles = get_articles(200)

    analyzed = [
        a for a in articles
        if a.get("ai_summary")
    ]

    analyzed.sort(
        key=lambda x: x.get("importance") or 0,
        reverse=True
    )

    now = datetime.now()
    date = now.strftime("%d/%m/%Y")
    timestamp = now.strftime("%Y%m%d-%H%M%S")

    categories = {}

    for article in analyzed:
        category = article.get("category") or "Technology"
        categories.setdefault(category, []).append(article)

    cards = []

    for index, article in enumerate(analyzed[:30], 1):

        title = escape(article.get("title") or "")
        source = escape(article.get("source") or "Fonte sconosciuta")
        category = escape(article.get("category") or "Technology")
        summary = escape(article.get("ai_summary") or "")
        analysis = escape(article.get("ai_analysis") or "")
        published = escape(article.get("published") or "Data non disponibile")
        url = escape(article.get("url") or "", quote=True)
        importance = max(1, min(10, int(article.get("importance") or 1)))

        cards.append(f"""
        <article class="news-card">
            <div class="card-meta">
                <span class="category">{category}</span>
                <span class="importance">Importanza {importance}/10</span>
            </div>

            <h2>{index}. {title}</h2>

            <div class="source">
                {source} · {published}
            </div>

            <h3>La notizia</h3>
            <p>{summary}</p>

            <h3>Analisi AI</h3>
            <p>{analysis}</p>

            <a class="read-more" href="{url}"
               target="_blank" rel="noopener noreferrer">
                Leggi la fonte originale →
            </a>
        </article>
        """)

    category_html = []

    for category, items in sorted(categories.items()):
        category_html.append(
            f'<span class="tag">{escape(category)} '
            f'<strong>{len(items)}</strong></span>'
        )

    html_document = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="AI Tech Intelligence - Daily Technology Briefing">
<title>AI Tech Intelligence | {date}</title>

<style>
:root {{
    --background: #f1f4f9;
    --surface: #ffffff;
    --primary: #102b46;
    --accent: #2878d0;
    --text: #26364a;
    --muted: #728096;
}}

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: var(--background);
    color: var(--text);
    font-family: Inter, Arial, sans-serif;
    line-height: 1.7;
}}

header {{
    background: linear-gradient(120deg, #102b46, #174e80);
    color: white;
    padding: 55px 20px;
}}

.header-content {{
    max-width: 1000px;
    margin: auto;
}}

header h1 {{
    font-size: clamp(32px, 5vw, 52px);
    margin: 0;
    letter-spacing: 2px;
}}

header p {{
    color: #c9dced;
}}

main {{
    max-width: 1000px;
    margin: 35px auto;
    padding: 0 20px;
}}

.stats {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 15px;
    margin-bottom: 30px;
}}

.stat {{
    background: var(--surface);
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 3px 15px #152b4510;
}}

.stat strong {{
    display: block;
    font-size: 28px;
    color: var(--accent);
}}

.news-card {{
    background: var(--surface);
    padding: 28px;
    margin-bottom: 22px;
    border-radius: 14px;
    border: 1px solid #e5eaf1;
    box-shadow: 0 4px 18px #152b4508;
    page-break-inside: avoid;
}}

.card-meta {{
    display: flex;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
}}

.category, .importance, .tag {{
    background: #eaf2fc;
    color: #175a9c;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 13px;
}}

.importance {{
    background: #fff3dc;
    color: #875b0b;
}}

.news-card h2 {{
    color: var(--primary);
    font-size: 23px;
    line-height: 1.35;
}}

.news-card h3 {{
    font-size: 15px;
    color: var(--accent);
    margin-bottom: 4px;
}}

.source {{
    color: var(--muted);
    font-size: 13px;
}}

.read-more {{
    display: inline-block;
    margin-top: 15px;
    color: var(--accent);
    font-weight: bold;
    text-decoration: none;
}}

.tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}}

footer {{
    background: var(--primary);
    color: white;
    text-align: center;
    padding: 30px;
    margin-top: 50px;
}}

@media(max-width:600px) {{
    .stats {{
        grid-template-columns: 1fr;
    }}

    .news-card {{
        padding: 20px;
    }}
}}

@media print {{
    body {{
        background: white;
    }}

    header {{
        background: var(--primary) !important;
        print-color-adjust: exact;
    }}

    .news-card {{
        box-shadow: none;
        border: 1px solid #ddd;
    }}

    a {{
        color: black;
    }}
}}
</style>
</head>

<body>

<header>
    <div class="header-content">
        <h1>AI TECH INTELLIGENCE</h1>
        <p>DAILY TECHNOLOGY BRIEFING</p>
        <p>{date} · Generato con Qwen AI</p>
    </div>
</header>

<main>

    <h2>Executive Overview</h2>

    <div class="stats">
        <div class="stat">
            <strong>{len(analyzed)}</strong>
            Articoli analizzati
        </div>
        <div class="stat">
            <strong>{len(categories)}</strong>
            Categorie
        </div>
        <div class="stat">
            <strong>{len([a for a in analyzed if (a.get("importance") or 0) >= 8])}</strong>
            Notizie prioritarie
        </div>
    </div>

    <h2>Technology Radar</h2>

    <div class="tags">
        {"".join(category_html)}
    </div>

    <h2 style="margin-top:40px">Top Technology News</h2>

    {"".join(cards) if cards else "<p>Nessun articolo analizzato disponibile.</p>"}

</main>

<footer>
    <strong>AI TECH INTELLIGENCE</strong>
    <p>Local AI · Qwen · Ollama · Open Technology</p>
    <small>Report generato il {now.strftime("%d/%m/%Y alle %H:%M")}</small>
</footer>

</body>
</html>
"""

    filename = f"ai-tech-daily-{timestamp}.html"
    filepath = REPORT_DIR / filename

    filepath.write_text(html_document, encoding="utf-8")

    return str(filepath)

