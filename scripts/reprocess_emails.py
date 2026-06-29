"""Riesegue country detection e content analysis su tutte le email gia' presenti nel DB
che non hanno ancora questi dati."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.connection import get_connection
from src.country.detector import CountryDetector
from src.db.country_repository import CountryRepository
from src.content.analyzer import ContentAnalyzer

def get_emails_without_country():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.id, e.from_address, e.body_text, e.body_html
        FROM emails e
        LEFT JOIN country_results cr ON cr.email_id = e.id
        WHERE cr.id IS NULL
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_emails_without_content():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.id, e.body_text, e.body_html
        FROM emails e
        LEFT JOIN content_results cr ON cr.email_id = e.id
        WHERE cr.id IS NULL
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_email_headers(email_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT raw_headers FROM emails WHERE id = %s", (email_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row.get("raw_headers") if row else None

def main():
    print("=" * 60)
    print("  REPROCESS EMAILS - Country Detection + Content Analysis")
    print("=" * 60)
    print()

    # --- Country Detection ---
    detector = CountryDetector()
    country_repo = CountryRepository()
    emails_no_country = get_emails_without_country()
    print(f"[Country] Email senza country detection: {len(emails_no_country)}")

    country_ok = 0
    country_fail = 0
    for email in emails_no_country:
        try:
            email_data = {
                "from": email.get("from_address", ""),
                "headers": {},
                "body_text": email.get("body_text", "") or "",
                "email_id": email["id"],
            }
            result = detector.detect(email_data)
            country_repo.save_result(email["id"], result)
            country_ok += 1
        except Exception as e:
            country_fail += 1
            print(f"  [ERRORE] Email {email['id']}: {e}")

    print(f"  Completato: {country_ok} ok, {country_fail} errori")
    print()

    # --- Content Analysis ---
    content_analyzer = ContentAnalyzer()
    emails_no_content = get_emails_without_content()
    print(f"[Content] Email senza content analysis: {len(emails_no_content)}")

    content_ok = 0
    content_fail = 0
    for email in emails_no_content:
        try:
            content_data = {
                "body_html": email.get("body_html"),
                "body_text": email.get("body_text"),
                "email_id": email["id"],
            }
            content_analyzer.analyze(content_data, save_to_db=True)
            content_ok += 1
        except Exception as e:
            content_fail += 1
            print(f"  [ERRORE] Email {email['id']}: {e}")

    print(f"  Completato: {content_ok} ok, {content_fail} errori")
    print()
    print("Done!")


if __name__ == "__main__":
    main()
