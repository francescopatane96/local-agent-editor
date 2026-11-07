import sys
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

sys.path.insert(0, "/app")


# ============================================================
# IMPORTAZIONE MODULI APPLICAZIONE
# ============================================================

from app.database import (
    init_db,
    get_articles,
    get_statistics,
    save_article
)

from app.collector import collect_news

from app.analyzer import analyze_pending

from app.reporter import generate_report

from app.trends import (
    analyze_trends,
    get_latest_trends
)

from app.companies import (
    COMPANIES,
    analyze_company,
    analyze_all_companies
)

from app.weekly import generate_weekly_analysis

from app.search_engine import (
    custom_search,
    SEARCH_TOPICS,
    TIME_RANGES
)

from app.extractor import extract_article


# ============================================================
# CONFIGURAZIONE STREAMLIT
# ============================================================

st.set_page_config(
    page_title="AI Tech Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# DIRECTORY
# ============================================================

REPORT_DIR = Path("/app/data/reports")

WEEKLY_DIR = REPORT_DIR / "weekly"

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

WEEKLY_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# INIZIALIZZAZIONE DATABASE
# ============================================================

init_db()


# ============================================================
# FUNZIONI DI SUPPORTO
# ============================================================

def get_reports(directory):

    directory = Path(directory)

    directory.mkdir(
        parents=True,
        exist_ok=True
    )

    return sorted(
        directory.glob("*.html"),
        key=lambda file: file.stat().st_mtime,
        reverse=True
    )


def download_report(report_path):

    report_path = Path(report_path)

    if not report_path.exists():

        st.error(
            "Il report non esiste."
        )

        return

    with open(report_path, "rb") as file:

        st.download_button(
            label="⬇️ Scarica giornale HTML",
            data=file.read(),
            file_name=report_path.name,
            mime="text/html",
            use_container_width=True,
            key=f"download_{report_path.name}"
        )


def display_article(article):

    title = article.get("title") or "Senza titolo"

    with st.expander(title):

        col1, col2 = st.columns(2)

        with col1:

            st.write(
                "**Fonte:**",
                article.get("source") or "Sconosciuta"
            )

        with col2:

            st.write(
                "**Data:**",
                article.get("published") or "Non disponibile"
            )

        st.write(
            "**Categoria:**",
            article.get("category") or "Technology"
        )

        if article.get("ai_summary"):

            st.markdown("### Riassunto AI")

            st.write(
                article["ai_summary"]
            )

            st.markdown("### Analisi AI")

            st.write(
                article.get("ai_analysis") or ""
            )

            importance = article.get("importance") or 0

            st.progress(
                max(0, min(10, importance)) / 10
            )

            st.caption(
                f"Importanza: {importance}/10"
            )

        else:

            st.warning(
                "Notizia non ancora analizzata."
            )

        url = article.get("url", "")

        if url:

            parsed = urlparse(url)

            if parsed.scheme in ("http", "https"):

                st.link_button(
                    "Leggi articolo originale",
                    url
                )


def valid_web_url(url):

    try:

        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )

    except Exception:

        return False


# ============================================================
# HEADER PRINCIPALE
# ============================================================

st.title("🧠 AI TECH INTELLIGENCE")

st.subheader(
    "International Technology Intelligence Platform"
)

st.caption(
    "Powered by Qwen AI | Ollama | Docker | Python | SearXNG"
)

st.divider()


# ============================================================
# SIDEBAR E NAVIGAZIONE
# ============================================================

with st.sidebar:

    st.title("🧠 AI TECH")

    st.caption(
        "Technology Intelligence Platform"
    )

    st.markdown("---")

    section = st.radio(
        "NAVIGAZIONE",
        [
            "Dashboard",
            "Internet Intelligence",
            "Technology News",
            "Trend Intelligence",
            "Company Intelligence",
            "Weekly Intelligence",
            "HTML Reports"
        ]
    )

    st.markdown("---")

    st.markdown("### SISTEMA")

    st.write("AI Engine: Qwen")

    st.write("Inference: Ollama")

    st.write("Database: SQLite")

    st.write("Search Engine: SearXNG")

    st.write("Infrastructure: Docker")

    st.markdown("---")

    st.caption(
        "AI Tech Intelligence v1.0"
    )


