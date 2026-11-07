import os
import json
import requests
import html

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from app.database import get_articles


# =====================================================
# CONFIGURAZIONE
# =====================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3.5:4b"
)

REPORT_DIR = Path("/app/data/reports/weekly")


# =====================================================
# GESTIONE DATE
# =====================================================

def parse_article_date(value):

    if not value:
        return None

    value = str(value).strip()

    try:
        date = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    except ValueError:

        try:
            date = parsedate_to_datetime(value)

        except (TypeError, ValueError, OverflowError):
            return None

    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    return date.astimezone(timezone.utc)


# =====================================================
# RACCOLTA NOTIZIE SETTIMANALI
# =====================================================

def get_weekly_articles():

    articles = get_articles(500)

    now = datetime.now(timezone.utc)

    cutoff = now - timedelta(days=7)

    recent_articles = []

    for article in articles:

        published = article.get("published")

        date = parse_article_date(published)

        if date is None:
            continue

        if cutoff <= date <= now:

            recent_articles.append(article)

    recent_articles.sort(
        key=lambda article: (
            parse_article_date(article.get("published"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True
    )

    return recent_articles


# =====================================================
# GENERAZIONE ANALISI CON QWEN
# =====================================================

def generate_weekly_analysis():

    recent_articles = get_weekly_articles()

    if not recent_articles:

        return {
            "title": "Weekly Technology Intelligence",
            "summary": (
                "Non sono disponibili notizie con date valide "
                "negli ultimi sette giorni."
            ),
            "top_news": [],
            "trends": [],
            "companies": [],
            "opportunities": [],
            "outlook": "",
            "articles_analyzed": 0
        }

    # -------------------------------------------------
    # PREPARAZIONE NOTIZIE
    # -------------------------------------------------

    news_text = ""

    for index, article in enumerate(recent_articles[:100], 1):

        news_text += f"""
NOTIZIA {index}

Titolo:
{article.get('title', '')}

Fonte:
{article.get('source', '')}

Data:
{article.get('published', '')}

Categoria:
{article.get('category', '')}

Riassunto:
{article.get('ai_summary') or article.get('original_summary') or ''}

Analisi:
{article.get('ai_analysis') or ''}

Importanza:
{article.get('importance', 0)}

URL:
{article.get('url', '')}

----------------------------------------
"""

    # -------------------------------------------------
    # PROMPT
    # -------------------------------------------------

    prompt = f"""
Sei il direttore di una redazione internazionale
specializzata in Technology Intelligence.

Devi produrre un report strategico settimanale
sul panorama tecnologico internazionale.

LINGUA: Italiano.

PERIODO: Ultimi sette giorni.

Analizza le notizie fornite.

OBIETTIVI:

1. Identificare gli avvenimenti più importanti.
2. Analizzare il settore AI e Machine Learning.
3. Analizzare semiconduttori e hardware.
4. Individuare le aziende protagoniste.
5. Identificare i trend tecnologici.
6. Individuare opportunità commerciali.
7. Elaborare prospettive per il futuro.

REGOLE:

- Non inventare notizie.
- Non inventare dati finanziari.
- Non inventare statistiche.
- Utilizza titoli realmente presenti nelle notizie.
- Distingui fatti e ipotesi.
- Non presentare ipotesi come fatti.
- Se mancano informazioni, dichiaralo.
- Non confondere il numero di articoli con la crescita
  effettiva di un mercato.

NOTIZIE DISPONIBILI:

{news_text}

Rispondi esclusivamente con JSON valido.

STRUTTURA:

{{
    "title": "Weekly Technology Intelligence",

    "summary": "Executive summary dettagliato",

    "top_news": [
        {{
            "title": "Titolo originale della notizia",
            "analysis": "Analisi e impatto",
            "importance": 8
        }}
    ],

    "trends": [
        {{
            "name": "Nome del trend",
            "description": "Descrizione",
            "evidence": "Evidenze disponibili"
        }}
    ],

    "companies": [
        {{
            "name": "Nome azienda",
            "development": "Sviluppo identificato"
        }}
    ],

    "opportunities": [
        "Opportunità commerciale identificata"
    ],

    "outlook": "Prospettive per la prossima settimana"
}}

Massimo:
- 10 notizie principali.
- 8 trend.
- 10 aziende.
- 8 opportunità.

"""

    # -------------------------------------------------
    # CHIAMATA OLLAMA
    # -------------------------------------------------

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",

        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",

            "options": {
                "temperature": 0.2
            }
        },

        timeout=900
    )

    response.raise_for_status()

    result = response.json()

    data = json.loads(
        result["response"]
    )

    # -------------------------------------------------
    # METADATI
    # -------------------------------------------------

    data["generated_at"] = datetime.now().isoformat()

    data["articles_analyzed"] = len(
        recent_articles
    )

    return data


# =====================================================
# GENERAZIONE HTML
# =====================================================

def generate_weekly_html(data):

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    now = datetime.now()

    timestamp = now.strftime(
        "%Y%m%d-%H%M%S"
    )

    date_label = now.strftime(
        "%d/%m/%Y"
    )

    def safe(value):

        return html.escape(
            str(value or ""),
            quote=True
        )

    # -------------------------------------------------
    # NOTIZIE
    # -------------------------------------------------

    news_cards = []

    for index, article in enumerate(
        data.get("top_news", []),
        1
    ):

        title = safe(article.get("title"))

        analysis = safe(article.get("analysis"))

        importance = article.get("importance", 5)

        try:
            importance = max(
                1,
                min(10, int(importance))
            )

        except (TypeError, ValueError):
            importance = 5

        news_cards.append(f"""
        <article class="card">

            <span class="badge">
                PRIORITÀ {importance}/10
            </span>

            <h3>{index}. {title}</h3>

            <p>{analysis}</p>

        </article>
        """)

    # -------------------------------------------------
    # TREND
    # -------------------------------------------------

    trend_cards = []

    for trend in data.get("trends", []):

        trend_cards.append(f"""
        <article class="card">

            <h3>{safe(trend.get('name'))}</h3>

            <p>{safe(trend.get('description'))}</p>

            <p>
                <strong>Evidenze:</strong>
                {safe(trend.get('evidence'))}
            </p>

        </article>
        """)

    # -------------------------------------------------
    # AZIENDE
    # -------------------------------------------------

    company_cards = []

    for company in data.get("companies", []):

        company_cards.append(f"""
        <article class="card">

            <h3>{safe(company.get('name'))}</h3>

            <p>{safe(company.get('development'))}</p>

        </article>
        """)

    # -------------------------------------------------
    # OPPORTUNITÀ
    # -------------------------------------------------

    opportunities = []

    for opportunity in data.get("opportunities", []):

        opportunities.append(
            f"<li>{safe(opportunity)}</li>"
        )

    # -------------------------------------------------
    # DOCUMENTO HTML
    # -------------------------------------------------

    document = f"""<!DOCTYPE html>

<html lang="it">

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>Weekly Technology Intelligence</title>

<style>

:root {{

    --primary: #102b46;
    --secondary: #174e80;
    --accent: #2878d0;
    --background: #f1f4f9;
    --surface: #ffffff;
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
    font-family: Arial, sans-serif;
    line-height: 1.7;

}}

header {{

    background: linear-gradient(
        120deg,
        var(--primary),
        var(--secondary)
    );

    color: white;
    padding: 85px 25px;

}}

.header-content {{

    max-width: 1000px;
    margin: auto;

}}

header h1 {{

    font-size: clamp(32px, 5vw, 52px);
    letter-spacing: 2px;
    margin: 0;

}}

header p {{

    color: #c9dced;

}}

main {{

    max-width: 1000px;
    margin: 40px auto;
    padding: 0 20px;

}}

section {{

    margin-bottom: 45px;

}}

section h2 {{

    color: var(--primary);
    border-bottom: 3px solid var(--accent);
    padding-bottom: 10px;

}}

.card {{

    background: var(--surface);
    padding: 25px;
    margin: 20px 0;
    border-radius: 12px;
    border: 1px solid #e5eaf1;
    box-shadow: 0 4px 18px #152b4508;

    page-break-inside: avoid;

}}

.card h3 {{

    color: var(--primary);
    margin-top: 8px;

}}

.badge {{

    background: #eaf2fc;
    color: #175a9c;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;

}}

.summary {{

    background: white;
    padding: 30px;
    border-radius: 12px;
    border-left: 5px solid var(--accent);

}}

.stats {{

    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
    margin: 25px 0;

}}

.stat {{

    background: white;
    padding: 20px;
    border-radius: 12px;

}}

.stat strong {{

    display: block;
    color: var(--accent);
    font-size: 30px;

}}

li {{

    margin-bottom: 12px;

}}

footer {{

    background: var(--primary);
    color: white;
    text-align: center;
    padding: 35px;

}}

@media(max-width:600px) {{

    .stats {{
        grid-template-columns: 1fr;
    }}

}}

@media print {{

    body {{
        background: white;
    }}

    header {{
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
    }}

    .card {{
        box-shadow: none;
    }}

}}

</style>

</head>

<body>

<header>

    <div class="header-content">

        <h1>AI TECH INTELLIGENCE</h1>

        <h2>WEEKLY TECHNOLOGY BRIEFING</h2>

        <p>Strategic Technology Intelligence</p>

        <p>{date_label}</p>

        <p>Powered by Qwen AI</p>

    </div>

</header>

<main>

    <section>

        <h2>Executive Summary</h2>

        <div class="summary">

            {safe(data.get('summary'))}

        </div>

        <div class="stats">

            <div class="stat">

                <strong>{data.get('articles_analyzed', 0)}</strong>

                Notizie analizzate

            </div>

            <div class="stat">

                <strong>{len(data.get('top_news', []))}</strong>

                Notizie principali

            </div>

        </div>

    </section>

    <section>

        <h2>Top Technology News</h2>

        {"".join(news_cards) or "<p>Nessuna notizia disponibile.</p>"}

    </section>

    <section>

        <h2>Technology Trends</h2>

        {"".join(trend_cards) or "<p>Nessun trend identificato.</p>"}

    </section>

    <section>

        <h2>Company Intelligence</h2>

        {"".join(company_cards) or "<p>Nessuna azienda identificata.</p>"}

    </section>

    <section>

        <h2>Business Opportunities</h2>

        <div class="card">

            <ul>

                {"".join(opportunities) or "<li>Nessuna opportunità identificata.</li>"}

            </ul>

        </div>

    </section>

    <section>

        <h2>Outlook</h2>

        <div class="summary">

            {safe(data.get('outlook'))}

        </div>

    </section>

</main>

<footer>

    <h3>AI TECH INTELLIGENCE</h3>

    <p>Local AI | Qwen | Ollama | Docker</p>

    <small>
        Report generato il {date_label}
    </small>

</footer>

</body>

</html>
"""

    # -------------------------------------------------
    # SALVATAGGIO
    # -------------------------------------------------

    filename = (
        f"ai-tech-weekly-{timestamp}.html"
    )

    filepath = REPORT_DIR / filename

    filepath.write_text(
        document,
        encoding="utf-8"
    )

    return str(filepath)


# =====================================================
# GENERAZIONE COMPLETA WEEKLY REPORT
# =====================================================

def generate_weekly_report():

    print(
        "Avvio generazione Weekly Intelligence..."
    )

    data = generate_weekly_analysis()

    report_path = generate_weekly_html(data)

    data["report_path"] = report_path

    print(
        f"Report settimanale creato: {report_path}"
    )

    return data
