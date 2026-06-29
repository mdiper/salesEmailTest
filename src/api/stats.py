from fastapi import APIRouter, Depends

from src.api.auth import verify_token
from src.db.connection import get_connection

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_stats(_user: str = Depends(verify_token)):
    """Statistiche aggregate: email per giorno, categorie, risk score, paesi."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    stats = {}

    # Email totali e per status
    cursor.execute("""
        SELECT processing_status, COUNT(*) as count
        FROM emails
        GROUP BY processing_status
    """)
    stats["by_status"] = {row["processing_status"]: row["count"] for row in cursor.fetchall()}
    stats["total_emails"] = sum(stats["by_status"].values())

    # Email per giorno (ultimi 30 giorni)
    cursor.execute("""
        SELECT DATE(date_received) as day, COUNT(*) as count
        FROM emails
        WHERE date_received >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        GROUP BY DATE(date_received)
        ORDER BY day
    """)
    stats["emails_per_day"] = [
        {"day": row["day"].isoformat() if row["day"] else None, "count": row["count"]}
        for row in cursor.fetchall()
    ]

    # Distribuzione per categoria
    cursor.execute("""
        SELECT category, COUNT(*) as count
        FROM content_results
        GROUP BY category
        ORDER BY count DESC
    """)
    stats["by_category"] = {row["category"]: row["count"] for row in cursor.fetchall()}

    # Distribuzione risk score (fasce)
    cursor.execute("""
        SELECT
            CASE
                WHEN risk_score BETWEEN 0 AND 29 THEN 'SAFE (0-29)'
                WHEN risk_score BETWEEN 30 AND 69 THEN 'SUSPICIOUS (30-69)'
                WHEN risk_score BETWEEN 70 AND 100 THEN 'DANGEROUS (70-100)'
            END as risk_band,
            COUNT(*) as count
        FROM security_results
        GROUP BY risk_band
        ORDER BY risk_band
    """)
    stats["by_risk_band"] = {row["risk_band"]: row["count"] for row in cursor.fetchall() if row["risk_band"]}

    # Distribuzione verdict
    cursor.execute("""
        SELECT verdict, COUNT(*) as count
        FROM security_results
        GROUP BY verdict
        ORDER BY count DESC
    """)
    stats["by_verdict"] = {row["verdict"]: row["count"] for row in cursor.fetchall()}

    # Email per paese (top 10)
    cursor.execute("""
        SELECT country, country_code, COUNT(*) as count
        FROM country_results
        WHERE country IS NOT NULL
        GROUP BY country, country_code
        ORDER BY count DESC
        LIMIT 10
    """)
    stats["by_country"] = [
        {"country": row["country"], "code": row["country_code"], "count": row["count"]}
        for row in cursor.fetchall()
    ]

    # Routing actions recenti
    cursor.execute("""
        SELECT action_type, COUNT(*) as count
        FROM routing_logs
        GROUP BY action_type
        ORDER BY count DESC
    """)
    stats["routing_actions"] = {row["action_type"]: row["count"] for row in cursor.fetchall()}

    cursor.close()
    conn.close()

    return stats
