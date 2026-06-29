import json

from src.db.connection import get_connection
from src.utils.logger import logger


class AuditRepository:
    """Gestisce il salvataggio degli eventi di audit nella tabella audit_log."""

    def save_audit_log(self, event_type: str, entity_type: str | None = None,
                       entity_id: int | None = None, actor: str | None = None,
                       details: dict | None = None) -> int:
        """Salva un evento di audit nel DB.

        Args:
            event_type: tipo evento (es: 'email_blocked', 'rule_created')
            entity_type: tipo entita' (es: 'email', 'routing_rule')
            entity_id: ID dell'entita'
            actor: chi ha generato l'evento (es: 'system', 'admin')
            details: dettagli aggiuntivi

        Returns:
            ID del record inserito
        """
        conn = get_connection()
        cursor = conn.cursor()

        sql = """
            INSERT INTO audit_log
                (event_type, entity_type, entity_id, actor, details)
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (
            event_type,
            entity_type,
            entity_id,
            actor or "system",
            json.dumps(details) if details else None,
        )

        try:
            cursor.execute(sql, values)
            conn.commit()
            record_id = cursor.lastrowid
            return record_id
        except Exception as e:
            conn.rollback()
            logger.error("audit_log_save_failed", error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()
