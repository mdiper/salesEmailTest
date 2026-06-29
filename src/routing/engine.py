from src.routing.condition_evaluator import ConditionEvaluator
from src.db.routing_repository import RoutingRepository
from src.utils.logger import logger


class RoutingEngine:
    """Motore di routing: valuta le regole in ordine di priorita' e raccoglie le azioni."""

    def __init__(self):
        self.evaluator = ConditionEvaluator()
        self.repository = RoutingRepository()
        self._rules: list[dict] | None = None

    def evaluate(self, email_context: dict) -> list[dict]:
        """Valuta tutte le regole attive contro il contesto email.

        Args:
            email_context: dict con security, country, content, email metadata

        Returns:
            Lista di azioni da eseguire (deduplicate).
        """
        rules = self._get_rules()
        actions = []

        for rule in rules:
            if self._matches(rule, email_context):
                rule_actions = rule.get("actions", [])
                for action in rule_actions:
                    actions.append({
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "action_type": action.get("type"),
                        "params": action.get("params", {}),
                        "priority": rule["priority"],
                    })

                logger.info(
                    "routing_rule_matched",
                    rule_id=rule["id"],
                    rule_name=rule["name"],
                    actions_count=len(rule_actions),
                )

                if rule.get("stop_processing"):
                    break

        actions = self._deduplicate_actions(actions)

        logger.info(
            "routing_evaluation_complete",
            rules_checked=len(rules),
            actions_count=len(actions),
        )

        return actions

    def _matches(self, rule: dict, email_context: dict) -> bool:
        """Valuta se una regola matcha il contesto con logica AND/OR."""
        conditions = rule.get("conditions", [])
        logic = rule.get("condition_logic", "AND")

        return self.evaluator.evaluate_all(conditions, email_context, logic)

    def _deduplicate_actions(self, actions: list[dict]) -> list[dict]:
        """Rimuove azioni duplicate e risolve conflitti.
        Block ha priorita' su tutto: se presente, rimuove forward/notify."""
        if not actions:
            return actions

        has_block = any(a["action_type"] == "block" for a in actions)

        seen = set()
        unique = []

        for action in actions:
            action_type = action["action_type"]

            # Se c'e' un block, skip forward
            if has_block and action_type == "forward":
                continue

            key = (action_type, str(action.get("params", {})))
            if key not in seen:
                seen.add(key)
                unique.append(action)

        return unique

    def _get_rules(self) -> list[dict]:
        """Carica le regole dal DB (con cache per la sessione)."""
        if self._rules is None:
            self._rules = self.repository.get_active_rules()
            logger.info("routing_rules_loaded", count=len(self._rules))
        return self._rules

    def reload_rules(self):
        """Forza il ricaricamento delle regole dal DB."""
        self._rules = None
