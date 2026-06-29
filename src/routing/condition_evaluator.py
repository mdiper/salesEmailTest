import re


class ConditionEvaluator:
    """Valuta condizioni di routing contro un contesto email.

    Supporta operatori: eq, neq, gt, gte, lt, lte, contains, matches, in, not_in.
    Supporta dot-notation per accesso a campi nested (es: security.risk_score).
    """

    OPERATORS = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "gt": lambda a, b: float(a) > float(b) if a is not None else False,
        "gte": lambda a, b: float(a) >= float(b) if a is not None else False,
        "lt": lambda a, b: float(a) < float(b) if a is not None else False,
        "lte": lambda a, b: float(a) <= float(b) if a is not None else False,
        "contains": lambda a, b: b.lower() in str(a).lower() if a is not None else False,
        "matches": lambda a, b: bool(re.search(b, str(a), re.IGNORECASE)) if a is not None else False,
        "in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else str(a) in str(b),
        "not_in": lambda a, b: a not in b if isinstance(b, (list, tuple, set)) else str(a) not in str(b),
    }

    def evaluate(self, condition: dict, context: dict) -> bool:
        """Valuta una singola condizione contro il contesto.

        Args:
            condition: dict con 'field', 'operator', 'value'
            context: dict con i dati email (security, country, content, ecc.)

        Returns:
            True se la condizione e' soddisfatta.
        """
        field_path = condition.get("field", "")
        operator = condition.get("operator", "eq")
        expected_value = condition.get("value")

        actual_value = self._resolve_field(field_path, context)

        op_func = self.OPERATORS.get(operator)
        if op_func is None:
            return False

        try:
            return op_func(actual_value, expected_value)
        except (TypeError, ValueError):
            return False

    def evaluate_all(self, conditions: list[dict], context: dict, logic: str = "AND") -> bool:
        """Valuta un gruppo di condizioni con logica AND o OR.

        Args:
            conditions: lista di condizioni
            context: contesto email
            logic: 'AND' o 'OR'

        Returns:
            True se le condizioni sono soddisfatte secondo la logica specificata.
        """
        if not conditions:
            return False

        results = [self.evaluate(c, context) for c in conditions]

        if logic.upper() == "OR":
            return any(results)
        return all(results)

    def _resolve_field(self, field_path: str, context: dict):
        """Risolve un campo dot-notation nel contesto.
        Es: 'security.risk_score' -> context['security']['risk_score']
        """
        if not field_path:
            return None

        parts = field_path.split(".")
        current = context

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                return None

        return current
