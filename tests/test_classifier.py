r"""
Test 4.11/4.17 - ContentClassifier rule-based e ibrido.
Testa almeno 2 email per ogni categoria.
Uso: .\venv\Scripts\python -m tests.test_classifier
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.content.classifier import ContentClassifier
from src.content.preprocessor import EmailPreprocessor


def main():
    classifier = ContentClassifier()
    preprocessor = EmailPreprocessor()

    print("=" * 70)
    print("TEST CONTENT CLASSIFIER (rule-based)")
    print("=" * 70)

    test_cases = [
        # INVOICE
        (
            "invoice_1",
            "invoice",
            "Gentile cliente, in allegato trova la fattura n. 2024/1234 "
            "per un importo totale di 1.500,00 EUR. La scadenza del pagamento "
            "e' fissata al 30/07/2026. Coordinate bancarie: IBAN IT12345.",
        ),
        (
            "invoice_2",
            "invoice",
            "Please find attached invoice number INV-5678 for the amount due "
            "of $3,200.00. Payment is expected within 30 days via bank transfer.",
        ),
        # MARKETING
        (
            "marketing_1",
            "marketing",
            "Offerta speciale! Sconto esclusivo del 30% su tutti i prodotti. "
            "Non perdere questa promozione limitata! Approfitta subito. "
            "Per disiscriviti dalla newsletter clicca qui.",
        ),
        (
            "marketing_2",
            "marketing",
            "Exclusive deal: 50% off all premium plans! Limited time offer. "
            "Free trial available. Unsubscribe from this mailing list anytime.",
        ),
        # SPAM
        (
            "spam_1",
            "spam",
            "Congratulations! You have won 5 million dollars in our lottery! "
            "Click here now to claim your prize immediately before it expires!",
        ),
        (
            "spam_2",
            "spam",
            "Nigerian prince needs your help to transfer 10 million USD. "
            "Act now! This inheritance is waiting for you. Make money fast!",
        ),
        # SUPPORT
        (
            "support_1",
            "support",
            "Ticket #45678: il problema segnalato e' stato risolto. "
            "L'errore nel sistema e' stato corretto con priorita' alta. "
            "Caso chiuso.",
        ),
        (
            "support_2",
            "support",
            "Case #12345 update: the issue has been resolved and the fix "
            "deployed. Please verify the bug is no longer present. "
            "Contact support if the problem persists.",
        ),
        # LEGAL
        (
            "legal_1",
            "legal",
            "In allegato il contratto per la sottoscrizione del servizio. "
            "Le clausole sono state riviste dall'avvocato. "
            "Prego apporre firma digitale entro il 15/07.",
        ),
        (
            "legal_2",
            "legal",
            "Informativa GDPR: il trattamento dei dati personali e' regolato "
            "dalla normativa vigente. In caso di controversia, il tribunale "
            "competente e' quello di Milano.",
        ),
        # HR
        (
            "hr_1",
            "hr",
            "Gentile candidato, la sua candidatura per la posizione aperta "
            "e' stata valutata positivamente. La invitiamo a un colloquio "
            "il giorno 10/07 per la selezione finale.",
        ),
        (
            "hr_2",
            "hr",
            "Comunicazione ferie: le ricordiamo che le richieste di permesso "
            "devono essere inoltrate almeno 15 giorni prima. "
            "Il payroll di luglio include il conguaglio retribuzione.",
        ),
        # SALES
        (
            "sales_1",
            "sales",
            "In allegato il preventivo richiesto per la fornitura. "
            "Ordine n. 2024-789. La consegna e' prevista entro 15 giorni. "
            "Disponibilita confermata a magazzino.",
        ),
        (
            "sales_2",
            "sales",
            "Offerta commerciale per il cliente Rossi SpA. "
            "Listino aggiornato con campioni gratuiti. "
            "Trattativa in corso, spedizione express possibile.",
        ),
        # PERSONAL
        (
            "personal_1",
            "personal",
            "Ciao! Come stai? Non ci vediamo da un po'. "
            "Ti va un aperitivo venerdi? Ci vediamo al solito posto!",
        ),
        (
            "personal_2",
            "personal",
            "Buon compleanno! Ti faccio i miei piu sinceri auguri. "
            "Spero tu stia passando una bella giornata. A presto!",
        ),
    ]

    results_by_category: dict[str, list] = {}
    total_correct = 0

    for name, expected, text in test_cases:
        result = classifier.classify(text)
        correct = result["category"] == expected
        if correct:
            total_correct += 1

        status = "OK" if correct else f"FAIL (got: {result['category']})"

        if expected not in results_by_category:
            results_by_category[expected] = []
        results_by_category[expected].append((name, correct, result))

        print(f"\n  [{status}] {name}")
        print(f"    Category:   {result['category']} (expected: {expected})")
        print(f"    Confidence: {result['confidence']}")
        print(f"    Method:     {result['method']}")

    # Riepilogo per categoria
    print(f"\n{'='*70}")
    print("RIEPILOGO PER CATEGORIA")
    print(f"{'='*70}")
    for cat, items in sorted(results_by_category.items()):
        correct = sum(1 for _, c, _ in items if c)
        print(f"  {cat:12s}: {correct}/{len(items)}")

    print(f"\n  TOTALE: {total_correct}/{len(test_cases)} test superati")

    # Test con email reali
    print(f"\n{'='*70}")
    print("TEST CON EMAIL REALI (ultime 3)")
    print(f"{'='*70}")

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

        clean_text = preprocessor.process(email_data)
        result = classifier.classify(clean_text)

        print(f"\n  Email #{i}: {parsed['subject'][:50]}")
        print(f"    Category:   {result['category']}")
        print(f"    Confidence: {result['confidence']}")
        print(f"    Method:     {result['method']}")
        # Top 3 scores
        top_scores = sorted(result["scores"].items(), key=lambda x: x[1], reverse=True)[:3]
        print(f"    Top scores: {', '.join(f'{k}={v}' for k, v in top_scores)}")

    client.disconnect()

    print(f"\n{'='*70}")
    print(f"Test completato. Accuracy: {total_correct}/{len(test_cases)}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
