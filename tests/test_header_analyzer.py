"""
Test 2.10 - HeaderAnalyzer con email reali dall'account Vianova.
Analizza le ultime 5 email e mostra i risultati dei security check.
Uso: .\venv\Scripts\python -m tests.test_header_analyzer
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.security.header_analyzer import HeaderAnalyzer


def main():
    client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()
    analyzer = HeaderAnalyzer()

    client.connect()

    status, messages = client._connection.select("INBOX")
    total = int(messages[0])
    print(f"Totale email in INBOX: {total}")
    print(f"Analisi ultime 5 email...\n")

    start = max(1, total - 4)
    for i in range(start, total + 1):
        status, data = client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)
        results = analyzer.analyze(parsed["headers"])

        risk = results["total_risk_contribution"]
        risk_bar = "#" * (risk // 5) + "." * (20 - risk // 5)

        print(f"{'='*70}")
        print(f"EMAIL #{i}: {parsed['subject'][:50]}")
        print(f"  From: {parsed['from']}")
        print(f"  Risk: [{risk_bar}] {risk}/100")
        print(f"  SPF:          {'PASS' if results['spf']['pass'] else 'FAIL'} (risk +{results['spf']['risk_contribution']})")
        print(f"  DKIM:         {'PASS' if results['dkim']['pass'] else 'FAIL'} (risk +{results['dkim']['risk_contribution']})")
        print(f"  DMARC:        {'PASS' if results['dmarc']['pass'] else 'FAIL'} (risk +{results['dmarc']['risk_contribution']})")
        print(f"  Return-Path:  {'MISMATCH' if results['return_path_mismatch']['mismatch'] else 'OK'} (risk +{results['return_path_mismatch']['risk_contribution']})")
        print(f"  Reply-To:     {'MISMATCH' if results['reply_to_mismatch']['mismatch'] else 'OK'} (risk +{results['reply_to_mismatch']['risk_contribution']})")
        print(f"  Received:     {results['received_chain']['hop_count']} hops, IP: {results['received_chain']['originating_ip'] or 'N/A'}")

        if results["spf"]["raw"]:
            print(f"  SPF detail:   {results['spf']['raw'][:80]}")
        if results["dkim"]["raw"]:
            print(f"  DKIM detail:  {results['dkim']['raw'][:80]}")
        if results["dmarc"]["raw"]:
            print(f"  DMARC detail: {results['dmarc']['raw'][:80]}")

        print()

    client.disconnect()
    print("Test completato.")


if __name__ == "__main__":
    main()
