from src.db.connection import get_connection
from src.db.routing_repository import RoutingRepository
from src.db.audit_repository import AuditRepository
from src.utils.logger import logger


class ActionExecutor:
    """Esegue le azioni di routing sulle email."""

    def __init__(self):
        self.routing_repo = RoutingRepository()
        self.audit_repo = AuditRepository()

    def execute(self, email_id: int, action: dict) -> bool:
        """Dispatcher: esegue l'azione corretta in base al tipo.

        Args:
            email_id: ID dell'email
            action: dict con action_type, params, rule_id, rule_name

        Returns:
            True se l'azione e' stata eseguita con successo.
        """
        action_type = action.get("action_type")
        params = action.get("params", {})
        rule_id = action.get("rule_id")
        rule_name = action.get("rule_name")

        success = False
        error_message = None

        try:
            if action_type == "block":
                success = self._action_block(email_id, params)
            elif action_type == "quarantine":
                success = self._action_quarantine(email_id, params)
            elif action_type == "tag":
                success = self._action_tag(email_id, params)
            elif action_type == "notify":
                success = self._action_notify(email_id, params)
            elif action_type == "forward":
                success = self._action_forward(email_id, params)
            else:
                logger.warning("unknown_action_type", action_type=action_type)
                error_message = f"Unknown action type: {action_type}"
        except Exception as e:
            error_message = str(e)
            logger.error("action_execution_failed", action_type=action_type, error=error_message)

        # Log routing
        self.routing_repo.save_routing_log(
            email_id=email_id,
            rule_id=rule_id,
            rule_name=rule_name,
            action_type=action_type,
            action_details=params,
            success=success,
            error_message=error_message,
        )

        # Audit log
        self.audit_repo.save_audit_log(
            event_type=f"action_{action_type}",
            entity_type="email",
            entity_id=email_id,
            actor="system",
            details={
                "rule_id": rule_id,
                "rule_name": rule_name,
                "action_type": action_type,
                "params": params,
                "success": success,
            },
        )

        return success

    def _action_block(self, email_id: int, params: dict) -> bool:
        """Marca l'email come bloccata nel DB."""
        conn = get_connection()
        cursor = conn.cursor()

        reason = params.get("reason", "blocked_by_rule")

        try:
            cursor.execute(
                "UPDATE emails SET processing_status = %s WHERE id = %s",
                ("blocked", email_id),
            )
            conn.commit()
            logger.info("email_blocked", email_id=email_id, reason=reason)
            return True
        except Exception as e:
            conn.rollback()
            logger.error("block_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def _action_quarantine(self, email_id: int, params: dict) -> bool:
        """Sposta l'email in quarantena: aggiorna status nel DB."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE emails SET processing_status = %s WHERE id = %s",
                ("quarantined", email_id),
            )
            conn.commit()
            logger.info("email_quarantined", email_id=email_id)
            return True
        except Exception as e:
            conn.rollback()
            logger.error("quarantine_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def _action_tag(self, email_id: int, params: dict) -> bool:
        """Salva tag associati all'email nel campo JSON."""
        conn = get_connection()
        cursor = conn.cursor()

        tags = params.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        try:
            import json
            cursor.execute(
                "UPDATE emails SET tags = %s WHERE id = %s",
                (json.dumps(tags), email_id),
            )
            conn.commit()
            logger.info("email_tagged", email_id=email_id, tags=tags)
            return True
        except Exception as e:
            conn.rollback()
            logger.error("tag_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            conn.close()

    def _action_notify(self, email_id: int, params: dict) -> bool:
        """Invia notifica all'admin (log per ora, SMTP in futuro)."""
        recipient = params.get("recipient", "admin")
        message = params.get("message", f"Alert: email {email_id} requires attention")

        # Per ora logga la notifica; SMTP sara' integrato nella fase di deployment
        logger.info(
            "notification_sent",
            email_id=email_id,
            recipient=recipient,
            message=message,
        )
        return True

    def _action_forward(self, email_id: int, params: dict) -> bool:
        """Registra l'inoltro dell'email verso il destinatario specificato.

        L'invio SMTP non e' ancora implementato, ma il destinatario viene
        salvato nel routing log per visibilita' nel frontend.
        """
        recipient = params.get("to", params.get("recipient", ""))
        if not recipient:
            logger.warning("forward_no_recipient", email_id=email_id)
            return False

        logger.info(
            "email_forwarded",
            email_id=email_id,
            recipient=recipient,
        )
        return True
