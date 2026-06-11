r"""
Test 3.6/3.9/3.12/3.17 - CountryDetector end-to-end.
Testa TLD detection, phone prefix, language detection e integrazione completa.
Uso: .\venv\Scripts\python -m tests.test_country_detector
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.country.detector import CountryDetector


def test_tld_detection(detector):
    """Test 3.6 - TLD detection con 10+ email di paesi diversi."""
    print("=" * 70)
    print("TEST TLD DETECTION")
    print("=" * 70)

    test_cases = [
        ("Mario Rossi <mario@azienda.it>", "Italy", "IT"),
        ("Jean Dupont <jean@societe.fr>", "France", "FR"),
        ("Hans Mueller <hans@firma.de>", "Germany", "DE"),
        ("Carlos Lopez <carlos@empresa.es>", "Spain", "ES"),
        ("John Smith <john@company.co.uk>", "United Kingdom", "GB"),
        ("Kenji Tanaka <kenji@kaisha.jp>", "Japan", "JP"),
        ("Chen Wei <chen@gongsi.cn>", "China", "CN"),
        ("Ana Silva <ana@empresa.com.br>", "Brazil", "BR"),
        ("Jan Kowalski <jan@firma.pl>", "Poland", "PL"),
        ("Ivan Petrov <ivan@kompaniya.ru>", "Russia", "RU"),
        ("Ahmed Hassan <ahmed@company.eg>", "Egypt", "EG"),
        ("Ravi Kumar <ravi@company.co.in>", "India", "IN"),
    ]

    passed = 0
    for from_field, expected_country, expected_code in test_cases:
        signal = detector._detect_from_tld(from_field)
        if signal:
            ok = signal["country_code"] == expected_code
            status = "OK" if ok else "FAIL"
            if ok:
                passed += 1
            print(f"  [{status}] {from_field[:40]:40s} -> {signal['country']} ({signal['country_code']})")
        else:
            print(f"  [FAIL] {from_field[:40]:40s} -> No signal")

    print(f"\n  Risultato: {passed}/{len(test_cases)} test superati\n")
    return passed == len(test_cases)


def test_phone_detection(detector):
    """Test 3.9 - Phone prefix detection con firme internazionali."""
    print("=" * 70)
    print("TEST PHONE PREFIX DETECTION")
    print("=" * 70)

    test_cases = [
        ("Cordiali saluti\nMario Rossi\nTel: +39 02 1234567", "Italy", "IT"),
        ("Best regards\nJohn\nPhone: +44 20 7946 0958", "United Kingdom", "GB"),
        ("Cordialement\nJean\nTel: +33 1 23 45 67 89", "France", "FR"),
        ("Mit freundlichen Gruessen\nHans\nTel: +49 30 12345678", "Germany", "DE"),
        ("Saludos\nCarlos\nTel: +34 91 123 4567", "Spain", "ES"),
        ("Contact: +1 212 555 0123\nNew York Office", "United States", "US"),
        ("Tel: +81 3 1234 5678\nTokyo", "Japan", "JP"),
        ("Contato: +55 11 91234-5678\nSao Paulo", "Brazil", "BR"),
    ]

    passed = 0
    for body_text, expected_country, expected_code in test_cases:
        signal = detector._detect_from_phone(body_text)
        if signal:
            ok = signal["country_code"] == expected_code
            status = "OK" if ok else "FAIL"
            if ok:
                passed += 1
            print(f"  [{status}] +{signal['detail'].split('+')[1]:5s} -> {signal['country']} ({signal['country_code']})")
        else:
            print(f"  [FAIL] Body: {body_text[:30]:30s}... -> No signal")

    print(f"\n  Risultato: {passed}/{len(test_cases)} test superati\n")
    return passed == len(test_cases)


def test_language_detection(detector):
    """Test 3.12 - Language detection con testi in 5+ lingue."""
    print("=" * 70)
    print("TEST LANGUAGE DETECTION")
    print("=" * 70)

    test_cases = [
        (
            "Gentile cliente, le confermiamo la ricezione della sua richiesta. "
            "Il nostro team si occupera di gestire la pratica nel piu breve tempo possibile.",
            "Italy", "IT",
        ),
        (
            "Dear customer, we confirm receipt of your request. "
            "Our team will process your application as soon as possible.",
            "United Kingdom", "GB",
        ),
        (
            "Cher client, nous confirmons la reception de votre demande. "
            "Notre equipe traitera votre dossier dans les meilleurs delais.",
            "France", "FR",
        ),
        (
            "Sehr geehrter Kunde, wir bestaetigen den Eingang Ihrer Anfrage. "
            "Unser Team wird sich so schnell wie moeglich um Ihr Anliegen kuemmern.",
            "Germany", "DE",
        ),
        (
            "Estimado cliente, confirmamos la recepcion de su solicitud. "
            "Nuestro equipo se encargara de gestionar su caso lo antes posible.",
            "Spain", "ES",
        ),
    ]

    passed = 0
    for body_text, expected_country, expected_code in test_cases:
        signal = detector._detect_language(body_text)
        if signal:
            ok = signal["country_code"] == expected_code
            status = "OK" if ok else f"FAIL (got {signal['country_code']})"
            if signal["country_code"] == expected_code:
                passed += 1
            print(f"  [{status}] {signal['detail']:25s} -> {signal['country']}")
        else:
            print(f"  [FAIL] Text: {body_text[:30]:30s}... -> No signal")

    print(f"\n  Risultato: {passed}/{len(test_cases)} test superati\n")
    return passed == len(test_cases)


def test_full_detection(detector):
    """Test 3.17 - Detection end-to-end con segnali combinati."""
    print("=" * 70)
    print("TEST FULL COUNTRY DETECTION (segnali combinati)")
    print("=" * 70)

    test_emails = [
        {
            "name": "Email italiana (TLD + lingua + telefono)",
            "from": "Mario Rossi <m.rossi@azienda.it>",
            "headers": {"Received": "from mail.azienda.it [93.63.49.10] by mx.google.com"},
            "body_text": (
                "Gentile cliente,\nle confermiamo la ricezione della sua richiesta.\n\n"
                "Cordiali saluti,\nMario Rossi\nTel: +39 02 12345678"
            ),
            "expected_country": "Italy",
            "expected_code": "IT",
        },
        {
            "name": "Email francese (TLD + lingua)",
            "from": "Jean Dupont <jean@entreprise.fr>",
            "headers": {},
            "body_text": (
                "Cher monsieur,\nnous avons bien recu votre demande et nous vous en remercions.\n\n"
                "Cordialement,\nJean Dupont\nTel: +33 1 45 67 89 00"
            ),
            "expected_country": "France",
            "expected_code": "FR",
        },
        {
            "name": "Email tedesca (TLD + lingua)",
            "from": "Hans Mueller <hans@unternehmen.de>",
            "headers": {},
            "body_text": (
                "Sehr geehrter Herr,\nwir bestaetigen den Eingang Ihrer Anfrage.\n\n"
                "Mit freundlichen Gruessen,\nHans Mueller\nTelefon: +49 89 123456"
            ),
            "expected_country": "Germany",
            "expected_code": "DE",
        },
        {
            "name": "Email UK (TLD co.uk + lingua EN)",
            "from": "John Smith <john@company.co.uk>",
            "headers": {},
            "body_text": (
                "Dear Sir,\nThank you for your enquiry. We will get back to you shortly.\n\n"
                "Kind regards,\nJohn Smith\nTel: +44 20 7946 0123"
            ),
            "expected_country": "United Kingdom",
            "expected_code": "GB",
        },
        {
            "name": "Email spagnola (TLD + lingua + telefono)",
            "from": "Carlos Garcia <carlos@empresa.es>",
            "headers": {},
            "body_text": (
                "Estimado cliente,\nconfirmamos la recepcion de su pedido.\n\n"
                "Atentamente,\nCarlos Garcia\nTel: +34 91 234 5678"
            ),
            "expected_country": "Spain",
            "expected_code": "ES",
        },
    ]

    passed = 0
    for email in test_emails:
        result = detector.detect(email)
        ok = result["country_code"] == email["expected_code"]
        status = "OK" if ok else "FAIL"
        if ok:
            passed += 1

        print(f"\n  [{status}] {email['name']}")
        print(f"       Country:    {result['country']} ({result['country_code']})")
        print(f"       Confidence: {result['confidence']}")
        print(f"       Method:     {result['detection_method']}")
        print(f"       Signals:    {len(result['signals'])}")
        for s in result["signals"]:
            print(f"         - {s['method']}: {s['detail']}")

    print(f"\n  Risultato: {passed}/{len(test_emails)} test superati\n")
    return passed == len(test_emails)


def test_real_emails(detector):
    """Test con email reali dall'INBOX."""
    print("=" * 70)
    print("TEST CON EMAIL REALI (ultime 3)")
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
            "from": parsed.get("from", ""),
            "headers": parsed.get("headers", {}),
            "body_text": parsed.get("body_text", "") or "",
        }

        result = detector.detect(email_data)

        print(f"\n  Email #{i}: {parsed['subject'][:50]}")
        print(f"    From:       {parsed['from'][:50]}")
        print(f"    Country:    {result['country']} ({result['country_code']})")
        print(f"    Confidence: {result['confidence']}")
        print(f"    Method:     {result['detection_method']}")
        for s in result["signals"]:
            print(f"      - {s['method']}: {s['detail']}")

    client.disconnect()


def main():
    detector = CountryDetector()

    tld_ok = test_tld_detection(detector)
    phone_ok = test_phone_detection(detector)
    lang_ok = test_language_detection(detector)
    full_ok = test_full_detection(detector)
    test_real_emails(detector)

    print("\n" + "=" * 70)
    print("RIEPILOGO FINALE")
    print(f"  TLD Detection:      {'PASS' if tld_ok else 'FAIL'}")
    print(f"  Phone Detection:    {'PASS' if phone_ok else 'FAIL'}")
    print(f"  Language Detection:  {'PASS' if lang_ok else 'FAIL'}")
    print(f"  Full Detection:     {'PASS' if full_ok else 'FAIL'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
