"""
Test 1.30 - End-to-end: avvia IngestionService, processa tutte le email non lette,
verifica salvataggio in DB e su filesystem.
Uso: .\venv\Scripts\python -m tests.test_ingestion_e2e
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.db.connection import get_connection
from src.ingestion.service import IngestionService


def main():
    print("=" * 60)
    print("TEST END-TO-END - Ingestion Service")
    print("=" * 60)

    service = IngestionService()
    print(f"\nAccount ID: {service.account_id}")
    print(f"IMAP: {config.IMAP_HOST} ({config.IMAP_USERNAME})")
    print(f"\nEsecuzione polling...")

    processed = service.run_poll()
    print(f"\nEmail processate: {processed}")

    # Riepilogo dal DB
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM emails")
    total_emails = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails WHERE processing_status = 'completed'")
    completed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM emails WHERE processing_status = 'failed'")
    failed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM email_headers")
    total_headers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM email_attachments")
    total_attachments = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"RIEPILOGO DB")
    print(f"{'='*60}")
    print(f"  Totale email in DB:     {total_emails}")
    print(f"  - completed:            {completed}")
    print(f"  - failed:               {failed}")
    print(f"  Totale headers salvati: {total_headers}")
    print(f"  Totale allegati:        {total_attachments}")

    # Mostra ultime 5 email processate
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, from_address, subject, has_attachments, processing_status
           FROM emails ORDER BY id DESC LIMIT 5"""
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if rows:
        print(f"\n{'='*60}")
        print(f"ULTIME 5 EMAIL")
        print(f"{'='*60}")
        for row in rows:
            eid, from_addr, subject, has_att, status = row
            att_flag = " [ATT]" if has_att else ""
            subject_short = (subject or "(nessun oggetto)")[:50]
            print(f"  #{eid} [{status}] {from_addr} - {subject_short}{att_flag}")

    # Verifica file su disco
    att_dir = Path("data/attachments")
    if att_dir.exists():
        folders = list(att_dir.iterdir())
        total_files = sum(1 for f in att_dir.rglob("*") if f.is_file())
        print(f"\n  File su disco: {total_files} file in {len(folders)} cartelle")

    service.stop()
    print(f"\nTest end-to-end completato.")


if __name__ == "__main__":
    main()
