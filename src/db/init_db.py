"""
Esegue init_schema.sql su MySQL per creare tutte le tabelle.
Uso: python -m src.db.init_db
"""

import sys
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.config import config
from src.utils.logger import logger

SCHEMA_FILE = Path(__file__).resolve().parent / "init_schema.sql"


def run_schema():
    """Legge init_schema.sql e lo esegue statement per statement."""
    if not SCHEMA_FILE.exists():
        logger.error("schema_file_not_found", path=str(SCHEMA_FILE))
        sys.exit(1)

    sql_content = SCHEMA_FILE.read_text(encoding="utf-8")

    # Rimuovi righe di commento
    lines = []
    for line in sql_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    clean_sql = "\n".join(lines)

    statements = [s.strip() for s in clean_sql.split(";") if s.strip()]

    try:
        connection = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
        )
        cursor = connection.cursor()

        for statement in statements:
            if not statement:
                continue
            try:
                cursor.execute(statement)
                connection.commit()
                logger.info("sql_executed", statement=statement[:80])
            except MySQLError as e:
                logger.warning("sql_statement_failed", error=str(e), statement=statement[:80])

        cursor.close()
        connection.close()

        logger.info("schema_initialization_complete")

    except MySQLError as e:
        logger.error("schema_initialization_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    run_schema()
