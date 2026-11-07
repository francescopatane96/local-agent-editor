import requests
import logging

from urllib.parse import urlparse

SEARXNG_URL = "http://127.0.0.1:8080"

logger = logging.getLogger(__name__)


# =====================================================
# ARGOMENTI DI RICERCA
# =====================================================

SEARCH_TOPICS = {

    "AI": [
        "artificial intelligence latest news",
        "large language models latest developments",
        "AI agents technology",
        "generative AI research"
    ],

    "Hardware": [
        "NVIDIA latest news",
        "AMD semiconductor news",
        "Intel processor technology",
        "TSMC semiconductor industry"
    ],

    "Cybersecurity": [
        "cybersecurity latest news",
        "data breaches security technology",
        "zero day vulnerability news"
    ],

    "Cloud": [
        "cloud computing latest developments",
        "AWS Azure Google Cloud news"
    ],

    "Robotics": [
        "humanoid robots latest news",
        "industrial robotics technology"
    ],

    "Startups": [
        "technology startups latest news",
        "AI startup funding news"
    ],

    "Open Source": [
        "open source AI projects",
        "new open source software releases"
    ]
}


# =====================================================
# PERIODI DI RICERCA
# =====================================================

TIME_RANGES = {

    "24 ore": "day",

    "7 giorni": "week",

    "30 giorni": "month",

    "Sempre": ""
}


# =====================================================
# MOTORE DI RICERCA
# =====================================================

def search_web(
    query,
    limit=10,
    time_range="week"
):

    endpoint = f"{SEARXNG_URL}/search"

    params = {

        "q": query,

        "format": "json",

        "categories": "news",

        "language": "all",

        "safesearch": 1

    }

    if time_range:

        params["time_range"] = time_range

    try:

        response = requests.get(

            endpoint,

            params=params,

            timeout=45

        )

        response.raise_for_status()

        data = response.json()

        results = []

        for item in data.get("results", []):

            url = item.get("url", "").strip()

            title = item.get("title", "").strip()

            if not url or not title:
                continue

            parsed = urlparse(url)

            if parsed.scheme not in ("http", "https"):
                continue

            results.append({

                "title": title,

                "url": url,

                "source": item.get(
                    "engine",
                    "Internet"
                ),

                "published": item.get(
                    "publishedDate",
                    ""
                ),

                "summary": item.get(
                    "content",
                    ""
                )[:5000],

                "category": "Technology"

            })

            if len(results) >= limit:
                break

        return results

    except requests.RequestException as error:

        logger.error(
            "Errore ricerca Internet: %s",
            error
        )

        return []

    except ValueError as error:

        logger.error(
            "Errore risposta JSON: %s",
            error
        )

        return []


# =====================================================
# RICERCA PER CATEGORIA
# =====================================================

def search_topic(

    category,

    queries=None,

    time_range="week"

):

    if queries is None:

        queries = SEARCH_TOPICS.get(
            category,
            [category]
        )

    collected = []

    for query in queries:

        logger.info(
            "Ricerca: %s",
            query
        )

        results = search_web(

            query,

            limit=10,

            time_range=time_range

        )

        for article in results:

            article["category"] = category

            collected.append(article)

    return collected


# =====================================================
# RICERCA COMPLETA
# =====================================================

def search_all_topics(time_range="week"):

    all_articles = []

    for category in SEARCH_TOPICS:

        articles = search_topic(

            category,

            time_range=time_range

        )

        all_articles.extend(articles)

    unique = {}

    for article in all_articles:

        url = article.get("url")

        if url and url not in unique:

            unique[url] = article

    return list(unique.values())


# =====================================================
# RICERCA PERSONALIZZATA
# =====================================================

def custom_search(

    query,

    limit=20,

    time_range="week"

):

    return search_web(

        query,

        limit=limit,

        time_range=time_range

    )
