import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from src.api.auth import verify_token
from src.db.connection import get_connection

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
def list_emails(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    category: str | None = None,
    country_code: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    _user: str = Depends(verify_token),
):
    """Lista email con paginazione e filtri."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    where_clauses = []
    params = []

    if status:
        where_clauses.append("e.processing_status = %s")
        params.append(status)
    if category:
        where_clauses.append("cr.category = %s")
        params.append(category)
    if country_code:
        where_clauses.append("ctr.country_code = %s")
        params.append(country_code)
    if date_from:
        where_clauses.append("e.date_received >= %s")
        params.append(date_from)
    if date_to:
        where_clauses.append("e.date_received <= %s")
        params.append(date_to)
    if search:
        where_clauses.append("(e.subject LIKE %s OR e.from_address LIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    # Count totale
    count_sql = f"""
        SELECT COUNT(*) as total
        FROM emails e
        LEFT JOIN content_results cr ON cr.email_id = e.id
        LEFT JOIN country_results ctr ON ctr.email_id = e.id
        {where_sql}
    """
    cursor.execute(count_sql, params)
    total = cursor.fetchone()["total"]

    # Query paginata
    offset = (page - 1) * per_page
    query_sql = f"""
        SELECT
            e.id, e.message_id, e.from_address, e.from_display,
            e.subject, e.date_received, e.processing_status, e.has_attachments, e.tags,
            sr.verdict as security_verdict, sr.risk_score,
            cr.category, cr.category_confidence,
            ctr.country, ctr.country_code
        FROM emails e
        LEFT JOIN security_results sr ON sr.email_id = e.id
        LEFT JOIN content_results cr ON cr.email_id = e.id
        LEFT JOIN country_results ctr ON ctr.email_id = e.id
        {where_sql}
        ORDER BY e.date_received DESC
        LIMIT %s OFFSET %s
    """
    cursor.execute(query_sql, params + [per_page, offset])
    emails = cursor.fetchall()

    cursor.close()
    conn.close()

    # Parse JSON fields
    for email in emails:
        if isinstance(email.get("tags"), str):
            email["tags"] = json.loads(email["tags"])
        for key, val in email.items():
            if isinstance(val, datetime):
                email[key] = val.isoformat()

    return {
        "emails": emails,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


@router.get("/{email_id}")
def get_email_detail(email_id: int, _user: str = Depends(verify_token)):
    """Dettaglio singola email con tutti i risultati di analisi."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Email base
    cursor.execute("SELECT * FROM emails WHERE id = %s", (email_id,))
    email = cursor.fetchone()
    if not email:
        cursor.close()
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Email non trovata")

    # Security results
    cursor.execute("SELECT * FROM security_results WHERE email_id = %s", (email_id,))
    security = cursor.fetchone()

    # Country results
    cursor.execute("SELECT * FROM country_results WHERE email_id = %s", (email_id,))
    country = cursor.fetchone()

    # Content results
    cursor.execute("SELECT * FROM content_results WHERE email_id = %s", (email_id,))
    content = cursor.fetchone()

    # Attachments
    cursor.execute("SELECT id, filename, content_type, size_bytes, hash_sha256, scan_status FROM email_attachments WHERE email_id = %s", (email_id,))
    attachments = cursor.fetchall()

    # Routing logs
    cursor.execute("SELECT * FROM routing_logs WHERE email_id = %s ORDER BY executed_at DESC", (email_id,))
    routing_logs = cursor.fetchall()

    cursor.close()
    conn.close()

    # Parse JSON fields
    def parse_json_fields(obj):
        if obj is None:
            return None
        for key, val in obj.items():
            if isinstance(val, str) and val.startswith(("[", "{")):
                try:
                    obj[key] = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    pass
            elif isinstance(val, datetime):
                obj[key] = val.isoformat()
        return obj

    return {
        "email": parse_json_fields(email),
        "security": parse_json_fields(security),
        "country": parse_json_fields(country),
        "content": parse_json_fields(content),
        "attachments": [parse_json_fields(a) for a in attachments],
        "routing_logs": [parse_json_fields(r) for r in routing_logs],
    }
