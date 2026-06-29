from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import verify_token
from src.db.connection import get_connection

router = APIRouter(prefix="/api/forwarding", tags=["forwarding"])


class ForwardingRuleCreate(BaseModel):
    country_code: str
    country_name: str
    forward_to: str
    is_active: bool = True


class ForwardingRuleUpdate(BaseModel):
    country_name: str | None = None
    forward_to: str | None = None
    is_active: bool | None = None


@router.get("/countries")
def list_available_countries(_user: str = Depends(verify_token)):
    """Lista di tutti i paesi del mondo (per combobox)."""
    from src.country.maps import COUNTRY_TLD_MAP

    seen = {}
    for _tld, (name, code) in COUNTRY_TLD_MAP.items():
        if code and code not in seen:
            seen[code] = name

    countries = sorted(
        [{"country": name, "country_code": code} for code, name in seen.items()],
        key=lambda x: x["country"],
    )
    return {"countries": countries}


@router.get("")
def list_forwarding_rules(_user: str = Depends(verify_token)):
    """Lista tutte le regole di forwarding per paese."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM forwarding_rules ORDER BY country_name, forward_to")
    rules = cursor.fetchall()
    cursor.close()
    conn.close()

    for r in rules:
        for k, v in r.items():
            if isinstance(v, datetime):
                r[k] = v.isoformat()

    return {"rules": rules, "count": len(rules)}


@router.post("", status_code=201)
def create_forwarding_rule(request: ForwardingRuleCreate, _user: str = Depends(verify_token)):
    """Crea una nuova regola di forwarding. Stesso paese puo' avere piu' destinatari."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Check duplicato esatto (stesso paese + stesso destinatario)
    cursor.execute(
        "SELECT id FROM forwarding_rules WHERE country_code = %s AND forward_to = %s",
        (request.country_code.upper(), request.forward_to),
    )
    if cursor.fetchone():
        cursor.close()
        conn.close()
        raise HTTPException(status_code=409, detail=f"Questo destinatario e' gia' configurato per il paese {request.country_code}")

    cursor.execute(
        "INSERT INTO forwarding_rules (country_code, country_name, forward_to, is_active) VALUES (%s, %s, %s, %s)",
        (request.country_code.upper(), request.country_name, request.forward_to, request.is_active),
    )
    conn.commit()
    rule_id = cursor.lastrowid

    cursor.execute("SELECT * FROM forwarding_rules WHERE id = %s", (rule_id,))
    rule = cursor.fetchone()
    cursor.close()
    conn.close()

    return rule


@router.put("/{rule_id}")
def update_forwarding_rule(rule_id: int, request: ForwardingRuleUpdate, _user: str = Depends(verify_token)):
    """Aggiorna una regola di forwarding."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM forwarding_rules WHERE id = %s", (rule_id,))
    existing = cursor.fetchone()
    if not existing:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Regola non trovata")

    updates = []
    params = []
    if request.country_name is not None:
        updates.append("country_name = %s")
        params.append(request.country_name)
    if request.forward_to is not None:
        updates.append("forward_to = %s")
        params.append(request.forward_to)
    if request.is_active is not None:
        updates.append("is_active = %s")
        params.append(request.is_active)

    if updates:
        params.append(rule_id)
        cursor.execute(f"UPDATE forwarding_rules SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()

    cursor.execute("SELECT * FROM forwarding_rules WHERE id = %s", (rule_id,))
    rule = cursor.fetchone()
    cursor.close()
    conn.close()

    return rule


@router.delete("/{rule_id}")
def delete_forwarding_rule(rule_id: int, _user: str = Depends(verify_token)):
    """Elimina una regola di forwarding."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM forwarding_rules WHERE id = %s", (rule_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Regola non trovata")

    cursor.execute("DELETE FROM forwarding_rules WHERE id = %s", (rule_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Regola eliminata"}


@router.get("/resolve/{email_id}")
def resolve_forward_for_email(email_id: int, _user: str = Depends(verify_token)):
    """Restituisce tutti i destinatari di forward per una email in base al suo paese."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT fr.forward_to, fr.country_name, cr.country_code
        FROM country_results cr
        JOIN forwarding_rules fr ON fr.country_code = cr.country_code AND fr.is_active = TRUE
        WHERE cr.email_id = %s
    """, (email_id,))
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    if results:
        return {
            "recipients": [r["forward_to"] for r in results],
            "country": results[0]["country_name"],
            "country_code": results[0]["country_code"],
        }
    else:
        return {"recipients": [], "country": None, "country_code": None}
