import time
import logging
import schedule

from datetime import datetime

from app.collector import collect_news
from app.analyzer import analyze_pending
from app.reporter import generate_report
from app.trends import analyze_trends
from app.weekly import generate_weekly_report


# =====================================================
# CONFIGURAZIONE LOG
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("AI-TECH-INTELLIGENCE")


# =====================================================
# RACCOLTA NOTIZIE
# =====================================================

def run_collection():

    logger.info("Avvio raccolta notizie")

    try:

        result = collect_news()

        logger.info(
            "Raccolta completata: %s articoli",
            result
        )

    except Exception:

        logger.exception(
            "Errore durante la raccolta"
        )


# =====================================================
# ANALISI AI
# =====================================================

def run_analysis():

    logger.info("Avvio analisi Qwen")

    try:

        analyze_pending()

        logger.info(
            "Analisi AI completata"
        )

    except Exception:

        logger.exception(
            "Errore durante analisi AI"
        )


# =====================================================
# DAILY INTELLIGENCE
# =====================================================

def run_daily_report():

    logger.info("Generazione Daily Intelligence")

    try:

        report = generate_report()

        logger.info(
            "Daily Report generato: %s",
            report
        )

    except Exception:

        logger.exception(
            "Errore generazione Daily Report"
        )


# =====================================================
# TREND INTELLIGENCE
# =====================================================

def run_trends():

    logger.info("Avvio Technology Trend Analysis")

    try:

        result = analyze_trends()

        logger.info(
            "Trend individuati: %s",
            len(result.get("trends", []))
        )

    except Exception:

        logger.exception(
            "Errore Trend Intelligence"
        )


# =====================================================
# WEEKLY INTELLIGENCE
# =====================================================

def run_weekly_report():

    logger.info("Generazione Weekly Intelligence")

    try:

        result = generate_weekly_report()

        logger.info(
            "Weekly Report generato: %s",
            result.get("report_path")
        )

    except Exception:

        logger.exception(
            "Errore Weekly Intelligence"
        )


# =====================================================
# CICLO INIZIALE
# =====================================================

def initial_cycle():

    logger.info("Avvio ciclo iniziale")

    run_collection()

    run_analysis()

    logger.info("Ciclo iniziale completato")


# =====================================================
# PROGRAMMAZIONE
# =====================================================

def configure_schedule():

    # Raccolta ogni 2 ore
    schedule.every(2).hours.do(
        run_collection
    )

    # Analisi ogni 2 ore
    schedule.every(2).hours.do(
        run_analysis
    )

    # Trend ogni giorno alle 07:00
    schedule.every().day.at("07:00").do(
        run_trends
    )

    # Daily Report ogni giorno alle 08:00
    schedule.every().day.at("08:00").do(
        run_daily_report
    )

    # Weekly Report ogni lunedì alle 09:00
    schedule.every().monday.at("09:00").do(
        run_weekly_report
    )


# =====================================================
# MAIN
# =====================================================

def main():

    logger.info(
        "AI TECH INTELLIGENCE SCHEDULER"
    )

    logger.info(
        "Avvio: %s",
        datetime.now()
    )

    configure_schedule()

    initial_cycle()

    logger.info(
        "Scheduler operativo"
    )

    while True:

        try:

            schedule.run_pending()

            time.sleep(30)

        except KeyboardInterrupt:

            logger.info(
                "Scheduler arrestato"
            )

            break

        except Exception:

            logger.exception(
                "Errore nel ciclo scheduler"
            )

            time.sleep(30)


if __name__ == "__main__":

    main()
