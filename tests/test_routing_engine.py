r"""
Test Fase 5 - Routing Engine end-to-end con email reali.
Esegue la pipeline completa: Security + Country + Content + Routing su email reali.
Uso: .\venv\Scripts\python -m tests.test_routing_engine
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.security.engine import SecurityEngine
from src.country.detector import CountryDetector
from src.content.analyzer import ContentAnalyzer
from src.routing.engine import RoutingEngine
from src.routing.action_executor import ActionExecutor


def main():
    # Inizializza componenti
    client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()
    security_engine = SecurityEngine()
    country_detector = CountryDetector()
    content_analyzer = ContentAnalyzer()
    routing_engine = RoutingEngine()
    action_executor = ActionExecutor()

    client.connect()

    status, messages = client._connection.select("INBOX")
    total = int(messages[0])

    print("=" * 70)
    print("TEST ROUTING ENGINE - EMAIL REALI (pipeline completa)")
    print("=" * 70)
    print(f"Totale email in INBOX: {total}")
    print(f"Analisi ultime 5 email...\n")

    start = max(1, total - 4)
    for i in range(start, total + 1):
        status, data = client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)

        # 1. Security Analysis
        security_data = {
            "headers": parsed.get("headers", {}),
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
            "from": parsed.get("from", ""),
            "attachments": parsed.get("attachments", []),
        }
        security_result = security_engine.analyze_email(security_data, save_to_db=False)

        # 2. Country Detection
        country_data = {
            "from": parsed.get("from", ""),
            "headers": parsed.get("headers", {}),
            "body_text": parsed.get("body_text", ""),
        }
        country_result = country_detector.detect(country_data)

        # 3. Content Analysis
        content_data = {
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
        }
        content_result = content_analyzer.analyze(content_data, save_to_db=False)

        # 4. Costruisci contesto per routing
        email_context = {
            "security": {
                "verdict": security_result.verdict,
                "risk_score": security_result.risk_score,
                "flags": security_result.flags,
            },
            "country": {
                "country": country_result.get("country"),
                "country_code": country_result.get("country_code"),
                "confidence": country_result.get("confidence"),
            },
            "content": {
                "category": content_result.get("category"),
                "category_confidence": content_result.get("category_confidence"),
            },
            "email": {
                "from": parsed.get("from", ""),
                "subject": parsed.get("subject", ""),
                "has_attachments": len(parsed.get("attachments", [])) > 0,
            },
        }

        # 5. Routing Evaluation
        actions = routing_engine.evaluate(email_context)

        # Output
        print(f"{'='*70}")
        print(f"EMAIL #{i}: {parsed['subject'][:55]}")
        print(f"  From: {parsed['from'][:55]}")
        print(f"  {'-'*66}")
        print(f"  Security:  {security_result.verdict} (score {security_result.risk_score})")
        print(f"  Country:   {country_result.get('country')} ({country_result.get('country_code')})")
        print(f"  Content:   {content_result.get('category')} (conf {content_result.get('category_confidence')})")
        print(f"  {'-'*66}")

        if actions:
            print(f"  AZIONI ROUTING ({len(actions)}):")
            for a in actions:
                print(f"    -> [{a['action_type'].upper()}] rule: {a['rule_name']} | params: {a.get('params', {})}")
        else:
            print(f"  AZIONI ROUTING: nessuna (email passa senza intervento)")

        if security_result.flags:
            print(f"  Flags: {', '.join(security_result.flags[:5])}")

        print()

    client.disconnect()

    # Mostra regole attive
    print(f"{'='*70}")
    print("REGOLE ATTIVE NEL SISTEMA")
    print(f"{'='*70}")
    rules = routing_engine._get_rules()
    for rule in rules:
        conditions_summary = " & ".join(
            f"{c['field']} {c['operator']} {c['value']}" for c in rule["conditions"]
        )
        actions_summary = ", ".join(a["type"] for a in rule["actions"])
        stop = " [STOP]" if rule.get("stop_processing") else ""
        print(f"  P{rule['priority']} | {rule['name']}")
        print(f"       IF: {conditions_summary}")
        print(f"       THEN: {actions_summary}{stop}")
        print()

    print(f"{'='*70}")
    print("Test completato.")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
