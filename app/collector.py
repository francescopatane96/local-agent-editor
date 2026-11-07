import logging

from app.database import save_article

from app.search_engine import (
    search_all_topics
)

from app.extractor import (
    extract_article
)


logger = logging.getLogger(__name__)


# =====================================================
# RACCOLTA NOTIZIE INTERNET
# =====================================================

def collect_news():

    logger.info(
        "Avvio ricerca notizie su Internet"
    )

    articles = search_all_topics()

    collected = 0

    for article in articles:

        try:

            title = article.get("title", "").strip()

            url = article.get("url", "").strip()

            if not title or not url:
                continue

            logger.info(
                "Estrazione articolo: %s",
                title
            )

            original_text = extract_article(url)

            # Se non riusciamo a recuperare
            # l'articolo completo utilizziamo
            # la descrizione del motore di ricerca.

            if not original_text:

                original_text = article.get(
                    "summary",
                    ""
                )

            if not original_text:
                continue

            news = {
                "title": title,
                "url": url,
                "source": article.get(
                    "source",
                    "Internet"
                ),
                "published": article.get(
                    "published",
                    ""
                ),
                "category": article.get(
                    "category",
                    "Technology"
                ),
                "summary": original_text[:5000]
            }

            save_article(news)

            collected += 1

        except Exception as error:

            logger.exception(
                "Errore raccolta articolo: %s",
                error
            )

    logger.info(
        "Raccolta Internet completata: %s articoli elaborati",
        collected
    )

    return collected
