r"""
Test 4.7 - EmailPreprocessor con email HTML complesse, thread citati e solo testo.
Uso: .\venv\Scripts\python -m tests.test_preprocessor
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.content.preprocessor import EmailPreprocessor


def main():
    preprocessor = EmailPreprocessor()

    print("=" * 70)
    print("TEST EMAIL PREPROCESSOR")
    print("=" * 70)

    # Test 1: HTML complesso con script, style, immagini
    print("\n[1] HTML complesso (script + style + immagini)")
    html_email = {
        "body_html": """
        <html>
        <head><title>Email</title><meta charset="utf-8"></head>
        <style>body { font-family: Arial; } .footer { color: gray; }</style>
        <script>alert('xss')</script>
        <body>
            <div style="padding: 20px;">
                <h1>Oggetto importante</h1>
                <p>Gentile <b>Mario Rossi</b>,</p>
                <p>le confermiamo la ricezione del suo ordine <a href="http://example.com/order/123">#12345</a>.</p>
                <p>Dettagli:</p>
                <ul>
                    <li>Prodotto A - 100 EUR</li>
                    <li>Prodotto B - 50 EUR</li>
                </ul>
                <p>Totale: <strong>150 EUR</strong></p>
                <img src="logo.png" alt="Logo">
                <div class="footer">
                    <p>Questo messaggio e' generato automaticamente.</p>
                </div>
            </div>
        </body>
        </html>
        """,
        "body_text": None,
    }
    result = preprocessor.process(html_email)
    print(f"  Output ({len(result)} chars):")
    print(f"  ---")
    for line in result.split("\n")[:10]:
        print(f"    {line}")
    print(f"  ---")
    assert "alert" not in result, "Script non rimosso!"
    assert "font-family" not in result, "Style non rimosso!"
    assert "Mario Rossi" in result, "Testo non estratto!"
    assert "150 EUR" in result, "Contenuto perso!"
    print("  PASS: HTML strippato correttamente")

    # Test 2: Email con thread citato (On ... wrote:)
    print("\n[2] Email con thread citato (On ... wrote:)")
    quoted_email = {
        "body_html": None,
        "body_text": """Ciao Marco,

confermo la disponibilita per il meeting di domani alle 15:00.
Porto io il materiale aggiornato.

Grazie,
Luca

On Mon, Jun 23, 2026 at 10:15 AM Marco Bianchi <marco@azienda.it> wrote:
> Ciao Luca,
> sei disponibile domani per un meeting?
> Dovremmo discutere del progetto X.
>
> Saluti,
> Marco
""",
    }
    result = preprocessor.process(quoted_email)
    print(f"  Output ({len(result)} chars):")
    print(f"  ---")
    for line in result.split("\n"):
        print(f"    {line}")
    print(f"  ---")
    assert "confermo la disponibilita" in result, "Contenuto originale perso!"
    assert "sei disponibile domani" not in result, "Citazione non rimossa!"
    assert "Marco Bianchi" not in result, "Header citazione non rimosso!"
    print("  PASS: Testo citato rimosso correttamente")

    # Test 3: Email con --- Original Message ---
    print("\n[3] Email con --- Original Message ---")
    original_msg_email = {
        "body_html": None,
        "body_text": """Ricevuto, grazie della conferma.

Procediamo come concordato.

--- Original Message ---
From: supplier@company.com
To: buyer@azienda.it
Subject: Re: Ordine 456

Confermo la spedizione per venerdi.
Cordiali saluti,
Il Fornitore
""",
    }
    result = preprocessor.process(original_msg_email)
    print(f"  Output ({len(result)} chars):")
    print(f"  ---")
    for line in result.split("\n"):
        print(f"    {line}")
    print(f"  ---")
    assert "Procediamo come concordato" in result
    assert "Confermo la spedizione" not in result, "Original Message non rimosso!"
    print("  PASS: Original Message rimosso")

    # Test 4: Email italiana con "Il ... ha scritto:"
    print("\n[4] Email con 'Il ... ha scritto:' (formato italiano)")
    italian_quote = {
        "body_html": None,
        "body_text": """Perfetto, confermo tutto.

A domani,
Giuseppe

Il giorno lun 23 giu 2026 alle ore 09:30 Anna Verdi <anna@test.it> ha scritto:
> Ciao Giuseppe,
> ti confermo l'appuntamento di domani.
> Anna
""",
    }
    result = preprocessor.process(italian_quote)
    print(f"  Output ({len(result)} chars):")
    print(f"  ---")
    for line in result.split("\n"):
        print(f"    {line}")
    print(f"  ---")
    assert "confermo tutto" in result
    assert "ti confermo l'appuntamento" not in result
    print("  PASS: Citazione italiana rimossa")

    # Test 5: Email solo testo semplice (nessuna citazione)
    print("\n[5] Email solo testo (nessuna citazione)")
    plain_email = {
        "body_html": None,
        "body_text": """Buongiorno,

in allegato trova il preventivo richiesto.
Resto a disposizione per qualsiasi chiarimento.

Cordiali saluti,
Marco Neri
Tel: +39 02 1234567
""",
    }
    result = preprocessor.process(plain_email)
    print(f"  Output ({len(result)} chars):")
    print(f"  ---")
    for line in result.split("\n"):
        print(f"    {line}")
    print(f"  ---")
    assert "preventivo richiesto" in result
    assert "Marco Neri" in result
    print("  PASS: Testo semplice mantenuto intatto")

    # Test 6: Email con whitespace eccessivo
    print("\n[6] Normalizzazione whitespace")
    messy_email = {
        "body_html": None,
        "body_text": "Ciao,\n\n\n\n\ncome    stai?\n\n\n\nSpero   bene.\n\n\t\tA presto",
    }
    result = preprocessor.process(messy_email)
    print(f"  Output: '{result}'")
    assert "\n\n\n" not in result, "Troppe righe vuote!"
    assert "come stai?" in result, "Spazi non normalizzati!"
    assert "Spero bene." in result
    print("  PASS: Whitespace normalizzato")

    # Test 7: Email reali dall'INBOX
    print(f"\n{'='*70}")
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
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
        }

        result = preprocessor.process(email_data)

        print(f"\n  Email #{i}: {parsed['subject'][:50]}")
        print(f"    Input HTML: {len(email_data['body_html'] or '')} chars")
        print(f"    Input Text: {len(email_data['body_text'] or '')} chars")
        print(f"    Output:     {len(result)} chars")
        # Mostra prime 3 righe
        preview = result[:200].split("\n")[:3]
        for line in preview:
            print(f"    | {line[:70]}")

    client.disconnect()

    print(f"\n{'='*70}")
    print("TUTTI I TEST SUPERATI")
    print("=" * 70)


if __name__ == "__main__":
    main()
