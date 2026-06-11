"""
Test 1.17 - Parsa l'ultima email dalla INBOX e la salva in DB (emails + email_headers).
Uso: .\venv\Scripts\python -m tests.test_save_email
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.db.email_repository import EmailRepository
from src.db.connection import get_connection


def get_account_id() -> int:
    """Recupera l'account_id dal DB basandosi sull'email IMAP configurata."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM accounts WHERE email_address = %s", (config.IMAP_USERNAME,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        raise RuntimeError("Account non trovato in DB. Eseguire prima: python -m src.db.seed_account")
    return row[0]


def main():
    account_id = get_account_id()
    print(f"Account ID: {account_id}")

    client = IMAPClient(
        host=config.IMAP_HOST,
        port=config.IMAP_PORT,
        username=config.IMAP_USERNAME,
        password=config.IMAP_PASSWORD,
    )
    parser = MIMEParser()
    repo = EmailRepository()

    client.connect()

    # Fetch ultima email
    status, messages = client._connection.select("INBOX")
    total = int(messages[0])
    print(f"Totale email in INBOX: {total}")

    status, data = client._connection.fetch(str(total).encode(), "(RFC822)")
    raw = data[0][1]

    # Parsing
    parsed = parser.parse(raw)
    print(f"\nEmail parsata:")
    print(f"  From:    {parsed['from']}")
    print(f"  Subject: {parsed['subject']}")
    print(f"  Headers: {len(parsed['headers'])} campi")

    # Salvataggio in DB
    print(f"\nSalvataggio in DB...")
    email_id = repo.save_email(parsed, account_id)
    print(f"  email_id generato: {email_id}")

    header_count = repo.save_headers(email_id, parsed["headers"])
    print(f"  Headers salvati: {header_count}")

    print(f"\nVerifica nel DB con:")
    print(f"  SELECT * FROM emails WHERE id = '{email_id}';")
    print(f"  SELECT * FROM email_headers WHERE email_id = '{email_id}';")

    client.disconnect()
    print("\nTest completato.")


if __name__ == "__main__":
    main()