# ============================================================
# STATISTICHE GENERALI
# ============================================================

stats = get_statistics()

total = stats["total"]

analyzed = stats["analyzed"]

pending = total - analyzed

percentage = (
    analyzed / total * 100
    if total > 0
    else 0
)


# ============================================================
# 1. DASHBOARD
# ============================================================

if section == "Dashboard":

    st.header("📊 Centro di controllo")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Notizie raccolte",
        total
    )

    col2.metric(
        "Notizie analizzate",
        analyzed
    )

    col3.metric(
        "Da analizzare",
        pending
    )

    col4.metric(
        "Completamento",
        f"{percentage:.1f}%"
    )

    st.divider()

    st.subheader("Centro operativo")

    col1, col2, col3 = st.columns(3)

    # --------------------------------------------------------
    # RACCOLTA NOTIZIE
    # --------------------------------------------------------

    with col1:

        if st.button(
            "🔎 Raccogli notizie RSS",
            use_container_width=True
        ):

            with st.spinner(
                "Raccolta notizie in corso..."
            ):

                try:

                    result = collect_news()

                    st.success(
                        f"Articoli elaborati: {result}"
                    )

                    st.rerun()

                except Exception as error:

                    st.error(str(error))

    # --------------------------------------------------------
    # ANALISI QWEN
    # --------------------------------------------------------

    with col2:

        if st.button(
            "🧠 Analizza con Qwen",
            use_container_width=True
        ):

            with st.spinner(
                "Qwen sta analizzando le notizie..."
            ):

                try:

                    analyze_pending()

                    st.success(
                        "Analisi completata!"
                    )

                    st.rerun()

                except Exception as error:

                    st.error(str(error))

    # --------------------------------------------------------
    # GENERAZIONE REPORT
    # --------------------------------------------------------

    with col3:

        if st.button(
            "📰 Genera Daily Report",
            use_container_width=True
        ):

            with st.spinner(
                "Generazione giornale HTML..."
            ):

                try:

                    report = generate_report()

                    st.session_state["daily_report"] = report

                    st.success(
                        "Giornale HTML generato!"
                    )

                except Exception as error:

                    st.error(str(error))

    if st.session_state.get("daily_report"):

        st.subheader("Daily Report")

        download_report(
            st.session_state["daily_report"]
        )

    st.divider()

    st.subheader("Ultime notizie")

    articles = get_articles(10)

    if articles:

        for article in articles:

            display_article(article)

    else:

        st.info(
            "Nessuna notizia disponibile."
        )


# ============================================================
# 2. INTERNET INTELLIGENCE
# ============================================================

