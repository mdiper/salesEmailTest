r"""
Test 5.27 - CRUD regole di routing via API + dry-run.
Avvia l'API, testa CRUD, poi esegue dry-run con contesto email reali.
Uso: .\venv\Scripts\python -m tests.test_routing_api
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.api.app import app
from src.utils.config import config
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.security.engine import SecurityEngine
from src.country.detector import CountryDetector
from src.content.analyzer import ContentAnalyzer


def main():
    client = TestClient(app)

    print("=" * 70)
    print("TEST API ROUTING RULES (CRUD + dry-run)")
    print("=" * 70)

    # 1. GET lista regole
    print("\n[1] GET /api/routing-rules")
    resp = client.get("/api/routing-rules")
    assert resp.status_code == 200
    rules = resp.json()
    print(f"    Status: {resp.status_code}")
    print(f"    Regole trovate: {rules['count']}")
    for r in rules["rules"]:
        print(f"      [{r['id']}] P{r['priority']} - {r['name']} (enabled: {r['enabled']})")

    # 2. GET singola regola
    print("\n[2] GET /api/routing-rules/1")
    resp = client.get("/api/routing-rules/1")
    assert resp.status_code == 200
    rule = resp.json()
    print(f"    Status: {resp.status_code}")
    print(f"    Nome: {rule['name']}")
    print(f"    Conditions: {rule['conditions']}")

    # 3. GET regola inesistente
    print("\n[3] GET /api/routing-rules/999 (not found)")
    resp = client.get("/api/routing-rules/999")
    assert resp.status_code == 404
    print(f"    Status: {resp.status_code} (corretto)")

    # 4. POST crea nuova regola
    print("\n[4] POST /api/routing-rules (crea regola test)")
    new_rule = {
        "name": "Test Rule - Block from Russia",
        "priority": 5,
        "conditions": [
            {"field": "country.country_code", "operator": "eq", "value": "RU"}
        ],
        "condition_logic": "AND",
        "actions": [
            {"type": "quarantine", "params": {}},
            {"type": "tag", "params": {"tags": ["geo-blocked"]}}
        ],
        "stop_processing": False,
    }
    resp = client.post("/api/routing-rules", json=new_rule)
    assert resp.status_code == 201
    created = resp.json()
    created_id = created["id"]
    print(f"    Status: {resp.status_code}")
    print(f"    Creata regola ID: {created_id}")
    print(f"    Nome: {created['name']}")

    # 5. PUT modifica regola
    print(f"\n[5] PUT /api/routing-rules/{created_id} (modifica)")
    update_data = {
        "name": "Test Rule - Block from Russia (UPDATED)",
        "priority": 4,
        "enabled": False,
    }
    resp = client.put(f"/api/routing-rules/{created_id}", json=update_data)
    assert resp.status_code == 200
    updated = resp.json()
    print(f"    Status: {resp.status_code}")
    print(f"    Nome aggiornato: {updated['name']}")
    print(f"    Priority: {updated['priority']}")
    print(f"    Enabled: {updated['enabled']}")

    # 6. DELETE elimina regola
    print(f"\n[6] DELETE /api/routing-rules/{created_id}")
    resp = client.delete(f"/api/routing-rules/{created_id}")
    assert resp.status_code == 200
    print(f"    Status: {resp.status_code}")
    print(f"    Result: {resp.json()}")

    # Verifica eliminazione
    resp = client.get(f"/api/routing-rules/{created_id}")
    assert resp.status_code == 404
    print(f"    Verifica 404 dopo delete: OK")

    # 7. DRY-RUN con email reali
    print(f"\n{'='*70}")
    print("DRY-RUN CON EMAIL REALI (ultime 3)")
    print(f"{'='*70}")

    imap_client = IMAPClient(config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME, config.IMAP_PASSWORD)
    parser = MIMEParser()
    security_engine = SecurityEngine()
    country_detector = CountryDetector()
    content_analyzer = ContentAnalyzer()

    imap_client.connect()
    status, messages = imap_client._connection.select("INBOX")
    total = int(messages[0])

    start = max(1, total - 2)
    for i in range(start, total + 1):
        status, data = imap_client._connection.fetch(str(i).encode(), "(RFC822)")
        if status != "OK" or data[0] is None:
            continue

        raw = data[0][1]
        parsed = parser.parse(raw)

        # Analisi
        security_data = {
            "headers": parsed.get("headers", {}),
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
            "from": parsed.get("from", ""),
            "attachments": parsed.get("attachments", []),
        }
        security_result = security_engine.analyze_email(security_data, save_to_db=False)

        country_result = country_detector.detect({
            "from": parsed.get("from", ""),
            "headers": parsed.get("headers", {}),
            "body_text": parsed.get("body_text", ""),
        })

        content_result = content_analyzer.analyze({
            "body_html": parsed.get("body_html"),
            "body_text": parsed.get("body_text"),
        }, save_to_db=False)

        # Dry-run via API
        dry_run_request = {
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
            },
        }

        resp = client.post("/api/routing-rules/dry-run", json=dry_run_request)
        assert resp.status_code == 200
        result = resp.json()

        print(f"\n  Email #{i}: {parsed['subject'][:50]}")
        print(f"    Security: {security_result.verdict} (score {security_result.risk_score})")
        print(f"    Country:  {country_result.get('country')}")
        print(f"    Content:  {content_result.get('category')}")
        print(f"    Dry-run:  {result['actions_count']} azioni")
        if result["matched_actions"]:
            for a in result["matched_actions"]:
                print(f"      -> {a['action_type'].upper()} (rule: {a['rule_name']})")
        else:
            print(f"      -> nessuna azione")
        print(f"    Would block: {result['would_block']} | Would quarantine: {result['would_quarantine']}")

    imap_client.disconnect()

    print(f"\n{'='*70}")
    print("TUTTI I TEST SUPERATI")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
