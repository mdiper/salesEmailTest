import re
from pathlib import Path

from mysql.connector import Error as MySQLError

from src.db.connection import get_connection
from src.security.constants import DANGEROUS_EXTENSIONS
from src.utils.logger import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "attachments"


class AttachmentStorage:
    """Gestisce metadata allegati e download condizionato post-security-check."""

    def __init__(self, base_dir: Path = BASE_DIR):
        self._base_dir = base_dir

    def save_metadata(self, email_id: int, attachment: dict) -> int:
        """Salva solo i metadata dell'allegato nel DB.
        Se l'estensione e' pericolosa, marca come 'blocked'.
        Restituisce l'id generato."""
        filename = attachment["filename"]
        scan_status = self._determine_scan_status(filename)

        if scan_status == "blocked":
            logger.warning(
                "attachment_blocked_dangerous_extension",
                email_id=email_id,
                filename=filename,
                extension=Path(filename).suffix.lower(),
            )

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """INSERT INTO email_attachments
                   (email_id, filename, content_type, size_bytes,
                    hash_sha256, storage_path, scan_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    email_id,
                    filename,
                    attachment["content_type"],
                    attachment["size"],
                    attachment["hash_sha256"],
                    None,  # storage_path resta NULL fino al download post-security-check
                    scan_status,
                ),
            )
            connection.commit()
            att_id = cursor.lastrowid
            logger.info(
                "attachment_metadata_saved",
                attachment_id=att_id,
                email_id=email_id,
                filename=filename,
                scan_status=scan_status,
            )
            return att_id

        except MySQLError as e:
            connection.rollback()
            logger.error(
                "attachment_metadata_failed",
                email_id=email_id,
                filename=filename,
                error=str(e),
            )
            raise
        finally:
            cursor.close()
            connection.close()

    def save_to_disk(self, email_id: int, attachment: dict) -> str:
        """Salva il file su disco. Da usare SOLO dopo security check positivo.
        Restituisce il path relativo."""
        self._base_dir.mkdir(parents=True, exist_ok=True)
        folder = self._base_dir / str(email_id)
        folder.mkdir(parents=True, exist_ok=True)

        filename = self._safe_filename(attachment["filename"])
        dest = folder / filename

        counter = 1
        while dest.exists():
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            dest = folder / f"{stem}_{counter}{suffix}"
            counter += 1

        dest.write_bytes(attachment["raw_bytes"])
        rel_path = dest.relative_to(self._base_dir).as_posix()
        logger.info(
            "attachment_saved_to_disk",
            email_id=email_id,
            filename=filename,
            size=len(attachment["raw_bytes"]),
            path=rel_path,
        )
        return rel_path

    def _determine_scan_status(self, filename: str) -> str:
        """Determina lo scan_status iniziale basandosi sull'estensione."""
        ext = Path(filename).suffix.lower()
        if ext in DANGEROUS_EXTENSIONS:
            return "blocked"
        return "pending_scan"

    def _safe_filename(self, filename: str) -> str:
        """Rimuove caratteri pericolosi dal nome file."""
        filename = filename.replace("/", "_").replace("\\", "_")
        filename = re.sub(r'[<>:"|?*\x00-\x1f]', "_", filename)
        return filename.strip(". ") or "unnamed"
