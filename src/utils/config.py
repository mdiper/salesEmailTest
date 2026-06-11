import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

REQUIRED_VARS = [
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "IMAP_HOST",
    "IMAP_PORT",
    "IMAP_USERNAME",
    "IMAP_PASSWORD",
]


class Config:
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "sales_email_tool")

    IMAP_HOST: str = os.getenv("IMAP_HOST", "")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USERNAME: str = os.getenv("IMAP_USERNAME", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ATTACHMENTS_DIR: Path = BASE_DIR / os.getenv("ATTACHMENTS_DIR", "data/attachments")
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))

    @classmethod
    def validate(cls) -> list[str]:
        """Verifica che tutte le variabili obbligatorie siano valorizzate.
        Restituisce la lista di quelle mancanti."""
        missing = []
        for var in REQUIRED_VARS:
            value = os.getenv(var)
            if not value:
                missing.append(var)
        return missing


config = Config()
