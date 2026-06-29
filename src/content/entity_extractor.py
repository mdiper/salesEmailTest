import re

from src.utils.logger import logger

# Pattern per importi monetari
AMOUNT_PATTERNS = [
    re.compile(r"[\u20ac$\u00a3]\s*[\d.,]+(?:\s*(?:EUR|USD|GBP))?", re.IGNORECASE),
    re.compile(r"[\d.,]+\s*(?:EUR|USD|GBP|CHF|\u20ac|\$|\u00a3)", re.IGNORECASE),
    re.compile(r"(?:euro|dollari|sterline)\s*[\d.,]+", re.IGNORECASE),
    re.compile(r"[\d.,]+\s*(?:euro|dollari|sterline)", re.IGNORECASE),
]

# Pattern per riferimenti (fatture, ordini, ticket)
REFERENCE_PATTERNS = [
    (re.compile(r"(?:fattura|invoice|fatt\.?)\s*(?:n\.?|nr\.?|numero|#)\s*[\w/\-]+", re.IGNORECASE), "invoice"),
    (re.compile(r"(?:ordine|order)\s*(?:n\.?|nr\.?|numero|#)\s*[\w/\-]+", re.IGNORECASE), "order"),
    (re.compile(r"(?:ticket|case)\s*[#:]\s*[\w\-]+", re.IGNORECASE), "ticket"),
    (re.compile(r"(?:preventivo|quotation|quote)\s*(?:n\.?|nr\.?|#)\s*[\w/\-]+", re.IGNORECASE), "quote"),
    (re.compile(r"(?:DDT|bolla)\s*(?:n\.?|nr\.?|#)\s*[\w/\-]+", re.IGNORECASE), "shipping"),
    (re.compile(r"(?:PO|purchase order)\s*(?:n\.?|#)\s*[\w/\-]+", re.IGNORECASE), "purchase_order"),
    (re.compile(r"\b[A-Z]{2,4}[-/]\d{4,}\b"), "code"),
]

# Pattern per date
DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
]

# Pattern per email
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")

# Pattern per numeri di telefono
PHONE_PATTERN = re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}")


class EntityExtractor:
    """Estrae entita' (persone, organizzazioni, date, importi, riferimenti) dal testo email."""

    def __init__(self):
        self._nlp = None

    def extract(self, text: str) -> dict:
        """Orchestratore: esegue tutte le estrazioni.

        Returns:
            dict con persons, organizations, dates, amounts, references, emails, phones
        """
        if not text or len(text.strip()) < 5:
            return self._empty_result()

        result = {
            "persons": [],
            "organizations": [],
            "dates": self._extract_dates(text),
            "amounts": self._extract_amounts(text),
            "references": self._extract_references(text),
            "emails": self._extract_emails(text),
            "phones": self._extract_phones(text),
        }

        # NER con spaCy (se disponibile)
        nlp = self._get_nlp()
        if nlp:
            ner_entities = self._extract_with_spacy(nlp, text)
            result["persons"] = ner_entities.get("persons", [])
            result["organizations"] = ner_entities.get("organizations", [])

        logger.debug(
            "entities_extracted",
            persons=len(result["persons"]),
            organizations=len(result["organizations"]),
            dates=len(result["dates"]),
            amounts=len(result["amounts"]),
            references=len(result["references"]),
        )

        return result

    def _extract_amounts(self, text: str) -> list[dict]:
        """Estrae importi monetari dal testo."""
        amounts = []
        seen = set()

        for pattern in AMOUNT_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(0).strip()
                if raw not in seen:
                    seen.add(raw)
                    amounts.append({
                        "raw": raw,
                        "value": self._parse_amount_value(raw),
                        "currency": self._detect_currency(raw),
                    })

        return amounts

    def _extract_references(self, text: str) -> list[dict]:
        """Estrae numeri di fattura, ordine, ticket, ecc."""
        references = []
        seen = set()

        for pattern, ref_type in REFERENCE_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(0).strip()
                if raw not in seen:
                    seen.add(raw)
                    references.append({
                        "raw": raw,
                        "type": ref_type,
                    })

        return references

    def _extract_dates(self, text: str) -> list[str]:
        """Estrae date dal testo."""
        dates = []
        seen = set()

        for pattern in DATE_PATTERNS:
            for match in pattern.finditer(text):
                raw = match.group(0).strip()
                if raw not in seen:
                    seen.add(raw)
                    dates.append(raw)

        return dates

    def _extract_emails(self, text: str) -> list[str]:
        """Estrae indirizzi email dal testo."""
        return list(set(EMAIL_PATTERN.findall(text)))

    def _extract_phones(self, text: str) -> list[str]:
        """Estrae numeri di telefono dal testo."""
        phones = []
        for match in PHONE_PATTERN.finditer(text):
            phone = match.group(0).strip()
            # Filtra falsi positivi (troppo corti o solo numeri generici)
            digits = re.sub(r"\D", "", phone)
            if 7 <= len(digits) <= 15:
                phones.append(phone)
        return list(set(phones))

    def _extract_with_spacy(self, nlp, text: str) -> dict:
        """Estrae PER e ORG con spaCy NER."""
        doc = nlp(text[:5000])  # Limita a 5000 chars per performance

        persons = []
        organizations = []

        for ent in doc.ents:
            if ent.label_ == "PER" and ent.text not in persons:
                persons.append(ent.text)
            elif ent.label_ == "ORG" and ent.text not in organizations:
                organizations.append(ent.text)

        return {"persons": persons, "organizations": organizations}

    def _get_nlp(self):
        """Carica modello spaCy (cache). Restituisce None se non disponibile."""
        if self._nlp is not None:
            return self._nlp

        try:
            import spacy
            self._nlp = spacy.load("it_core_news_lg")
            return self._nlp
        except (ImportError, OSError):
            return None

    def _parse_amount_value(self, raw: str) -> float | None:
        """Prova a parsare il valore numerico dall'importo."""
        # Rimuovi simboli valuta e testo
        cleaned = re.sub(r"[^\d.,]", "", raw)
        if not cleaned:
            return None

        # Gestisci formato europeo (1.234,56) vs americano (1,234.56)
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                # Formato europeo: 1.234,56
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                # Formato americano: 1,234.56
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # Solo virgola: potrebbe essere decimale europeo
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _detect_currency(self, raw: str) -> str:
        """Rileva la valuta dall'importo raw."""
        raw_upper = raw.upper()
        if "\u20ac" in raw or "EUR" in raw_upper or "EURO" in raw_upper:
            return "EUR"
        if "$" in raw or "USD" in raw_upper or "DOLLAR" in raw_upper:
            return "USD"
        if "\u00a3" in raw or "GBP" in raw_upper or "STERLIN" in raw_upper:
            return "GBP"
        if "CHF" in raw_upper:
            return "CHF"
        return "EUR"  # Default per contesto italiano

    def _empty_result(self) -> dict:
        return {
            "persons": [],
            "organizations": [],
            "dates": [],
            "amounts": [],
            "references": [],
            "emails": [],
            "phones": [],
        }
