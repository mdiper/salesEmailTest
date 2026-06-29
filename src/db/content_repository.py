import json

from src.db.connection import get_connection
from src.utils.logger import logger


class ContentRepository:
    """Gestisce il salvataggio dei risultati di content analysis nella tabella content_results."""

    def save_result(self, email_id: int, content_result: dict) -> int:
        """Salva il risultato di content analysis nel DB.

        Args:
            email_id: ID dell'email analizzata
            content_result: dict con category, confidence, summary, sentiment, urgency, entities

        Returns:
            ID del record inserito
        """
        conn = get_connection()
        cursor = conn.cursor()

        sql = """
            INSERT INTO content_results
                (email_id, category, category_confidence, summary, sentiment, urgency, entities)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            email_id,
            content_result.get("category", "unknown"),
            content_result.get("category_confidence"),
            content_result.get("summary"),
            content_result.get("sentiment"),
            content_result.get("urgency"),
            json.dumps(content_result.get("entities", {})),
        )

        try:
            cursor.execute(sql, values)
            conn.commit()
            record_id = cursor.lastrowid

            logger.info(
                "content_result_saved",
                email_id=email_id,
                record_id=record_id,
                category=content_result.get("category"),
            )

            return record_id
        except Exception as e:
            conn.rollback()
            logger.error("content_result_save_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def get_result(self, email_id: int) -> dict | None:
        """Recupera il risultato di content analysis per un email_id."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM content_results WHERE email_id = %s", (email_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row and isinstance(row.get("entities"), str):
            row["entities"] = json.loads(row["entities"])

        return row
