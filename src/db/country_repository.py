import json

from src.db.connection import get_connection
from src.utils.logger import logger


class CountryRepository:
    """Gestisce il salvataggio dei risultati di country detection nella tabella country_results."""

    def save_result(self, email_id: int, country_result: dict) -> int:
        """Salva il risultato di country detection nel DB.

        Args:
            email_id: ID dell'email analizzata
            country_result: dict con country, country_code, confidence, detection_method, signals

        Returns:
            ID del record inserito
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Serializza signals senza raw_bytes o dati troppo grandi
        signals_data = []
        for s in country_result.get("signals", []):
            signals_data.append({
                "method": s.get("method"),
                "country": s.get("country"),
                "country_code": s.get("country_code"),
                "confidence": s.get("confidence"),
                "detail": s.get("detail"),
            })

        sql = """
            INSERT INTO country_results
                (email_id, country, country_code, confidence, detection_method, signals)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        values = (
            email_id,
            country_result.get("country", "Unknown"),
            country_result.get("country_code"),
            country_result.get("confidence", 0.0),
            country_result.get("detection_method", "none"),
            json.dumps(signals_data),
        )

        try:
            cursor.execute(sql, values)
            conn.commit()
            record_id = cursor.lastrowid

            logger.info(
                "country_result_saved",
                email_id=email_id,
                record_id=record_id,
                country=country_result.get("country"),
                confidence=country_result.get("confidence"),
            )

            return record_id
        except Exception as e:
            conn.rollback()
            logger.error("country_result_save_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def get_result(self, email_id: int) -> dict | None:
        """Recupera il risultato di country detection per un email_id."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM country_results WHERE email_id = %s", (email_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row and isinstance(row.get("signals"), str):
            row["signals"] = json.loads(row["signals"])

        return row
