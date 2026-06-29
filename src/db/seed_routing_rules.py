r"""
Inserisce le regole iniziali di routing nel DB.
Uso: .\venv\Scripts\python -m src.db.seed_routing_rules
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.db.connection import get_connection


INITIAL_RULES = [
    {
        "name": "Block DANGEROUS emails",
        "priority": 1,
        "conditions": [
            {"field": "security.verdict", "operator": "eq", "value": "DANGEROUS"}
        ],
        "condition_logic": "AND",
        "actions": [
            {"type": "block", "params": {"reason": "security_dangerous"}},
            {"type": "notify", "params": {"recipient": "admin", "message": "Email bloccata: security DANGEROUS"}},
        ],
        "stop_processing": True,
    },
    {
        "name": "Quarantine SUSPICIOUS with high score",
        "priority": 2,
        "conditions": [
            {"field": "security.verdict", "operator": "eq", "value": "SUSPICIOUS"},
            {"field": "security.risk_score", "operator": "gte", "value": 60},
        ],
        "condition_logic": "AND",
        "actions": [
            {"type": "quarantine", "params": {}},
            {"type": "notify", "params": {"recipient": "admin", "message": "Email in quarantena: score >= 60"}},
        ],
        "stop_processing": False,
    },
    {
        "name": "Auto-tag spam emails",
        "priority": 3,
        "conditions": [
            {"field": "content.category", "operator": "eq", "value": "spam"}
        ],
        "condition_logic": "AND",
        "actions": [
            {"type": "tag", "params": {"tags": ["spam", "auto-detected"]}},
            {"type": "quarantine", "params": {}},
        ],
        "stop_processing": True,
    },
    {
        "name": "Tag invoices",
        "priority": 10,
        "conditions": [
            {"field": "content.category", "operator": "eq", "value": "invoice"}
        ],
        "condition_logic": "AND",
        "actions": [
            {"type": "tag", "params": {"tags": ["invoice", "accounting"]}},
        ],
        "stop_processing": False,
    },
    {
        "name": "Tag support tickets",
        "priority": 10,
        "conditions": [
            {"field": "content.category", "operator": "eq", "value": "support"}
        ],
        "condition_logic": "AND",
        "actions": [
            {"type": "tag", "params": {"tags": ["support", "ticket"]}},
        ],
        "stop_processing": False,
    },
]


def main():
    conn = get_connection()
    cursor = conn.cursor()

    # Verifica se ci sono gia regole
    cursor.execute("SELECT COUNT(*) FROM routing_rules")
    count = cursor.fetchone()[0]

    if count > 0:
        print(f"Ci sono gia {count} regole nel DB. Vuoi sovrascrivere? (skip)")
        cursor.close()
        conn.close()
        return

    for rule in INITIAL_RULES:
        sql = """
            INSERT INTO routing_rules
                (name, priority, conditions, condition_logic, actions, stop_processing, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            rule["name"],
            rule["priority"],
            json.dumps(rule["conditions"]),
            rule["condition_logic"],
            json.dumps(rule["actions"]),
            rule["stop_processing"],
            "system_seed",
        )
        cursor.execute(sql, values)

    conn.commit()
    print(f"Inserite {len(INITIAL_RULES)} regole di routing.")

    # Mostra riepilogo
    cursor.execute("SELECT id, name, priority, enabled FROM routing_rules ORDER BY priority")
    for row in cursor.fetchall():
        print(f"  [{row[0]}] P{row[2]} - {row[1]} (enabled: {row[3]})")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
