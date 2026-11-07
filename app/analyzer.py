import requests
import json
import os

from app.database import (
    get_unanalyzed_articles,
    update_analysis
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")

def analyze_article(article):

    prompt = f"""
Sei un giornalista tecnologico esperto.

Analizza questa notizia e rispondi esclusivamente
con un oggetto JSON valido.

TITOLO:
{article['title']}

FONTE:
{article['source']}

TESTO:
{article['original_summary']}

Rispondi con questa struttura:

{{
  "summary": "Riassunto in italiano",
  "analysis": "Impatto tecnologico e commerciale",
  "category": "AI, Cybersecurity, Cloud, Software, Hardware, Robotics, Startup oppure Open Source",
  "importance": 1
}}

IMPORTANCE deve essere un numero da 1 a 10.

Non inventare informazioni mancanti.
Non confondere ipotesi e fatti.
"""

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1
            }
        },
        timeout=300
    )

    response.raise_for_status()

    result = response.json()
    data = json.loads(result["response"])

    return data


def analyze_pending():

    articles = get_unanalyzed_articles(20)

    for article in articles:

        try:
            print(f"Analisi: {article['title']}")

            result = analyze_article(article)

            update_analysis(
                article["id"],
                result.get("summary", ""),
                result.get("analysis", ""),
                result.get("category", "Technology"),
                max(1, min(10, int(result.get("importance", 5))))
            )

        except Exception as error:
            print(f"Errore analisi: {error}")
