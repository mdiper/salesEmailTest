from src.utils.logger import logger
from src.db.connection import get_connection
from src.security.engine import SecurityEngine
from src.country.detector import CountryDetector
from src.content.analyzer import ContentAnalyzer
from src.routing.engine import RoutingEngine
from src.routing.action_executor import ActionExecutor


class EmailPipeline:
    """Pipeline completa di analisi email:
    SecurityEngine -> CountryDetector -> ContentAnalyzer -> RoutingEngine + ActionExecutor.

    Gestisce errori per step: se uno step fallisce, marca l'email come 'failed'
    e prosegue con le email successive.
    Implementa fast-track: se security = DANGEROUS, salta country + content
    e va direttamente al routing.
    """

    def __init__(self):
        self.security_engine = SecurityEngine()
        self.country_detector = CountryDetector()
        self.content_analyzer = ContentAnalyzer()
        self.routing_engine = RoutingEngine()
        self.action_executor = ActionExecutor()

    def process(self, email_id: int, parsed: dict) -> dict:
        """Processa una singola email attraverso l'intera pipeline.

        Args:
            email_id: ID dell'email nel DB (gia' salvata da IngestionService)
            parsed: dict output del MIMEParser

        Returns:
            dict con risultati di ogni step.
        """
        logger.info("pipeline_start", email_id=email_id, subject=parsed.get("subject", "")[:50])

        result = {
            "email_id": email_id,
            "security": None,
            "country": None,
            "content": None,
            "routing_actions": [],
            "status": "completed",
            "error": None,
        }

        # === STEP 1: Security Analysis ===
        try:
            security_data = {
                "headers": parsed.get("headers", {}),
                "body_html": parsed.get("body_html"),
                "body_text": parsed.get("body_text"),
                "from": parsed.get("from", ""),
                "attachments": parsed.get("attachments", []),
                "email_id": email_id,
            }
            security_result = self.security_engine.analyze_email(security_data, save_to_db=True)
            result["security"] = {
                "verdict": security_result.verdict,
                "risk_score": security_result.risk_score,
                "flags": security_result.flags,
            }
        except Exception as e:
            logger.error("pipeline_security_failed", email_id=email_id, error=str(e))
            result["status"] = "failed"
            result["error"] = f"security: {str(e)}"
            self._mark_failed(email_id, result["error"])
            return result

        # === FAST-TRACK: se DANGEROUS, salta country + content ===
        if security_result.verdict == "DANGEROUS":
            logger.info("pipeline_fast_track", email_id=email_id, verdict="DANGEROUS")
            result["country"] = {"skipped": True, "reason": "fast-track DANGEROUS"}
            result["content"] = {"skipped": True, "reason": "fast-track DANGEROUS"}
        else:
            # === STEP 2: Country Detection ===
            try:
                country_data = {
                    "from": parsed.get("from", ""),
                    "headers": parsed.get("headers", {}),
                    "body_text": parsed.get("body_text", ""),
                    "email_id": email_id,
                }
                country_result = self.country_detector.detect(country_data)
                result["country"] = country_result
            except Exception as e:
                logger.error("pipeline_country_failed", email_id=email_id, error=str(e))
                result["country"] = {"error": str(e)}

            # === STEP 3: Content Analysis ===
            try:
                content_data = {
                    "body_html": parsed.get("body_html"),
                    "body_text": parsed.get("body_text"),
                    "email_id": email_id,
                }
                content_result = self.content_analyzer.analyze(content_data, save_to_db=True)
                result["content"] = {
                    "category": content_result.get("category"),
                    "category_confidence": content_result.get("category_confidence"),
                    "summary": content_result.get("summary", "")[:200],
                }
            except Exception as e:
                logger.error("pipeline_content_failed", email_id=email_id, error=str(e))
                result["content"] = {"error": str(e)}

        # === STEP 4: Routing ===
        try:
            email_context = {
                "security": result["security"] or {},
                "country": result["country"] if not result["country"].get("skipped") and not result["country"].get("error") else {},
                "content": result["content"] if not result["content"].get("skipped") and not result["content"].get("error") else {},
                "email": {
                    "from": parsed.get("from", ""),
                    "subject": parsed.get("subject", ""),
                    "has_attachments": len(parsed.get("attachments", [])) > 0,
                },
            }

            actions = self.routing_engine.evaluate(email_context)
            result["routing_actions"] = actions

            # Esegui le azioni
            for action in actions:
                self.action_executor.execute(email_id, action)

        except Exception as e:
            logger.error("pipeline_routing_failed", email_id=email_id, error=str(e))
            result["routing_actions"] = [{"error": str(e)}]

        # === Aggiorna status finale ===
        if result["status"] != "failed":
            has_block = any(a.get("action_type") == "block" for a in result["routing_actions"])
            has_quarantine = any(a.get("action_type") == "quarantine" for a in result["routing_actions"])

            if not has_block and not has_quarantine:
                self._update_status(email_id, "completed")

        logger.info(
            "pipeline_complete",
            email_id=email_id,
            security_verdict=result["security"].get("verdict") if result["security"] else None,
            actions_count=len(result["routing_actions"]),
            status=result["status"],
        )

        return result

    def _mark_failed(self, email_id: int, error: str):
        """Marca l'email come failed nel DB."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE emails SET processing_status = %s WHERE id = %s",
                ("failed", email_id),
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            pass

    def _update_status(self, email_id: int, status: str):
        """Aggiorna lo status dell'email nel DB."""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE emails SET processing_status = %s WHERE id = %s",
                (status, email_id),
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            pass
