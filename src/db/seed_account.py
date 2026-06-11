"""
Inserisce il record dell'account Vianova nella tabella accounts.
Uso: python -m src.db.seed_account
"""

import json
import sys
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.config import config
from src.utils.logger import logger


def seed_vianova_account():
    """Inserisce l'account IMAP Vianova se non esiste gia'."""
    connection_config = json.dumps({
        "host": config.IMAP_HOST,
        "port": config.IMAP_PORT,
        "username": config.IMAP_USERNAME,
        "use_ssl": True,
    })

    try:
        connection = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
        )
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM accounts WHERE email_address = %s",
            (config.IMAP_USERNAME,)
        )
        existing = cursor.fetchone()

        if existing:
            logger.info("account_already_exists", id=existing[0], email=config.IMAP_USERNAME)
            cursor.close()
            connection.close()
            return

        cursor.execute(
            """INSERT INTO accounts (email_address, provider, connection_config, status)
               VALUES (%s, %s, %s, %s)""",
            (config.IMAP_USERNAME, "imap", connection_config, "active")
        )
        connection.commit()
        account_id = cursor.lastrowid
        cursor.close()
        connection.close()

        logger.info("account_created", id=account_id, email=config.IMAP_USERNAME)

    except MySQLError as e:
        logger.error("seed_account_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    seed_vianova_account()
