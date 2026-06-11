import imaplib
import select
import time
from typing import Callable

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.utils.logger import logger


class IMAPClient:
    """Client IMAP per connessione, polling e gestione della mailbox."""

    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self._connection: imaplib.IMAP4_SSL | None = None

    def connect(self) -> None:
        """Connessione IMAP4_SSL, login con credenziali, selezione INBOX."""
        try:
            self._connection = imaplib.IMAP4_SSL(self.host, self.port)
            self._connection.login(self.username, self.password)
            self._connection.select("INBOX")
            logger.info(
                "imap_connected",
                host=self.host,
                user=self.username,
            )
        except imaplib.IMAP4.error as e:
            logger.error("imap_login_failed", host=self.host, error=str(e))
            self._connection = None
            raise
        except OSError as e:
            logger.error("imap_connection_failed", host=self.host, error=str(e))
            self._connection = None
            raise

    def disconnect(self) -> None:
        """Logout e chiusura connessione sicura."""
        if self._connection is None:
            return
        try:
            self._connection.close()
            self._connection.logout()
            logger.info("imap_disconnected", host=self.host)
        except imaplib.IMAP4.error as e:
            logger.warning("imap_disconnect_warning", error=str(e))
        finally:
            self._connection = None

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, max=60),
        retry=retry_if_exception_type((imaplib.IMAP4.error, OSError, ConnectionError)),
        before_sleep=lambda retry_state: logger.warning(
            "imap_poll_retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep,
        ),
    )
    def poll(self) -> list[bytes]:
        """Cerca email non lette (UNSEEN), fetch RFC822, restituisce lista di raw bytes.
        Retry automatico con exponential backoff (max 5 tentativi)."""
        if self._connection is None:
            raise ConnectionError("IMAP non connesso. Chiamare connect() prima di poll().")

        status, messages = self._connection.search(None, "UNSEEN")
        if status != "OK":
            raise imaplib.IMAP4.error(f"Search failed with status: {status}")

        msg_ids = messages[0].split()
        if not msg_ids:
            logger.info("imap_poll_no_new_emails")
            return []

        results = []
        for msg_id in msg_ids:
            status, data = self._connection.fetch(msg_id, "(RFC822)")
            if status == "OK" and data[0] is not None:
                results.append(data[0][1])
            else:
                logger.warning("imap_fetch_failed", msg_id=msg_id.decode())

        logger.info("imap_poll_complete", count=len(results))
        return results

    def idle_listen(self, on_new_email: Callable[[list[bytes]], None] | None = None) -> None:
        """IMAP IDLE: ascolto continuo, trigger poll() quando arriva un nuovo messaggio.
        Riconnessione automatica con backoff se la connessione cade.
        
        Args:
            on_new_email: callback opzionale chiamata con la lista di raw bytes delle nuove email.
                          Se None, esegue solo poll() e logga.
        """
        if self._connection is None:
            raise ConnectionError("IMAP non connesso. Chiamare connect() prima di idle_listen().")

        self._idle_running = True
        reconnect_attempts = 0
        max_reconnect_attempts = 10
        logger.info("imap_idle_started", host=self.host)

        while self._idle_running:
            try:
                # Invia comando IDLE
                tag = self._connection._new_tag().decode()
                self._connection.send(f"{tag} IDLE\r\n".encode())

                # Leggi la continuation response (+ idling)
                response = self._connection.readline()
                if not response.startswith(b"+"):
                    logger.warning("imap_idle_no_continuation", response=response.decode(errors="replace"))
                    raise OSError("Server did not accept IDLE command")

                # Attendi eventi sul socket (check ogni 5s per permettere Ctrl+C)
                sock = self._connection.socket()
                readable = None
                line = b""
                idle_timeout = 1740  # 29 min per RFC 2177
                elapsed = 0
                while elapsed < idle_timeout and self._idle_running:
                    readable, _, _ = select.select([sock], [], [], 5)
                    if readable:
                        line = self._connection.readline()
                        logger.info("imap_idle_event", data=line.decode(errors="replace").strip())
                        break
                    elapsed += 5

                if not self._idle_running:
                    self._connection.send(b"DONE\r\n")
                    break

                # Termina IDLE
                self._connection.send(b"DONE\r\n")

                # Leggi la risposta al DONE fino a trovare il tag
                while True:
                    done_response = self._connection.readline()
                    if done_response.startswith(tag.encode()):
                        break

                if readable and (b"EXISTS" in line or b"RECENT" in line):
                    logger.info("imap_idle_new_email_detected")
                    new_emails = self.poll()
                    if new_emails and on_new_email:
                        on_new_email(new_emails)

                # Reset reconnect counter on success
                reconnect_attempts = 0

            except (imaplib.IMAP4.error, OSError) as e:
                logger.error("imap_idle_error", error=str(e))

                if not self._idle_running:
                    break

                reconnect_attempts += 1
                if reconnect_attempts > max_reconnect_attempts:
                    logger.error("imap_idle_max_reconnects_reached", attempts=reconnect_attempts)
                    break

                wait_seconds = min(2 ** reconnect_attempts, 300)
                logger.info(
                    "imap_idle_reconnecting",
                    attempt=reconnect_attempts,
                    wait_seconds=wait_seconds,
                )
                time.sleep(wait_seconds)

                try:
                    self.disconnect()
                    self.connect()
                    logger.info("imap_idle_reconnected", attempt=reconnect_attempts)
                except (imaplib.IMAP4.error, OSError) as reconnect_err:
                    logger.error("imap_idle_reconnect_failed", error=str(reconnect_err))
                    continue

        logger.info("imap_idle_stopped")

    def stop_idle(self) -> None:
        """Ferma il loop IDLE."""
        self._idle_running = False

    @property
    def is_connected(self) -> bool:
        """Verifica se la connessione è attiva."""
        if self._connection is None:
            return False
        try:
            status, _ = self._connection.noop()
            return status == "OK"
        except (imaplib.IMAP4.error, OSError):
            return False
