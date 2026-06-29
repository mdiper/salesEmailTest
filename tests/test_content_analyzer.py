r"""
Test 4.22/4.30/4.33 - ContentAnalyzer end-to-end.
Testa preprocessing, classificazione, summarization, entity extraction.
Uso: .\venv\Scripts\python -m tests.test_content_analyzer
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.content.analyzer import ContentAnalyzer


def main():
    analyzer = ContentAnalyzer()

    print("=" * 70)
    print("TEST CONTENT ANALYZER - EMAIL REALI")
    print("=" * 70)

    from src.utils.config import config
    from src.ingestion.imap_client import IMAPClient
    from src.ingestion.mime_parser import MIMEParser

    client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()

    client.connect()
    status, messages = client._connection.select("INBOX")
    total = int(messages[0])

    start = max(1, total - 2)
    for i in range(start, total + 1):
        status, data = client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)

        email_data = {
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
        }

        result = analyzer.analyze(email_data, save_to_db=False)

        print(f"\n  Email #{i}: {parsed['subject'][:50]}")
        print(f"    Category:   {result['category']} ({result['category_confidence']})")
        print(f"    Summary:    {result['summary'][:80]}...")
        ents = result["entities"]
        if ents["amounts"]:
            print(f"    Importi:    {[a['raw'] for a in ents['amounts']]}")
        if ents["references"]:
            print(f"    Riferimenti:{[r['raw'] for r in ents['references']]}")
        if ents["dates"]:
            print(f"    Date:       {ents['dates']}")
        if ents["phones"]:
            print(f"    Telefoni:   {ents['phones']}")

    client.disconnect()

    print(f"\n{'='*70}")
    print("Test completato.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
