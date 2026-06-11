from src.utils.config import config
from src.utils.logger import logger
from src.ingestion.imap_client import IMAPClient
from src.ingestion.mime_parser import MIMEParser
from src.db.email_repository import EmailRepository
from src.db.connection import get_connection
from src.ingestion.attachment_storage import AttachmentStorage


class IngestionService:
    """Orchestratore: IMAPClient -> MIMEParser -> EmailRepository + AttachmentStorage.
    Gestisce il flusso completo: fetch, parsing, salvataggio, aggiornamento status."""

    def __init__(self):
        self.client = IMAPClient(
            host=config.IMAP_HOST,
            port=config.IMAP_PORT,
            username=config.IMAP_USERNAME,
            password=config.IMAP_PASSWORD,
        )
        self.parser = MIMEParser()
        self.repo = EmailRepository()
        self.storage = AttachmentStorage()
        self._account_id: int | None = None

    @property
    def account_id(self) -> int:
        if self._account_id is None:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM accounts WHERE email_address = %s",
                (config.IMAP_USERNAME,)
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if not row:
                raise RuntimeError(
                    f"Account '{config.IMAP_USERNAME}' non trovato in DB. "
                    "Eseguire: python -m src.db.seed_account"
                )
            self._account_id = row[0]
        return self._account_id

    def run_poll(self) -> int:
        """Esegue un ciclo di polling: fetch email non lette, processa e salva.
        Restituisce il numero di email processate."""
        if not self.client.is_connected:
            self.client.connect()

        raw_emails = self.client.poll()
        if not raw_emails:
            return 0

        processed = 0
        for raw in raw_emails:
            try:
                self._process_single_email(raw)
                processed += 1
            except Exception as e:
                logger.error("ingestion_email_failed", error=str(e))

        logger.info("ingestion_poll_cycle_complete", processed=processed, total=len(raw_emails))
        return processed

    def run_idle(self) -> None:
        """Avvia IMAP IDLE per ascolto continuo con processing automatico."""
        if not self.client.is_connected:
            self.client.connect()

        self.client.idle_listen(on_new_email=self._on_new_emails)

    def stop(self) -> None:
        """Ferma il servizio (IDLE + disconnessione)."""
        self.client.stop_idle()
        self.client.disconnect()

    def _on_new_emails(self, raw_emails: list[bytes]) -> None:
        """Callback per IDLE: processa le nuove email ricevute."""
        for raw in raw_emails:
            try:
                self._process_single_email(raw)
            except Exception as e:
                logger.error("ingestion_email_failed", error=str(e))

    def _process_single_email(self, raw: bytes) -> int:
        """Processa una singola email: parse -> save -> attachments -> status update.
        Restituisce l'email_id."""
        parsed = self.parser.parse(raw)

        # Salva email (status: pending)
        email_id = self.repo.save_email(parsed, self.account_id)

        # Aggiorna status a processing
        self.repo.update_status(email_id, "processing")

        try:
            # Salva headers
            self.repo.save_headers(email_id, parsed["headers"])

            # Salva solo metadata allegati (nessun download su disco)
            for att in parsed.get("attachments", []):
                self.storage.save_metadata(email_id, att)

            # Completato
            self.repo.update_status(email_id, "completed")
            logger.info(
                "ingestion_email_processed",
                email_id=email_id,
                subject=parsed.get("subject", "")[:60],
                attachments=len(parsed.get("attachments", [])),
            )

        except Exception as e:
            self.repo.update_status(email_id, "failed")
            logger.error("ingestion_processing_failed", email_id=email_id, error=str(e))
            raise

        return email_id
