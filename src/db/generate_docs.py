"""
Genera documentazione del database: struttura tabelle + prime 5 righe per ciascuna.
Salva in src/db/docs/db_salesemailtool.md
Uso: python -m src.db.generate_docs
"""

import sys
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.utils.config import config

DOCS_DIR = Path(__file__).resolve().parent / "docs"
OUTPUT_FILE = DOCS_DIR / "db_salesemailtool.md"


def generate():
    DOCS_DIR.mkdir(exist_ok=True)

    connection = mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
    )
    cursor = connection.cursor()

    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    lines = []
    lines.append(f"# Database: {config.DB_NAME}")
    lines.append(f"")
    lines.append(f"Tabelle totali: {len(tables)}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    for table in tables:
        lines.append(f"## {table}")
        lines.append(f"")

        # Struttura
        cursor.execute(f"DESCRIBE `{table}`")
        columns = cursor.fetchall()
        lines.append(f"| Campo | Tipo | Null | Key | Default | Extra |")
        lines.append(f"|-------|------|------|-----|---------|-------|")
        for col in columns:
            field, col_type, null, key, default, extra = col
            lines.append(f"| {field} | {col_type} | {null} | {key} | {default} | {extra} |")
        lines.append(f"")

        # Prime 5 righe
        cursor.execute(f"SELECT * FROM `{table}` LIMIT 5")
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]

        if rows:
            lines.append(f"**Dati (prime {len(rows)} righe):**")
            lines.append(f"")
            lines.append(f"| {' | '.join(col_names)} |")
            lines.append(f"| {'|'.join(['---' for _ in col_names])} |")
            for row in rows:
                values = []
                for v in row:
                    s = str(v) if v is not None else "NULL"
                    if len(s) > 60:
                        s = s[:57] + "..."
                    s = s.replace("|", "\\|").replace("\n", " ")
                    values.append(s)
                lines.append(f"| {' | '.join(values)} |")
        else:
            lines.append(f"*Tabella vuota.*")

        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    cursor.close()
    connection.close()

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Documentazione generata: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate()
