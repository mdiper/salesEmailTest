"""
SalesEmailTool - Entry point.
Avvia il servizio di ingestion email con polling periodico.
"""

import sys
import time
import schedule

from src.utils.config import config, Config
from src.utils.logger import logger
from src.db.connection import test_connection
from src.ingestion.service import IngestionService


def main():
    logger.info("application_starting", version="0.1.0")

    # Validazione variabili d'ambiente
    missing = Config.validate()
    if missing:
        logger.warning(
            "missing_env_vars",
            missing=missing,
            message="Alcune variabili non sono configurate.",
        )

    # Test connessione database
    logger.info("testing_database_connection")
    if test_connection():
        logger.info("database_connection_ok")
    else:
        logger.error("database_connection_failed", message="Impossibile connettersi al database. Verificare .env")
        sys.exit(1)

    # Inizializza servizio di ingestion
    service = IngestionService()
    logger.info(
        "application_ready",
        db_host=config.DB_HOST,
        db_name=config.DB_NAME,
        imap_host=config.IMAP_HOST,
        poll_interval=config.POLL_INTERVAL_SECONDS,
    )

    # Configura polling periodico
    schedule.every(config.POLL_INTERVAL_SECONDS).seconds.do(service.run_poll)

    # Esegui primo poll immediatamente
    service.run_poll()

    # Loop principale
    logger.info("polling_loop_started", interval_seconds=config.POLL_INTERVAL_SECONDS)
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("application_stopping")
        service.stop()
        logger.info("application_stopped")


if __name__ == "__main__":
    main()
