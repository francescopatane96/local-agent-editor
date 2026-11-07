import json
import requests
import os
import sqlite3

from datetime import datetime

from app.database import get_articles

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434"
)

MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3.5:4b"
)

DB_PATH = "/app/data/news.db"


def save_trends(data):

    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trend_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            overview TEXT,
            trends_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        INSERT INTO trend_reports
        (overview, trends_json)
        VALUES (?, ?)
    """, (
        data.get("overview", ""),
        json.dumps(data.get("trends", []), ensure_ascii=False)
    ))

    conn.commit()
    conn.close()


def get_latest_trends():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    row = conn.execute("""
        SELECT *
        FROM trend_reports
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    conn.close()

    if not row:
        return None

    return {
        "overview": row["overview"],
        "trends": json.loads(row["trends_json"]),
        "created_at": row["created_at"]
    }


def analyze_trends():

    articles = get_articles(200)

    analyzed = [
        article
        for article in articles
        if article.get("ai_summary")
    ]

    if not analyzed:

        return {
            "overview": "Non ci sono ancora abbastanza notizie.",
            "trends": []
        }

    news_text = ""

    for article in analyzed[:100]:

        news_text += f"""
Titolo: {article['title']}
Categoria: {article['category']}
Riassunto: {article['ai_summary']}
Importanza: {article['importance']}
"""

    prompt = f"""
Sei un analista senior di intelligence tecnologica.

Analizza le notizie e individua i trend.

Distingui chiaramente:
- Evidenze presenti nelle notizie.
- Segnali emergenti.
- Ipotesi future.

Non inventare statistiche.
Non affermare che un trend sta crescendo se non ci sono
dati temporali sufficienti.

NOTIZIE:

{news_text}

Rispondi esclusivamente con JSON valido:

{{
    "overview": "Sintesi generale",
    "trends": [
        {{
            "name": "Nome del trend",
            "description": "Descrizione",
            "evidence": "Evidenze disponibili",
            "impact": "Alto, Medio o Basso",
            "confidence": "Alta, Media o Bassa"
        }}
    ]
}}

Massimo 8 trend.
"""

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

    data = json.loads(
        response.json()["response"]
    )

    save_trends(data)

    return data
