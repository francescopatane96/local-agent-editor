import requests
import trafilatura
import logging

from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def extract_article(url):

    try:

        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return ""

        response = requests.get(
            url,
            timeout=25,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; AITechIntelligence/1.0)"
                )
            }
        )

        response.raise_for_status()

        if len(response.content) > 10_000_000:
            return ""

        text = trafilatura.extract(
            response.text,
            include_comments=False,
            include_tables=False,
            favor_precision=True
        )

        if not text:
            return ""

        return text[:12000]

    except Exception as error:

        logger.warning(
            "Impossibile estrarre %s: %s",
            url,
            error
        )

        return ""
