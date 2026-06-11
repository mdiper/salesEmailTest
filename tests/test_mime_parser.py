"""
Test manuale 1.13 - Testa MIMEParser con email reali dalla mailbox.
Recupera le ultime 3 email e stampa il risultato del parsing.
Uso: .\venv\Scripts\python -m tests.test_mime_parser
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser


def main():
    client = IMAPClient(
        host=config.IMAP_HOST,
        port=config.IMAP_PORT,
        username=config.IMAP_USERNAME,
        password=config.IMAP_PASSWORD,
    )
    parser = MIMEParser()

    client.connect()

    # Fetch ultime 3 email (non solo UNSEEN, tutte)
    status, messages = client._connection.select("INBOX")
    total = int(messages[0])
    print(f"Totale email in INBOX: {total}\n")

    start = max(1, total - 2)
    for i in range(start, total + 1):
        print(f"{'='*60}")
        print(f"EMAIL #{i}")
        print(f"{'='*60}")

        status, data = client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            print("  (fetch fallito)\n")
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)

        print(f"  Message-ID: {parsed['message_id'][:60]}")
        print(f"  From:       {parsed['from']}")
        print(f"  To:         {parsed['to']}")
        print(f"  CC:         {parsed['cc'] or '(nessuno)'}")
        print(f"  Subject:    {parsed['subject']}")
        print(f"  Date:       {parsed['date']}")
        print(f"  Headers:    {len(parsed['headers'])} campi")
        print(f"  Body text:  {'SI' if parsed['body_text'] else 'NO'} ({len(parsed['body_text'] or '')} chars)")
        print(f"  Body HTML:  {'SI' if parsed['body_html'] else 'NO'} ({len(parsed['body_html'] or '')} chars)")
        print(f"  Allegati:   {len(parsed['attachments'])}")

        for att in parsed["attachments"]:
            print(f"    - {att['filename']} ({att['content_type']}, {att['size']} bytes, SHA256: {att['hash_sha256'][:16]}...)")

        if parsed["body_text"]:
            preview = parsed["body_text"][:200].replace("\n", " ")
            print(f"  Preview:    {preview}...")

        print()

    client.disconnect()
    print("Test completato.")


if __name__ == "__main__":
    main()