elif section == "Internet Intelligence":

    st.header("🌐 Internet Intelligence")

    st.write(
        "Ricerca di notizie tecnologiche direttamente "
        "su Internet attraverso SearXNG."
    )

    st.info(
        "Cerca informazioni, scopri notizie recenti "
        "e importa gli articoli interessanti nel database."
    )

    # --------------------------------------------------------
    # FORM RICERCA
    # --------------------------------------------------------

    with st.form("internet_search_form"):

        st.subheader("Motore di ricerca")

        query = st.text_input(
            "Cosa vuoi cercare?",
            placeholder=(
                "Esempio: nuovi modelli AI "
                "rilasciati da Google e OpenAI"
            )
        )

        col1, col2, col3 = st.columns(3)

        with col1:

            category = st.selectbox(
                "Categoria",
                ["Tutte"] + list(SEARCH_TOPICS.keys())
            )

        with col2:

            period = st.selectbox(
                "Periodo",
                [
                    "24 ore",
                    "7 giorni",
                    "30 giorni",
                    "Sempre"
                ]
            )

        with col3:

            limit = st.slider(
                "Numero risultati",
                min_value=5,
                max_value=30,
                value=10
            )

        search_button = st.form_submit_button(
            "🔎 CERCA SU INTERNET",
            use_container_width=True
        )

    # --------------------------------------------------------
    # ESECUZIONE RICERCA
    # --------------------------------------------------------

    if search_button:

        if not query.strip():

            st.warning(
                "Inserisci un argomento da cercare."
            )

        else:

            search_query = query.strip()

            if category != "Tutte":

                search_query += " " + category

            time_range = TIME_RANGES[period]

            with st.spinner(
                "Ricerca delle notizie su Internet..."
            ):

                try:

                    results = custom_search(
                        search_query,
                        limit=limit,
                        time_range=time_range
                    )

                    st.session_state["internet_results"] = results

                    st.session_state["internet_query"] = query

                    st.session_state["internet_category"] = category

                    st.session_state["internet_period"] = period

                except Exception as error:

                    st.error(
                        f"Errore durante la ricerca: {error}"
                    )

    # --------------------------------------------------------
    # RISULTATI
    # --------------------------------------------------------

    results = st.session_state.get(
        "internet_results",
        []
    )

    if results:

        st.divider()

        st.subheader(
            "📡 Risultati della ricerca"
        )

        st.caption(
            f"Ricerca: {st.session_state.get('internet_query', '')}"
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Risultati trovati",
            len(results)
        )

        col2.metric(
            "Periodo",
            st.session_state.get(
                "internet_period",
                "N/D"
            )
        )

        st.write(
            "Seleziona gli articoli che desideri importare."
        )

        selected_articles = []

        for index, article in enumerate(results):

            title = article.get(
                "title",
                "Senza titolo"
            )

            url = article.get(
                "url",
                ""
            )

            domain = (
                urlparse(url).netloc.replace("www.", "")
                if valid_web_url(url)
                else "Fonte sconosciuta"
            )

            with st.expander(
                f"📰 {title}"
            ):

                col1, col2 = st.columns(2)

                col1.write(
                    f"**Fonte:** {domain}"
                )

                col2.write(
                    f"**Data:** {article.get('published') or 'Non disponibile'}"
                )

                st.write(
                    article.get("summary")
                    or "Descrizione non disponibile."
                )

                if valid_web_url(url):

                    st.link_button(
                        "Leggi articolo originale",
                        url
                    )

                selected = st.checkbox(
                    "Seleziona per importazione",
                    key=f"web_article_{index}_{url}"
                )

                if selected:

                    selected_articles.append(article)

        # ----------------------------------------------------
        # IMPORTAZIONE ARTICOLI
        # ----------------------------------------------------

        st.divider()

        st.subheader(
            "📥 Importazione nel database"
        )

        st.write(
            f"Articoli selezionati: {len(selected_articles)}"
        )

        if st.button(
            "IMPORTA ARTICOLI SELEZIONATI",
            use_container_width=True,
            disabled=not selected_articles
        ):

            imported = 0

            progress = st.progress(0)

            with st.spinner(
                "Recupero e importazione degli articoli..."
            ):

                for index, article in enumerate(
                    selected_articles
                ):

                    try:

                        url = article.get("url", "")

                        if not valid_web_url(url):

                            continue

                        # Estrazione testo originale

                        content = extract_article(url)

                        # Fallback descrizione SearXNG

                        if not content:

                            content = article.get(
                                "summary",
                                ""
                            )

                        if not content:

                            continue

                        domain = urlparse(url).netloc.replace(
                            "www.",
                            ""
                        )

                        selected_category = st.session_state.get(
                            "internet_category",
                            "Tutte"
                        )

                        if selected_category == "Tutte":

                            selected_category = "Technology"

                        news = {

                            "title": article.get(
                                "title",
                                "Senza titolo"
                            ),

                            "url": url,

                            "source": domain,

                            "published": article.get(
                                "published",
                                ""
                            ),

                            "category": selected_category,

                            "summary": content[:5000]

                        }

                        save_article(news)

                        imported += 1

                    except Exception as error:

                        st.warning(
                            f"Errore importazione: {error}"
                        )

                    finally:

                        progress.progress(
                            (index + 1) / len(selected_articles)
                        )

            st.success(
                f"Operazione completata. "
                f"{imported} articoli elaborati."
            )

            st.info(
                "Gli articoli sono disponibili nella "
                "sezione Technology News. "
                "I duplicati vengono ignorati da SQLite."
            )

            st.rerun()

    elif "internet_results" in st.session_state:

        st.warning(
            "Nessun risultato trovato. "
            "Prova a modificare la ricerca."
        )

    else:

        st.info(
            "Effettua una ricerca per visualizzare "
            "le notizie disponibili."
        )


