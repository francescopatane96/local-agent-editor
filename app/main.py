from app.database import init_db, get_statistics
from app.collector import collect_news
from app.analyzer import analyze_pending
from app.reporter import generate_report


def run_pipeline():

    print("\nAI TECH NEWS INTELLIGENCE")
    print("=========================\n")

    print("[1/4] Inizializzazione database")

    init_db()

    print("[2/4] Raccolta notizie")

    collected = collect_news()

    print(f"Articoli elaborati: {collected}")

    print("[3/4] Analisi AI con Qwen")

    analyze_pending()

    print("[4/4] Generazione report")

    report = generate_report()

    stats = get_statistics()

    print("\nOperazione completata!")
    print(f"Articoli nel database: {stats['total']}")
    print(f"Articoli analizzati: {stats['analyzed']}")
    print(f"Report: {report}")


if __name__ == "__main__":
    run_pipeline()
