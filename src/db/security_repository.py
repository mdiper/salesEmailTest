import json

from src.db.connection import get_connection
from src.security.risk_scorer import SecurityResult
from src.utils.logger import logger


class SecurityRepository:
    """Gestisce il salvataggio dei risultati di sicurezza nella tabella security_results."""

    def save_result(self, email_id: int, result: SecurityResult, header_data: dict = None) -> int:
        """Salva il SecurityResult nel DB.

        Args:
            email_id: ID dell'email analizzata
            result: SecurityResult con score, verdict, flags, details
            header_data: dict con risultati header analysis per campi SPF/DKIM/DMARC

        Returns:
            ID del record inserito
        """
        conn = get_connection()
        cursor = conn.cursor()

        spf_pass = None
        dkim_pass = None
        dmarc_pass = None
        phishing_score = None

        if header_data:
            spf_pass = header_data.get("spf", {}).get("pass")
            dkim_pass = header_data.get("dkim", {}).get("pass")
            dmarc_pass = header_data.get("dmarc", {}).get("pass")

        if result.details.get("component_scores"):
            phishing_score = result.details["component_scores"].get("phishing")

        sql = """
            INSERT INTO security_results
                (email_id, verdict, risk_score, spf_pass, dkim_pass, dmarc_pass,
                 phishing_score, flags, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            email_id,
            result.verdict,
            result.risk_score,
            spf_pass,
            dkim_pass,
            dmarc_pass,
            phishing_score,
            json.dumps(result.flags),
            json.dumps(result.details),
        )

        try:
            cursor.execute(sql, values)
            conn.commit()
            record_id = cursor.lastrowid

            logger.info(
                "security_result_saved",
                email_id=email_id,
                record_id=record_id,
                verdict=result.verdict,
                risk_score=result.risk_score,
            )

            return record_id
        except Exception as e:
            conn.rollback()
            logger.error("security_result_save_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def get_result(self, email_id: int) -> dict | None:
        """Recupera il risultato di sicurezza per un email_id."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM security_results WHERE email_id = %s", (email_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row:
            if isinstance(row.get("flags"), str):
                row["flags"] = json.loads(row["flags"])
            if isinstance(row.get("details"), str):
                row["details"] = json.loads(row["details"])

        return row
