"""
Test manuale 1.5 - Connessione IMAP all'account Vianova.
Uso: .\venv\Scripts\python -m tests.test_imap_connect
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient


def main():
    print(f"Connessione a {config.IMAP_HOST}:{config.IMAP_PORT} come {config.IMAP_USERNAME}...")

    client = IMAPClient(
        host=config.IMAP_HOST,
        port=config.IMAP_PORT,
        username=config.IMAP_USERNAME,
        password=config.IMAP_PASSWORD,
    )

    try:
        client.connect()
        print("CONNESSIONE RIUSCITA")
        print(f"  Connected: {client.is_connected}")

        # Fetch ultima email ricevuta
        import email
        from email.header import decode_header

        status, messages = client._connection.select("INBOX")
        num_messages = int(messages[0])
        print(f"\n  Totale email in INBOX: {num_messages}")

        if num_messages > 0:
            status, data = client._connection.fetch(str(num_messages).encode(), "(RFC822)")
            raw = data[0][1]
            msg = email.message_from_bytes(raw)

            def decode_field(field):
                if field is None:
                    return "(vuoto)"
                decoded_parts = decode_header(field)
                result = ""
                for part, charset in decoded_parts:
                    if isinstance(part, bytes):
                        result += part.decode(charset or "utf-8", errors="replace")
                    else:
                        result += part
                return result

            print(f"\n  --- ULTIMA EMAIL ---")
            print(f"  Da:      {decode_field(msg['From'])}")
            print(f"  A:       {decode_field(msg['To'])}")
            print(f"  Oggetto: {decode_field(msg['Subject'])}")
            print(f"  Data:    {msg['Date']}")
            print(f"  -------------------")

        client.disconnect()
        print("\n  Disconnessione OK")
    except Exception as e:
        print(f"ERRORE: {e}")


if __name__ == "__main__":
    main()
