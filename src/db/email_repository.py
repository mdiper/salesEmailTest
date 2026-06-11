import json
from datetime import datetime
from email.utils import parsedate_to_datetime, getaddresses

from mysql.connector import Error as MySQLError

from src.db.connection import get_connection
from src.utils.logger import logger


class EmailRepository:
    """Repository per operazioni CRUD sulla tabella emails e email_headers."""

    def save_email(self, parsed_data: dict, account_id: int) -> int:
        """INSERT nella tabella emails (skip se message_id gia' presente).
        Restituisce l'id (nuovo o esistente)."""
        message_id = parsed_data.get("message_id", "")
        to_list = self._parse_address_list(parsed_data.get("to", ""))
        cc_list = self._parse_address_list(parsed_data.get("cc", ""))

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT id FROM emails WHERE message_id = %s", (message_id,)
            )
            existing = cursor.fetchone()
            if existing:
                logger.info("email_already_exists", email_id=existing[0], message_id=message_id[:40])
                return existing[0]

            cursor.execute(
                """INSERT INTO emails
                   (message_id, account_id, from_address, from_display,
                    to_addresses, cc_addresses, subject, date_sent,
                    body_text, body_html, raw_size_bytes, has_attachments, processing_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    message_id,
                    account_id,
                    self._extract_address(parsed_data.get("from", "")),
                    parsed_data.get("from", ""),
                    json.dumps(to_list),
                    json.dumps(cc_list),
                    parsed_data.get("subject", ""),
                    self._parse_date(parsed_data.get("date", "")),
                    parsed_data.get("body_text"),
                    parsed_data.get("body_html"),
                    self._calc_size(parsed_data),
                    len(parsed_data.get("attachments", [])) > 0,
                    "pending",
                )
            )
            connection.commit()
            email_id = cursor.lastrowid
            logger.info("email_saved", email_id=email_id, message_id=message_id[:40])
            return email_id

        except MySQLError as e:
            connection.rollback()
            logger.error("email_save_failed", error=str(e), message_id=message_id)
            raise
        finally:
            cursor.close()
            connection.close()

    def save_headers(self, email_id: int, headers_dict: dict) -> int:
        """INSERT multiplo nella tabella email_headers. Restituisce il numero di header salvati."""
        connection = get_connection()
        cursor = connection.cursor()
        count = 0

        try:
            for name, value in headers_dict.items():
                values_list = value if isinstance(value, list) else [value]
                for v in values_list:
                    cursor.execute(
                        """INSERT INTO email_headers (email_id, header_name, header_value)
                           VALUES (%s, %s, %s)""",
                        (email_id, name, str(v)[:65535])
                    )
                    count += 1

            connection.commit()
            logger.info("headers_saved", email_id=email_id, count=count)
            return count

        except MySQLError as e:
            connection.rollback()
            logger.error("headers_save_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            connection.close()

    def update_status(self, email_id: int, status: str) -> None:
        """Aggiorna il processing_status di un'email (pending/processing/completed/failed)."""
        valid_statuses = ("pending", "processing", "completed", "failed")
        if status not in valid_statuses:
            raise ValueError(f"Status '{status}' non valido. Deve essere uno tra: {valid_statuses}")

        connection = get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "UPDATE emails SET processing_status = %s WHERE id = %s",
                (status, email_id)
            )
            connection.commit()
            logger.info("email_status_updated", email_id=email_id, status=status)
        except MySQLError as e:
            connection.rollback()
            logger.error("email_status_update_failed", email_id=email_id, error=str(e))
            raise
        finally:
            cursor.close()
            connection.close()

    def _parse_address_list(self, field: str) -> list[str]:
        """Parsing robusto di indirizzi email multipli usando email.utils.getaddresses."""
        if not field:
            return []
        addresses = getaddresses([field])
        return [f"{name} <{addr}>" if name else addr for name, addr in addresses if addr]

    def _extract_address(self, from_field: str) -> str:
        """Estrae solo l'indirizzo email da un campo From."""
        if "<" in from_field and ">" in from_field:
            return from_field.split("<")[1].split(">")[0]
        return from_field.strip()

    def _parse_date(self, date_str: str) -> datetime | None:
        """Converte la data RFC 2822 in datetime MySQL-compatibile."""
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            return None

    def _calc_size(self, parsed_data: dict) -> int:
        """Calcola dimensione approssimativa dell'email in bytes."""
        size = 0
        if parsed_data.get("body_text"):
            size += len(parsed_data["body_text"].encode("utf-8", errors="replace"))
        if parsed_data.get("body_html"):
            size += len(parsed_data["body_html"].encode("utf-8", errors="replace"))
        for att in parsed_data.get("attachments", []):
            size += att.get("size", 0)
        return size
