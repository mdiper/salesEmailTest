"""
SalesEmailTool - Entry point.
Avvia il servizio di ingestion email con pipeline completa di analisi.
"""

import sys
import time
import schedule

from src.utils.config import config, Config
from src.utils.logger import logger
from src.db.connection import test_connection
from src.ingestion.service import IngestionService
from src.pipeline import EmailPipeline


def main():
    logger.info("application_starting", version="1.0.0")

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

    # Inizializza servizi
    service = IngestionService()
    pipeline = EmailPipeline()

    logger.info(
        "application_ready",
        db_host=config.DB_HOST,
        db_name=config.DB_NAME,
        imap_host=config.IMAP_HOST,
        poll_interval=config.POLL_INTERVAL_SECONDS,
    )

    def poll_and_process():
        """Polling: fetch nuove email, poi pipeline completa per ognuna."""
        if not service.client.is_connected:
            service.client.connect()

        raw_emails = service.client.poll()
        if not raw_emails:
            return

        for raw in raw_emails:
            try:
                # Step 1: Ingestion (parse + save to DB)
                email_id = service._process_single_email(raw)

                # Step 2: Pipeline completa (security + country + content + routing)
                parsed = service.parser.parse(raw)
                pipeline.process(email_id, parsed)

            except Exception as e:
                logger.error("poll_process_failed", error=str(e))

        logger.info("poll_cycle_complete", emails_processed=len(raw_emails))

    # Configura polling periodico
    schedule.every(config.POLL_INTERVAL_SECONDS).seconds.do(poll_and_process)

    # Esegui primo poll immediatamente
    poll_and_process()

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
