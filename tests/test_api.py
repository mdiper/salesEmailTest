"""Test completo di tutti gli endpoint API."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def get_auth_headers() -> dict:
    """Login e restituisce headers con token JWT."""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("[OK] GET /health")


def test_auth_login():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    print("[OK] POST /api/auth/login")


def test_auth_login_invalid():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    print("[OK] POST /api/auth/login (invalid credentials -> 401)")


def test_auth_me():
    headers = get_auth_headers()
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
    print("[OK] GET /api/auth/me")


def test_protected_without_token():
    resp = client.get("/api/emails")
    assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"
    print(f"[OK] GET /api/emails (no token -> {resp.status_code})")


def test_list_emails():
    headers = get_auth_headers()
    resp = client.get("/api/emails", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "emails" in data
    assert "total" in data
    assert "page" in data
    print(f"[OK] GET /api/emails -> {data['total']} emails, page {data['page']}/{data['pages']}")


def test_list_emails_pagination():
    headers = get_auth_headers()
    resp = client.get("/api/emails?page=1&per_page=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["per_page"] == 5
    assert len(data["emails"]) <= 5
    print(f"[OK] GET /api/emails?page=1&per_page=5 -> {len(data['emails'])} risultati")


def test_email_detail():
    headers = get_auth_headers()
    # Prima recupera lista per avere un ID valido
    resp = client.get("/api/emails?per_page=1", headers=headers)
    data = resp.json()
    if data["total"] == 0:
        print("[SKIP] GET /api/emails/{id} - nessuna email in DB")
        return

    email_id = data["emails"][0]["id"]
    resp = client.get(f"/api/emails/{email_id}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert "email" in detail
    assert "security" in detail
    assert "country" in detail
    assert "content" in detail
    assert "attachments" in detail
    assert "routing_logs" in detail
    print(f"[OK] GET /api/emails/{email_id} -> dettaglio completo")


def test_email_detail_not_found():
    headers = get_auth_headers()
    resp = client.get("/api/emails/99999", headers=headers)
    assert resp.status_code == 404
    print("[OK] GET /api/emails/99999 -> 404")


def test_stats():
    headers = get_auth_headers()
    resp = client.get("/api/stats", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_emails" in data
    assert "by_status" in data
    assert "emails_per_day" in data
    assert "by_category" in data
    assert "by_risk_band" in data
    assert "by_country" in data
    print(f"[OK] GET /api/stats -> total: {data['total_emails']}, categories: {list(data['by_category'].keys())}")


def test_routing_rules_crud():
    headers = get_auth_headers()

    # Lista regole
    resp = client.get("/api/routing-rules", headers=headers)
    assert resp.status_code == 200
    rules = resp.json()
    print(f"[OK] GET /api/routing-rules -> {rules['count']} rules")


def test_dry_run():
    headers = get_auth_headers()
    context = {
        "email_context": {
            "from_address": "test@example.com",
            "subject": "Test dry run",
            "security": {"verdict": "SAFE", "risk_score": 10},
            "country": {"country_code": "IT"},
            "content": {"category": "commerciale"},
        }
    }
    resp = client.post("/api/routing-rules/dry-run", json=context, headers=headers)
    assert resp.status_code == 200
    print(f"[OK] POST /api/routing-rules/dry-run -> {resp.json()}")


if __name__ == "__main__":
    print("=" * 60)
    print("  TEST API ENDPOINTS - SalesEmailTool")
    print("=" * 60)
    print()

    tests = [
        test_health,
        test_auth_login,
        test_auth_login_invalid,
        test_auth_me,
        test_protected_without_token,
        test_list_emails,
        test_list_emails_pagination,
        test_email_detail,
        test_email_detail_not_found,
        test_stats,
        test_routing_rules_crud,
        test_dry_run,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print()
    print(f"Risultati: {passed} passed, {failed} failed")
