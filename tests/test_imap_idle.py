"""
Test 1.24 - IMAP IDLE: avvia il listener e attende nuove email.
Invia un'email all'account durante l'esecuzione per verificare la detection.
Premi Ctrl+C per fermare.
Uso: .\venv\Scripts\python -m tests.test_imap_idle
"""

import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser


parser = MIMEParser()


def on_new_email(raw_emails: list[bytes]):
    print(f"\n{'='*50}")
    print(f"NUOVE EMAIL RILEVATE: {len(raw_emails)}")
    print(f"{'='*50}")
    for i, raw in enumerate(raw_emails, 1):
        parsed = parser.parse(raw)
        print(f"  [{i}] From:    {parsed['from']}")
        print(f"      Subject: {parsed['subject']}")
        print(f"      Allegati: {len(parsed['attachments'])}")
    print(f"{'='*50}")
    print("\nIn attesa di altre email... (Ctrl+C per uscire)")


def main():
    client = IMAPClient(
        host=config.IMAP_HOST,
        port=config.IMAP_PORT,
        username=config.IMAP_USERNAME,
        password=config.IMAP_PASSWORD,
    )

    def handle_sigint(signum, frame):
        print("\n\nInterrotto dall'utente.")
        client.stop_idle()

    signal.signal(signal.SIGINT, handle_sigint)

    client.connect()
    print(f"Connesso a {config.IMAP_HOST}")
    print(f"IDLE attivo - in attesa di nuove email...")
    print(f"Invia un'email a {config.IMAP_USERNAME} per testare.")
    print(f"Premi Ctrl+C per fermare.\n")

    client.idle_listen(on_new_email=on_new_email)
    client.disconnect()
    print("Disconnesso.")


if __name__ == "__main__":
    main()
