"""
Test 1.22 (refactored) - Verifica salvataggio SOLO metadata allegati.
- Nessun file viene scritto su disco
- Estensioni pericolose vengono marcate come 'blocked'
Uso: .\venv\Scripts\python -m tests.test_save_attachment
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.db.email_repository import EmailRepository
from src.db.connection import get_connection
from src.ingestion.attachment_storage import AttachmentStorage


def get_account_id() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM accounts WHERE email_address = %s", (config.IMAP_USERNAME,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        raise RuntimeError("Account non trovato. Eseguire prima: python -m src.db.seed_account")
    return row[0]


def main():
    account_id = get_account_id()

    client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()
    repo = EmailRepository()
    storage = AttachmentStorage()

    client.connect()

    status, messages = client._connection.select("INBOX")
    total = int(messages[0])
    status, data = client._connection.fetch(str(total).encode(), "(RFC822)")
    raw = data[0][1]
    parsed = parser.parse(raw)

    print(f"Email: {parsed['subject']}")
    print(f"From:  {parsed['from']}")
    print(f"Allegati trovati: {len(parsed['attachments'])}")

    if not parsed["attachments"]:
        print("\nNESSUN ALLEGATO nell'ultima email.")
        print("Invia un'email con allegato e riprova.")
        client.disconnect()
        return

    email_id = repo.save_email(parsed, account_id)
    repo.save_headers(email_id, parsed["headers"])
    print(f"\nEmail salvata con id={email_id}")

    print(f"\n--- ALLEGATI (solo metadata, NO file su disco) ---")
    for att in parsed["attachments"]:
        att_id = storage.save_metadata(email_id, att)
        ext = Path(att["filename"]).suffix.lower()
        print(f"  {att['filename']}")
        print(f"    ID DB:       {att_id}")
        print(f"    Size:        {att['size']} bytes")
        print(f"    SHA256:      {att['hash_sha256'][:32]}...")
        print(f"    Estensione:  {ext}")
        print(f"    raw_bytes:   {'NON presente (OK)' if 'raw_bytes' not in att else 'PRESENTE (ERRORE!)'}")

    # Verifica: nessun file su disco
    att_dir = Path("data/attachments") / str(email_id)
    if att_dir.exists() and any(att_dir.iterdir()):
        print(f"\n  ERRORE: trovati file su disco in {att_dir}!")
    else:
        print(f"\n  OK: Nessun file scritto su disco.")

    # Verifica scan_status nel DB
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT filename, scan_status FROM email_attachments WHERE email_id = %s",
        (email_id,)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    print(f"\n--- SCAN STATUS nel DB ---")
    for filename, scan_status in rows:
        status_label = "BLOCCATO" if scan_status == "blocked" else scan_status
        print(f"  {filename} -> {status_label}")

    client.disconnect()
    print(f"\nTest completato.")


if __name__ == "__main__":
    main()
