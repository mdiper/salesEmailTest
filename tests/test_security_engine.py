r"""
Test 2.34 - SecurityEngine end-to-end.
Analizza le ultime email dall'INBOX con la pipeline completa:
HeaderAnalyzer + PhishingDetector + MalwareScanner + RiskScorer -> salvataggio DB.
Uso: .\venv\Scripts\python -m tests.test_security_engine
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.security.engine import SecurityEngine
from src.db.security_repository import SecurityRepository


def main():
    client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()
    engine = SecurityEngine()
    repo = SecurityRepository()

    client.connect()

    status, messages = client._connection.select("INBOX")
    total = int(messages[0])
    print(f"Totale email in INBOX: {total}")
    print(f"Analisi ultime 3 email con SecurityEngine...\n")

    start = max(1, total - 2)
    for i in range(start, total + 1):
        status, data = client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)

        email_data = {
            "headers": parsed["headers"],
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
            "from": parsed.get("from", ""),
            "attachments": parsed.get("attachments", []),
        }

        # Analisi senza salvataggio DB (non abbiamo email_id dall'IMAP diretto)
        result = engine.analyze_email(email_data, save_to_db=False)

        risk_bar = "#" * (result.risk_score // 5) + "." * (20 - result.risk_score // 5)

        print(f"{'='*70}")
        print(f"EMAIL #{i}: {parsed['subject'][:60]}")
        print(f"  From: {parsed['from'][:60]}")
        print(f"  {'-'*66}")
        print(f"  VERDICT:    {result.verdict}")
        print(f"  RISK SCORE: [{risk_bar}] {result.risk_score}/100")
        print(f"  {'-'*66}")

        scores = result.details.get("component_scores", {})
        print(f"  Components:")
        print(f"    Header:     {scores.get('header', 0):3d}/100  (peso 25%)")
        print(f"    Phishing:   {scores.get('phishing', 0):3d}/100  (peso 30%)")
        print(f"    Attachment: {scores.get('attachment', 0):3d}/100  (peso 25%)")
        print(f"    Reputation: {scores.get('reputation', 0):3d}/100  (peso 10%)")
        print(f"    Anomaly:    {scores.get('anomaly', 0):3d}/100  (peso 10%)")

        if result.flags:
            print(f"  Flags: {', '.join(result.flags)}")
        else:
            print(f"  Flags: (nessun flag attivo)")

        # Dettagli allegati
        att_count = len(parsed.get("attachments", []))
        if att_count > 0:
            print(f"  Allegati: {att_count}")
            for att in parsed.get("attachments", []):
                print(f"    - {att.get('filename', '?')} ({att.get('content_type', '?')}, {att.get('size', 0)} bytes)")

        print()

    client.disconnect()

    # Test con email simulata phishing (senza DB)
    print(f"{'='*70}")
    print("TEST SIMULATO - Email phishing con allegato .exe\n")

    fake_email = {
        "headers": {
            "Authentication-Results": "mx.test.com; spf=fail; dkim=fail; dmarc=fail",
            "From": "PayPal Security <hacker@evil-domain.xyz>",
            "Return-Path": "<bounce@different.com>",
            "Reply-To": "scammer@another.com",
            "Received": "from unknown [185.43.210.99] by mx.test.com",
        },
        "body_html": """
            <html><body>
            <p>Your account has been suspended! Click immediately to verify:</p>
            <a href="http://192.168.1.100/paypal-login/verify">Verify Account Now</a>
            <a href="https://bit.ly/3xABC123">Reset Password</a>
            </body></html>
        """,
        "body_text": "Your account has been suspended. Verify your credentials immediately.",
        "from": "PayPal Security <hacker@evil-domain.xyz>",
        "attachments": [
            {"filename": "invoice.exe", "content_type": "application/octet-stream", "size": 512, "raw_bytes": b"MZ\x90" + b"\x00" * 57 + b"PE\x00\x00"},
        ],
    }

    result = engine.analyze_email(fake_email, save_to_db=False)

    risk_bar = "#" * (result.risk_score // 5) + "." * (20 - result.risk_score // 5)
    print(f"  VERDICT:    {result.verdict}")
    print(f"  RISK SCORE: [{risk_bar}] {result.risk_score}/100")

    scores = result.details.get("component_scores", {})
    print(f"  Components:")
    print(f"    Header:     {scores.get('header', 0):3d}/100")
    print(f"    Phishing:   {scores.get('phishing', 0):3d}/100")
    print(f"    Attachment: {scores.get('attachment', 0):3d}/100")
    print(f"  Flags: {', '.join(result.flags)}")

    assert result.verdict == "DANGEROUS", f"Expected DANGEROUS, got {result.verdict}"
    assert result.risk_score >= 70, f"Expected score >= 70, got {result.risk_score}"
    print(f"\n  ASSERTION OK: phishing simulato correttamente classificato DANGEROUS")

    # Test email pulita
    print(f"\n{'='*70}")
    print("TEST SIMULATO - Email legittima\n")

    clean_email = {
        "headers": {
            "Authentication-Results": "mx.google.com; spf=pass; dkim=pass; dmarc=pass",
            "From": "Team Vianova <info@vianova.it>",
            "Return-Path": "<noreply@vianova.it>",
            "Received": "from mail.vianova.it [93.63.49.10] by mx.google.com",
        },
        "body_html": "<p>Gentile cliente, le confermiamo la ricezione della sua richiesta.</p>",
        "body_text": "Gentile cliente, le confermiamo la ricezione della sua richiesta.",
        "from": "Team Vianova <info@vianova.it>",
        "attachments": [],
    }

    result = engine.analyze_email(clean_email, save_to_db=False)

    risk_bar = "#" * (result.risk_score // 5) + "." * (20 - result.risk_score // 5)
    print(f"  VERDICT:    {result.verdict}")
    print(f"  RISK SCORE: [{risk_bar}] {result.risk_score}/100")

    scores = result.details.get("component_scores", {})
    print(f"  Components:")
    print(f"    Header:     {scores.get('header', 0):3d}/100")
    print(f"    Phishing:   {scores.get('phishing', 0):3d}/100")
    print(f"    Attachment: {scores.get('attachment', 0):3d}/100")
    if result.flags:
        print(f"  Flags: {', '.join(result.flags)}")
    else:
        print(f"  Flags: (nessuno)")

    assert result.verdict == "SAFE", f"Expected SAFE, got {result.verdict}"
    assert result.risk_score < 30, f"Expected score < 30, got {result.risk_score}"
    print(f"\n  ASSERTION OK: email legittima correttamente classificata SAFE")

    print(f"\n{'='*70}")
    print("Test SecurityEngine end-to-end completato con successo!")


if __name__ == "__main__":
    main()
