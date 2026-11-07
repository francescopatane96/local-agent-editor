import sqlite3
import os

DB_PATH = "/app/data/news.db"

def get_connection():
    os.makedirs("/app/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source TEXT,
            published TEXT,
            category TEXT,
            original_summary TEXT,
            ai_summary TEXT,
            ai_analysis TEXT,
            importance INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def save_article(article):
    conn = get_connection()

    try:
        conn.execute("""
            INSERT OR IGNORE INTO articles
            (title, url, source, published, category, original_summary)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            article["title"],
            article["url"],
            article["source"],
            article["published"],
            article["category"],
            article["summary"]
        ))

        conn.commit()
    finally:
        conn.close()

def get_articles(limit=100):
    conn = get_connection()

    rows = conn.execute("""
        SELECT * FROM articles
        ORDER BY published DESC, id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    conn.close()

    return [dict(row) for row in rows]

def get_unanalyzed_articles(limit=20):
    conn = get_connection()

    rows = conn.execute("""
        SELECT * FROM articles
        WHERE ai_summary IS NULL
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    conn.close()

    return [dict(row) for row in rows]

def update_analysis(article_id, summary, analysis, category, importance):
    conn = get_connection()

    conn.execute("""
        UPDATE articles
        SET ai_summary = ?,
            ai_analysis = ?,
            category = ?,
            importance = ?
        WHERE id = ?
    """, (summary, analysis, category, importance, article_id))

    conn.commit()
    conn.close()

def get_statistics():
    conn = get_connection()

    total = conn.execute(
        "SELECT COUNT(*) FROM articles"
    ).fetchone()[0]

    analyzed = conn.execute(
        "SELECT COUNT(*) FROM articles WHERE ai_summary IS NOT NULL"
    ).fetchone()[0]

    conn.close()

    return {"total": total, "analyzed": analyzed}
