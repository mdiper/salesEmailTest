"""
Test 2.18 - PhishingDetector con email di phishing simulate + email reali.
Uso: .\venv\Scripts\python -m tests.test_phishing_detector
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.security.phishing_detector import PhishingDetector
from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser


def test_simulated_phishing():
    """Test con email di phishing simulate."""
    detector = PhishingDetector()

    print("=" * 70)
    print("TEST PHISHING SIMULATI")
    print("=" * 70)

    # Caso 1: phishing classico PayPal
    result = detector.analyze({
        "from": "PayPal Security <alert-noreply@secure-paypal.evil.xyz>",
        "body_text": "Your account has been suspended. Click immediately to verify your credentials. https://192.168.1.1/login/paypal",
        "body_html": '<a href="https://192.168.1.1/login/paypal">Verify now</a>',
    })
    print(f"\n[1] Phishing PayPal classico")
    print(f"    Score: {result['phishing_score']}/100")
    print(f"    URL risk: {result['url_risk']}, Pattern: {result['pattern_risk']}, Spoof: {result['display_name_spoof']}")
    print(f"    Patterns: {result['details']['patterns_matched'][:2]}")

    # Caso 2: URL shortener + urgenza
    result = detector.analyze({
        "from": "Support <support@legitimate.com>",
        "body_text": "Congratulations! You won the lottery! Act immediately: https://bit.ly/abc123",
        "body_html": '<a href="https://bit.ly/abc123">Claim prize</a>',
    })
    print(f"\n[2] URL shortener + urgenza")
    print(f"    Score: {result['phishing_score']}/100")
    print(f"    URL risk: {result['url_risk']}, Pattern: {result['pattern_risk']}")

    # Caso 3: homoglyph attack (Cyrillic 'a' in 'apple')
    result = detector.analyze({
        "from": "\u0430pple Support <security@icloud-verify.com>",
        "body_text": "Confirm your Apple ID. Your account will be locked within 24 hours.",
        "body_html": "",
    })
    print(f"\n[3] Homoglyph attack (Cyrillic 'a' in apple)")
    print(f"    Score: {result['phishing_score']}/100")
    print(f"    Homoglyph: {result['homoglyph_detected']}, Pattern: {result['pattern_risk']}")

    # Caso 4: email legittima (nessun rischio)
    result = detector.analyze({
        "from": "Mario Rossi <mario.rossi@azienda.it>",
        "body_text": "Ciao, ti invio il report mensile come da accordi. A presto.",
        "body_html": "",
    })
    print(f"\n[4] Email legittima (attesa: score basso)")
    print(f"    Score: {result['phishing_score']}/100")
    print(f"    URL risk: {result['url_risk']}, Pattern: {result['pattern_risk']}")

    # Caso 5: subdomain eccessivi + punycode
    result = detector.analyze({
        "from": "Amazon <orders@amazon.com>",
        "body_text": "Your order has shipped",
        "body_html": '<a href="https://login.amazon.com.secure.verify.xn--80ak6aa.evil.ru/signin">Track order</a>',
    })
    print(f"\n[5] Subdomain eccessivi + punycode")
    print(f"    Score: {result['phishing_score']}/100")
    print(f"    URL risk: {result['url_risk']}, URLs: {result['details']['urls_analyzed']}")


def test_real_emails():
    """Test con email reali dalla mailbox."""
    detector = PhishingDetector()
    client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()

    client.connect()
    status, messages = client._connection.select("INBOX")
    total = int(messages[0])

    print(f"\n\n{'='*70}")
    print(f"TEST CON EMAIL REALI (ultime 5)")
    print(f"{'='*70}")

    start = max(1, total - 4)
    for i in range(start, total + 1):
        status, data = client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)
        result = detector.analyze(parsed)

        score = result["phishing_score"]
        bar = "#" * (score // 5) + "." * (20 - score // 5)

        print(f"\n  #{i} {parsed['subject'][:45]}")
        print(f"       From: {parsed['from'][:50]}")
        print(f"       Score: [{bar}] {score}/100")
        print(f"       URLs: {result['urls_found']}, Patterns: {result['pattern_risk']}, Spoof: {result['display_name_spoof']}")

    client.disconnect()


def main():
    test_simulated_phishing()
    test_real_emails()
    print(f"\n\nTest completato.")


if __name__ == "__main__":
    main()
