import json

from src.db.connection import get_connection
from src.utils.logger import logger


class RoutingRepository:
    """Gestisce le operazioni DB per routing rules e routing logs."""

    def get_active_rules(self) -> list[dict]:
        """Restituisce le regole attive ordinate per priority (ASC = alta priorita' prima)."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT * FROM routing_rules
            WHERE enabled = TRUE
            ORDER BY priority ASC
        """)
        rules = cursor.fetchall()

        cursor.close()
        conn.close()

        for rule in rules:
            if isinstance(rule.get("conditions"), str):
                rule["conditions"] = json.loads(rule["conditions"])
            if isinstance(rule.get("actions"), str):
                rule["actions"] = json.loads(rule["actions"])

        return rules

    def get_all_rules(self) -> list[dict]:
        """Restituisce tutte le regole (attive e disabilitate)."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM routing_rules ORDER BY priority ASC")
        rules = cursor.fetchall()

        cursor.close()
        conn.close()

        for rule in rules:
            if isinstance(rule.get("conditions"), str):
                rule["conditions"] = json.loads(rule["conditions"])
            if isinstance(rule.get("actions"), str):
                rule["actions"] = json.loads(rule["actions"])

        return rules

    def get_rule_by_id(self, rule_id: int) -> dict | None:
        """Restituisce una singola regola per ID."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM routing_rules WHERE id = %s", (rule_id,))
        rule = cursor.fetchone()

        cursor.close()
        conn.close()

        if rule:
            if isinstance(rule.get("conditions"), str):
                rule["conditions"] = json.loads(rule["conditions"])
            if isinstance(rule.get("actions"), str):
                rule["actions"] = json.loads(rule["actions"])

        return rule

    def create_rule(self, data: dict) -> int:
        """Crea una nuova regola di routing."""
        conn = get_connection()
        cursor = conn.cursor()

        sql = """
            INSERT INTO routing_rules
                (name, priority, enabled, conditions, condition_logic, actions, stop_processing, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data["name"],
            data.get("priority", 100),
            data.get("enabled", True),
            json.dumps(data["conditions"]),
            data.get("condition_logic", "AND"),
            json.dumps(data["actions"]),
            data.get("stop_processing", False),
            data.get("created_by", "api"),
        )

        try:
            cursor.execute(sql, values)
            conn.commit()
            rule_id = cursor.lastrowid
            logger.info("routing_rule_created", rule_id=rule_id, name=data["name"])
            return rule_id
        except Exception as e:
            conn.rollback()
            logger.error("routing_rule_create_failed", error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def update_rule(self, rule_id: int, data: dict) -> bool:
        """Aggiorna una regola esistente."""
        conn = get_connection()
        cursor = conn.cursor()

        fields = []
        values = []

        if "name" in data:
            fields.append("name = %s")
            values.append(data["name"])
        if "priority" in data:
            fields.append("priority = %s")
            values.append(data["priority"])
        if "enabled" in data:
            fields.append("enabled = %s")
            values.append(data["enabled"])
        if "conditions" in data:
            fields.append("conditions = %s")
            values.append(json.dumps(data["conditions"]))
        if "condition_logic" in data:
            fields.append("condition_logic = %s")
            values.append(data["condition_logic"])
        if "actions" in data:
            fields.append("actions = %s")
            values.append(json.dumps(data["actions"]))
        if "stop_processing" in data:
            fields.append("stop_processing = %s")
            values.append(data["stop_processing"])

        if not fields:
            return False

        values.append(rule_id)
        sql = f"UPDATE routing_rules SET {', '.join(fields)} WHERE id = %s"

        try:
            cursor.execute(sql, values)
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info("routing_rule_updated", rule_id=rule_id)
            return updated
        except Exception as e:
            conn.rollback()
            logger.error("routing_rule_update_failed", error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def delete_rule(self, rule_id: int) -> bool:
        """Elimina una regola."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM routing_rules WHERE id = %s", (rule_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("routing_rule_deleted", rule_id=rule_id)
            return deleted
        except Exception as e:
            conn.rollback()
            logger.error("routing_rule_delete_failed", error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def save_routing_log(self, email_id: int, rule_id: int | None,
                         rule_name: str | None, action_type: str,
                         action_details: dict | None = None,
                         success: bool = True, error_message: str | None = None) -> int:
        """Salva un log di routing nella tabella routing_logs."""
        conn = get_connection()
        cursor = conn.cursor()

        sql = """
            INSERT INTO routing_logs
                (email_id, rule_id, rule_name, action_type, action_details, success, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            email_id,
            rule_id,
            rule_name,
            action_type,
            json.dumps(action_details) if action_details else None,
            success,
            error_message,
        )

        try:
            cursor.execute(sql, values)
            conn.commit()
            record_id = cursor.lastrowid
            return record_id
        except Exception as e:
            conn.rollback()
            logger.error("routing_log_save_failed", error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()
