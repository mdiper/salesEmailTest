import re

from bs4 import BeautifulSoup

from src.utils.logger import logger

# Pattern per rilevare testo citato nelle email
QUOTE_PATTERNS = [
    re.compile(r"^>+\s?", re.MULTILINE),
    re.compile(r"^On .+ wrote:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,}\s*Original Message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,}\s*Messaggio Originale\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,}\s*Forwarded message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Il .+ ha scritto:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Da:\s+.+$", re.MULTILINE),
    re.compile(r"^From:\s+.+$", re.MULTILINE),
    re.compile(r"^\s*_{3,}\s*$", re.MULTILINE),
]

# Pattern che segna l'inizio della sezione citata (tutto cio' che segue viene rimosso)
QUOTE_START_PATTERNS = [
    re.compile(r"^On .+ wrote:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,}\s*Original Message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,}\s*Messaggio Originale\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^-{3,}\s*Forwarded message\s*-{3,}", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Il .+ ha scritto:\s*$", re.MULTILINE | re.IGNORECASE),
]


class EmailPreprocessor:
    """Preprocessa il contenuto email: strip HTML, normalizza, rimuove citazioni."""

    def process(self, email_data: dict) -> str:
        """Orchestratore: esegue i 3 step di preprocessing.

        Args:
            email_data: dict con 'body_html' e/o 'body_text'

        Returns:
            Testo pulito pronto per analisi di contenuto.
        """
        body_html = email_data.get("body_html") or ""
        body_text = email_data.get("body_text") or ""

        # Step 1: estrai testo da HTML oppure usa body_text
        if body_html:
            text = self._strip_html(body_html)
        else:
            text = body_text

        # Se HTML ha prodotto poco contenuto, prova body_text
        if len(text.strip()) < 20 and body_text and len(body_text.strip()) > len(text.strip()):
            text = body_text

        # Step 2: rimuovi testo citato
        text = self._remove_quoted_text(text)

        # Step 3: normalizza whitespace
        text = self._normalize_whitespace(text)

        logger.debug(
            "email_preprocessed",
            input_html_len=len(body_html),
            input_text_len=len(body_text),
            output_len=len(text),
        )

        return text

    def _strip_html(self, html: str) -> str:
        """Rimuove HTML e restituisce testo puro.
        Elimina tag script, style, head prima dell'estrazione."""
        soup = BeautifulSoup(html, "html.parser")

        # Rimuovi tag non testuali
        for tag in soup.find_all(["script", "style", "head", "meta", "link"]):
            tag.decompose()

        # Estrai testo con separatori per tag blocco
        text = soup.get_text(separator="\n")

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalizza whitespace: spazi multipli, tab, righe vuote eccessive."""
        # Tab -> spazio
        text = text.replace("\t", " ")

        # Spazi multipli su stessa riga -> spazio singolo
        text = re.sub(r"[^\S\n]+", " ", text)

        # Righe vuote multiple -> massimo una riga vuota
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Strip righe singole
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Strip finale
        text = text.strip()

        return text

    def _remove_quoted_text(self, text: str) -> str:
        """Rimuove il testo citato (reply thread, forward).
        Tronca tutto il contenuto dopo il marker di citazione."""
        # Cerca il primo marker di inizio citazione e tronca
        earliest_pos = len(text)

        for pattern in QUOTE_START_PATTERNS:
            match = pattern.search(text)
            if match and match.start() < earliest_pos:
                earliest_pos = match.start()

        if earliest_pos < len(text):
            text = text[:earliest_pos]

        # Rimuovi righe che iniziano con ">" (citazione inline)
        lines = text.split("\n")
        clean_lines = []
        for line in lines:
            if re.match(r"^>+\s?", line):
                continue
            clean_lines.append(line)

        return "\n".join(clean_lines)
