import email
import hashlib
from email.header import decode_header
from email.policy import default as default_policy


class MIMEParser:
    """Parser completo di email MIME: header, body, allegati."""

    def parse(self, raw_bytes: bytes) -> dict:
        """Parsing completo di un'email raw in un dizionario strutturato."""
        msg = email.message_from_bytes(raw_bytes, policy=default_policy)

        return {
            "message_id": msg["Message-ID"] or "",
            "from": self._decode_field(msg["From"]),
            "to": self._decode_field(msg["To"]),
            "cc": self._decode_field(msg["Cc"]),
            "subject": self._decode_field(msg["Subject"]),
            "date": msg["Date"] or "",
            "headers": self._extract_headers(msg),
            "body_text": self._extract_body(msg, "text/plain"),
            "body_html": self._extract_body(msg, "text/html"),
            "attachments": self._extract_attachments(msg),
        }

    def _decode_field(self, field) -> str:
        """Decodifica un header field che potrebbe essere encoded (RFC 2047)."""
        if field is None:
            return ""
        decoded_parts = decode_header(str(field))
        result = ""
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(charset or "utf-8", errors="replace")
            else:
                result += part
        return result

    def _extract_headers(self, msg) -> dict:
        """Estrae tutti gli header come dizionario chiave-valore."""
        headers = {}
        for key, value in msg.items():
            if key in headers:
                existing = headers[key]
                if isinstance(existing, list):
                    existing.append(str(value))
                else:
                    headers[key] = [existing, str(value)]
            else:
                headers[key] = str(value)
        return headers

    def _extract_body(self, msg, content_type: str) -> str | None:
        """Walk delle parti MIME, estrae il body del content_type specificato."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == content_type:
                    charset = part.get_content_charset() or "utf-8"
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(charset, errors="replace")
        else:
            if msg.get_content_type() == content_type:
                charset = msg.get_content_charset() or "utf-8"
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors="replace")
        return None

    def _extract_attachments(self, msg) -> list[dict]:
        """Estrae i metadata degli allegati (no raw bytes in memoria)."""
        attachments = []
        for part in msg.walk():
            content_disposition = part.get_content_disposition()
            if content_disposition not in ("attachment", "inline"):
                continue

            filename = part.get_filename()
            if not filename:
                continue

            filename = self._decode_field(filename)
            payload = part.get_payload(decode=True)

            if payload is None:
                continue

            attachments.append({
                "filename": filename,
                "content_type": part.get_content_type(),
                "size": len(payload),
                "hash_sha256": hashlib.sha256(payload).hexdigest(),
            })
            # raw_bytes non viene conservato: risparmia memoria
            # e previene salvataggio accidentale di file malevoli

        return attachments
