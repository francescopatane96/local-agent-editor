import os
import json
import requests

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


# =====================================================
# AZIENDE MONITORATE
# =====================================================

COMPANIES = [
    "NVIDIA",
    "AMD",
    "Intel",
    "Google",
    "Microsoft",
    "OpenAI",
    "Anthropic",
    "Meta",
    "Amazon",
    "Apple"
]


# =====================================================
# ANALISI AZIENDA
# =====================================================

def analyze_company(company):

    articles = get_articles(500)

    relevant_articles = []

    # -------------------------------------------------
    # RICERCA NOTIZIE
    # -------------------------------------------------

    for article in articles:

        title = article.get("title") or ""

        summary = (
            article.get("original_summary") or ""
        )

        ai_summary = (
            article.get("ai_summary") or ""
        )

        text = (
            title + " " +
            summary + " " +
            ai_summary
        )

        if company.lower() in text.lower():

            relevant_articles.append(article)

    # -------------------------------------------------
    # NESSUNA NOTIZIA
    # -------------------------------------------------

    if not relevant_articles:

        return {
            "company": company,
            "summary": (
                "Non sono state trovate notizie "
                "riguardanti questa azienda nel database."
            ),
            "developments": [],
            "opportunities": [],
            "risks": [],
            "articles_analyzed": 0
        }

    # -------------------------------------------------
    # PREPARAZIONE NOTIZIE
    # -------------------------------------------------

    news_text = ""

    for article in relevant_articles[:30]:

        news_text += f"""

TITOLO:
{article.get('title', '')}

FONTE:
{article.get('source', '')}

DATA:
{article.get('published', '')}

CATEGORIA:
{article.get('category', '')}

RIASSUNTO:
{article.get('ai_summary') or article.get('original_summary') or ''}

ANALISI:
{article.get('ai_analysis') or ''}

IMPORTANZA:
{article.get('importance', 0)}

----------------------------------------

"""

    # -------------------------------------------------
    # PROMPT QWEN
    # -------------------------------------------------

    prompt = f"""

Sei un analista senior di Corporate Intelligence.

Devi analizzare le informazioni disponibili
sull'azienda {company}.

Utilizza esclusivamente le notizie fornite.

OBIETTIVI:

1. Identificare gli sviluppi tecnologici.
2. Individuare nuovi prodotti e servizi.
3. Analizzare investimenti e partnership.
4. Individuare opportunità commerciali.
5. Identificare rischi competitivi.
6. Valutare il posizionamento tecnologico.

IMPORTANTE:

- Non inventare informazioni.
- Non creare dati finanziari inesistenti.
- Non confondere ipotesi e fatti.
- Segnala quando le informazioni sono insufficienti.
- Distingui gli sviluppi recenti da quelli meno recenti.

NOTIZIE DISPONIBILI:

{news_text}

Rispondi esclusivamente con JSON valido.

STRUTTURA:

{{
    "summary": "Sintesi aziendale",

    "developments": [
        "Sviluppo tecnologico"
    ],

    "opportunities": [
        "Opportunità commerciale"
    ],

    "risks": [
        "Rischio identificato"
    ]
}}

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

        timeout=600
    )

    response.raise_for_status()

    # -------------------------------------------------
    # LETTURA RISULTATO
    # -------------------------------------------------

    result = response.json()

    data = json.loads(
        result["response"]
    )

    # -------------------------------------------------
    # RISULTATO FINALE
    # -------------------------------------------------

    data["company"] = company

    data["articles_analyzed"] = len(
        relevant_articles
    )

    return data


# =====================================================
# ANALISI DI TUTTE LE AZIENDE
# =====================================================

def analyze_all_companies():

    results = []

    for company in COMPANIES:

        print(
            f"Analisi aziendale: {company}"
        )

        try:

            result = analyze_company(company)

            results.append(result)

        except Exception as error:

            print(
                f"Errore analisi {company}: {error}"
            )

    return results