# ============================================================
# 3. TECHNOLOGY NEWS
# ============================================================

elif section == "Technology News":

    st.header("🌍 Technology News")

    articles = get_articles(200)

    if articles:

        categories = sorted(
            set(
                article.get("category") or "Technology"
                for article in articles
            )
        )

        category = st.selectbox(
            "Categoria",
            ["Tutte"] + categories
        )

        search = st.text_input(
            "Cerca notizie"
        )

        filtered = articles

        if category != "Tutte":

            filtered = [
                article
                for article in filtered
                if article.get("category") == category
            ]

        if search:

            filtered = [
                article
                for article in filtered
                if search.lower() in (
                    article.get("title") or ""
                ).lower()
            ]

        st.caption(
            f"Notizie trovate: {len(filtered)}"
        )

        for article in filtered:

            display_article(article)

    else:

        st.info(
            "Nessuna notizia disponibile."
        )


# ============================================================
# 4. TREND INTELLIGENCE
# ============================================================

elif section == "Trend Intelligence":

    st.header("📈 Technology Trend Intelligence")

    st.write(
        "Identificazione dei principali trend tecnologici."
    )

    if st.button(
        "Analizza trend tecnologici",
        use_container_width=True
    ):

        with st.spinner(
            "Qwen sta analizzando i trend..."
        ):

            try:

                data = analyze_trends()

                st.session_state["trends_data"] = data

                st.success(
                    "Analisi completata!"
                )

            except Exception as error:

                st.error(str(error))

    trends = (
        st.session_state.get("trends_data")
        or get_latest_trends()
    )

    if trends:

        st.subheader("Executive Overview")

        st.write(
            trends.get("overview", "")
        )

        st.subheader("Trend individuati")

        for trend in trends.get("trends", []):

            with st.expander(
                trend.get("name", "Trend")
            ):

                st.write(
                    trend.get("description", "")
                )

                st.write(
                    "**Evidenze:**",
                    trend.get("evidence", "")
                )

                col1, col2 = st.columns(2)

                col1.metric(
                    "Impatto",
                    trend.get("impact", "N/D")
                )

                col2.metric(
                    "Confidenza",
                    trend.get("confidence", "N/D")
                )

    else:

        st.info(
            "Non sono ancora disponibili analisi dei trend."
        )


# ============================================================
# 5. COMPANY INTELLIGENCE
# ============================================================

elif section == "Company Intelligence":

    st.header("🏢 Company Intelligence")

    st.write(
        "Analisi delle principali aziende tecnologiche."
    )

    company = st.selectbox(
        "Seleziona azienda",
        COMPANIES
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Analizza azienda",
            use_container_width=True
        ):

            with st.spinner(
                f"Analisi di {company}..."
            ):

                try:

                    result = analyze_company(company)

                    st.session_state["company_result"] = result

                except Exception as error:

                    st.error(str(error))

    with col2:

        if st.button(
            "Analizza tutte le aziende",
            use_container_width=True
        ):

            with st.spinner(
                "Analisi delle aziende in corso..."
            ):

                try:

                    results = analyze_all_companies()

                    st.session_state["all_companies"] = results

                    st.success(
                        "Analisi completata!"
                    )

                except Exception as error:

                    st.error(str(error))

    result = st.session_state.get(
        "company_result"
    )

    if result and result.get("company") == company:

        st.divider()

        st.subheader(company)

        st.write(
            result.get("summary", "")
        )

        st.markdown("### Sviluppi tecnologici")

        for item in result.get("developments", []):

            st.markdown(f"- {item}")

        st.markdown("### Opportunità")

        for item in result.get("opportunities", []):

            st.markdown(f"- {item}")

        st.markdown("### Rischi")

        for item in result.get("risks", []):

            st.markdown(f"- {item}")

        st.caption(
            f"Notizie analizzate: "
            f"{result.get('articles_analyzed', 0)}"
        )

    all_companies = st.session_state.get(
        "all_companies",
        []
    )

    if all_companies:

        st.divider()

        st.subheader("Risultati aziendali")

        for item in all_companies:

            with st.expander(
                item.get("company", "Azienda")
            ):

                st.write(
                    item.get("summary", "")
                )


