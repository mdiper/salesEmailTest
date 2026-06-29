r"""
Test 6.5 - EmailPipeline end-to-end con email reali.
Esegue la pipeline completa sulle ultime email dall'INBOX.
Uso: .\venv\Scripts\python -m tests.test_pipeline
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.pipeline import EmailPipeline


def main():
    imap_client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()
    pipeline = EmailPipeline()

    imap_client.connect()

    status, messages = imap_client._connection.select("INBOX")
    total = int(messages[0])

    print("=" * 70)
    print("TEST PIPELINE COMPLETA - EMAIL REALI")
    print("=" * 70)
    print(f"Totale email in INBOX: {total}")
    print(f"Analisi ultime 5 email (senza salvataggio DB)...\n")

    start = max(1, total - 4)
    for i in range(start, total + 1):
        status, data = imap_client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)

        # Simula pipeline senza DB (email_id fittizio, save_to_db disabilitato)
        result = _run_pipeline_dry(pipeline, parsed)

        print(f"{'='*70}")
        print(f"EMAIL #{i}: {parsed['subject'][:55]}")
        print(f"  From: {parsed['from'][:55]}")
        print(f"  {'-'*66}")

        # Security
        sec = result.get("security", {})
        print(f"  [Security]  {sec.get('verdict', '?')} (score {sec.get('risk_score', '?')})")
        if sec.get("flags"):
            print(f"              Flags: {', '.join(sec['flags'][:5])}")

        # Country
        country = result.get("country", {})
        if country.get("skipped"):
            print(f"  [Country]   SKIPPED ({country.get('reason')})")
        elif country.get("error"):
            print(f"  [Country]   ERROR: {country['error']}")
        else:
            print(f"  [Country]   {country.get('country', '?')} ({country.get('country_code', '?')}) conf={country.get('confidence', '?')}")

        # Content
        content = result.get("content", {})
        if content.get("skipped"):
            print(f"  [Content]   SKIPPED ({content.get('reason')})")
        elif content.get("error"):
            print(f"  [Content]   ERROR: {content['error']}")
        else:
            print(f"  [Content]   {content.get('category', '?')} (conf {content.get('category_confidence', '?')})")
            if content.get("summary"):
                print(f"              Summary: {content['summary'][:70]}...")

        # Routing
        actions = result.get("routing_actions", [])
        if actions:
            print(f"  [Routing]   {len(actions)} azioni:")
            for a in actions:
                print(f"              -> {a.get('action_type', '?').upper()} (rule: {a.get('rule_name', '?')})")
        else:
            print(f"  [Routing]   Nessuna azione (email passa)")

        print(f"  [Status]    {result.get('status', '?')}")
        print()

    imap_client.disconnect()

    print(f"{'='*70}")
    print("Test pipeline completato.")
    print(f"{'='*70}")


def _run_pipeline_dry(pipeline: EmailPipeline, parsed: dict) -> dict:
    """Esegue la pipeline senza salvare in DB (simula email_id=0)."""
    from src.security.engine import SecurityEngine
    from src.country.detector import CountryDetector
    from src.content.analyzer import ContentAnalyzer
    from src.routing.engine import RoutingEngine

    result = {
        "security": None,
        "country": None,
        "content": None,
        "routing_actions": [],
        "status": "completed",
    }

    # Security
    security_data = {
        "headers": parsed.get("headers", {}),
        "body_html": parsed.get("body_html"),
        "body_text": parsed.get("body_text"),
        "from": parsed.get("from", ""),
        "attachments": parsed.get("attachments", []),
    }
    security_result = pipeline.security_engine.analyze_email(security_data, save_to_db=False)
    result["security"] = {
        "verdict": security_result.verdict,
        "risk_score": security_result.risk_score,
        "flags": security_result.flags,
    }

    # Fast-track
    if security_result.verdict == "DANGEROUS":
        result["country"] = {"skipped": True, "reason": "fast-track DANGEROUS"}
        result["content"] = {"skipped": True, "reason": "fast-track DANGEROUS"}
    else:
        # Country
        country_data = {
            "from": parsed.get("from", ""),
            "headers": parsed.get("headers", {}),
            "body_text": parsed.get("body_text", ""),
        }
        result["country"] = pipeline.country_detector.detect(country_data)

        # Content
        content_data = {
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
        }
        content_result = pipeline.content_analyzer.analyze(content_data, save_to_db=False)
        result["content"] = {
            "category": content_result.get("category"),
            "category_confidence": content_result.get("category_confidence"),
            "summary": content_result.get("summary", "")[:200],
        }

    # Routing
    email_context = {
        "security": result["security"] or {},
        "country": result["country"] if not result["country"].get("skipped") else {},
        "content": result["content"] if not result["content"].get("skipped") else {},
        "email": {
            "from": parsed.get("from", ""),
            "subject": parsed.get("subject", ""),
            "has_attachments": len(parsed.get("attachments", [])) > 0,
        },
    }
    result["routing_actions"] = pipeline.routing_engine.evaluate(email_context)

    return result


if __name__ == "__main__":
    main()
