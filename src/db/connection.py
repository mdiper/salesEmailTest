import mysql.connector
from mysql.connector import Error as MySQLError
from src.utils.config import config
from src.utils.logger import logger


def get_connection():
    """Crea e restituisce una connessione MySQL usando i parametri da config."""
    try:
        connection = mysql.connector.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
        )
        if connection.is_connected():
            logger.info(
                "database_connected",
                host=config.DB_HOST,
                database=config.DB_NAME,
            )
        return connection
    except MySQLError as e:
        logger.error("database_connection_failed", error=str(e))
        raise


def test_connection() -> bool:
    """Testa la connessione al database. Restituisce True se OK."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return True
    except MySQLError:
        return False