# ============================================================
# 6. WEEKLY INTELLIGENCE
# ============================================================

elif section == "Weekly Intelligence":

    st.header("📅 Weekly Technology Intelligence")

    st.write(
        "Report strategico settimanale generato con Qwen."
    )

    st.info(
        "Il sistema analizzerà le notizie degli ultimi sette giorni."
    )

    if st.button(
        "🚀 GENERATE WEEKLY INTELLIGENCE",
        use_container_width=True
    ):

        with st.spinner(
            "Qwen sta preparando il report settimanale..."
        ):

            try:

                result = generate_weekly_analysis()

                st.session_state["weekly_result"] = result

                st.success(
                    "Weekly Intelligence generata!"
                )

            except Exception as error:

                st.error(
                    f"Errore durante la generazione: {error}"
                )

    result = st.session_state.get(
        "weekly_result"
    )

    if result:

        st.divider()

        st.subheader("Executive Summary")

        st.write(
            result.get("summary", "")
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Notizie analizzate",
            result.get("articles_analyzed", 0)
        )

        col2.metric(
            "Notizie principali",
            len(result.get("top_news", []))
        )

        st.subheader("Top Technology News")

        for news in result.get("top_news", []):

            with st.expander(
                news.get("title", "Notizia")
            ):

                st.write(
                    news.get("analysis", "")
                )

                st.metric(
                    "Importanza",
                    news.get("importance", 0)
                )

        st.subheader("Technology Trends")

        for trend in result.get("trends", []):

            with st.expander(
                trend.get("name", "Trend")
            ):

                st.write(
                    trend.get("description", "")
                )

        st.subheader("Company Intelligence")

        for company in result.get("companies", []):

            st.markdown(
                f"**{company.get('name', '')}**"
            )

            st.write(
                company.get("development", "")
            )

        st.subheader("Business Opportunities")

        for opportunity in result.get("opportunities", []):

            st.markdown(
                f"- {opportunity}"
            )

        st.subheader("Outlook")

        st.write(
            result.get("outlook", "")
        )

        if result.get("generated_at"):

            st.caption(
                f"Generato: {result['generated_at']}"
            )

    st.divider()

    st.subheader("Archivio Weekly Reports")

    weekly_reports = get_reports(WEEKLY_DIR)

    if weekly_reports:

        for report in weekly_reports:

            with st.expander(report.name):

                download_report(report)

    else:

        st.info(
            "Non sono ancora presenti report settimanali HTML."
        )


# ============================================================
# 7. HTML REPORTS
# ============================================================

elif section == "HTML Reports":

    st.header("📰 HTML Reports")

    st.write(
        "Archivio dei report di intelligence generati."
    )

    st.subheader("Daily Reports")

    daily_reports = get_reports(REPORT_DIR)

    daily_reports = [
        report
        for report in daily_reports
        if report.parent == REPORT_DIR
    ]

    if daily_reports:

        for report in daily_reports:

            with st.expander(report.name):

                download_report(report)

    else:

        st.info(
            "Nessun Daily Report disponibile."
        )

    st.divider()

    st.subheader("Weekly Reports")

    weekly_reports = get_reports(WEEKLY_DIR)

    if weekly_reports:

        for report in weekly_reports:

            with st.expander(report.name):

                download_report(report)

    else:

        st.info(
            "Nessun Weekly Report disponibile."
        )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.markdown(
    """
    <div style="
        text-align: center;
        padding: 25px;
    ">

        <h3>🧠 AI TECH INTELLIGENCE</h3>

        International Technology Intelligence Platform

        <p>
            Qwen | Ollama | Docker | Python | SQLite | SearXNG
        </p>

        <small>
            Local AI Technology Intelligence System
        </small>

    </div>
    """,
    unsafe_allow_html=True
)
