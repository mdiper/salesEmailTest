import re
from pathlib import Path

import tldextract

from src.country.maps import (
    COUNTRY_TLD_MAP,
    COMPOUND_TLD_MAP,
    PHONE_PREFIX_MAP,
    LANGUAGE_COUNTRY_MAP,
)
from src.utils.logger import logger

GEOIP_DB_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "GeoLite2-Country.mmdb"

# Pesi dei segnali per confidence
SIGNAL_WEIGHTS = {
    "tld": 0.7,
    "phone": 0.8,
    "language": 0.5,
    "ip_geo": 0.6,
    "domain": 0.6,
}


class CountryDetector:
    """Detecta il paese di provenienza di una email combinando segnali multipli."""

    def __init__(self):
        self._geoip_reader = None

    def detect(self, email_data: dict) -> dict:
        """Esegue la country detection completa e restituisce il risultato.

        Args:
            email_data: dict con 'from', 'headers', 'body_text'

        Returns:
            dict con country, country_code, confidence, detection_method, signals
        """
        from_address = email_data.get("from", "")
        headers = email_data.get("headers", {})
        body_text = email_data.get("body_text", "") or ""

        signals = []

        # Signal 1: TLD del dominio email
        tld_signal = self._detect_from_tld(from_address)
        if tld_signal:
            signals.append(tld_signal)

        # Signal 2: Dominio email (per gTLD con dominio locale riconoscibile)
        domain_signal = self._detect_from_domain(from_address)
        if domain_signal:
            signals.append(domain_signal)

        # Signal 3: Prefisso telefonico nella firma
        phone_signal = self._detect_from_phone(body_text)
        if phone_signal:
            signals.append(phone_signal)

        # Signal 4: Lingua del body
        lang_signal = self._detect_language(body_text)
        if lang_signal:
            signals.append(lang_signal)

        # Signal 5: Geolocalizzazione IP
        ip_signal = self._detect_from_ip(headers)
        if ip_signal:
            signals.append(ip_signal)

        # Risoluzione segnali
        result = self._resolve_signals(signals)

        logger.info(
            "country_detection_complete",
            country=result.get("country"),
            country_code=result.get("country_code"),
            confidence=result.get("confidence"),
            method=result.get("detection_method"),
            signals_count=len(signals),
        )

        return result

    def _detect_from_tld(self, from_address: str) -> dict | None:
        """Estrae il TLD dal dominio email e cerca nella mappa ccTLD."""
        email = self._extract_email(from_address)
        if not email:
            return None

        extracted = tldextract.extract(email)
        suffix = extracted.suffix.lower()

        # Controlla TLD composti (co.uk, com.au, ecc.)
        if suffix in COMPOUND_TLD_MAP:
            resolved_tld = COMPOUND_TLD_MAP[suffix]
            if resolved_tld in COUNTRY_TLD_MAP:
                country, code = COUNTRY_TLD_MAP[resolved_tld]
                return {
                    "method": "tld",
                    "country": country,
                    "country_code": code,
                    "confidence": SIGNAL_WEIGHTS["tld"],
                    "detail": f"TLD: .{suffix} -> {resolved_tld}",
                }

        # TLD semplice
        tld = suffix.split(".")[-1] if "." in suffix else suffix
        if tld in COUNTRY_TLD_MAP:
            country, code = COUNTRY_TLD_MAP[tld]
            return {
                "method": "tld",
                "country": country,
                "country_code": code,
                "confidence": SIGNAL_WEIGHTS["tld"],
                "detail": f"TLD: .{tld}",
            }

        return None

    def _detect_from_domain(self, from_address: str) -> dict | None:
        """Per domini gTLD (.com, .org, .net), cerca ccTLD nel dominio di secondo livello.
        Es: poste.it -> Italy, laposte.fr -> France."""
        email = self._extract_email(from_address)
        if not email:
            return None

        extracted = tldextract.extract(email)
        suffix = extracted.suffix.lower()

        # Solo per gTLD
        if suffix not in ("com", "org", "net", "info", "biz"):
            return None

        # Cerca nel dominio completo un pattern che contenga un ccTLD
        domain = extracted.domain.lower()
        for tld, (country, code) in COUNTRY_TLD_MAP.items():
            if len(tld) == 2 and domain.endswith(tld) and len(domain) > 2:
                return {
                    "method": "domain",
                    "country": country,
                    "country_code": code,
                    "confidence": SIGNAL_WEIGHTS["domain"] * 0.5,
                    "detail": f"Domain hint: {domain}.{suffix} contains '{tld}'",
                }

        return None

    def _detect_from_phone(self, body_text: str) -> dict | None:
        """Cerca prefissi telefonici internazionali negli ultimi 500 caratteri (firma)."""
        if not body_text:
            return None

        signature = body_text[-500:]

        # Pattern: +XX, +XXX, 00XX, 00XXX (prefissi internazionali)
        patterns = [
            r"\+(\d{1,3})[\s.\-/]?\d",
            r"(?:^|[\s(])00(\d{1,3})[\s.\-/]?\d",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, signature)
            for prefix in matches:
                # Prova prima prefisso a 3 cifre, poi 2, poi 1
                for length in (3, 2, 1):
                    candidate = prefix[:length]
                    if candidate in PHONE_PREFIX_MAP:
                        country, code = PHONE_PREFIX_MAP[candidate]
                        return {
                            "method": "phone",
                            "country": country,
                            "country_code": code,
                            "confidence": SIGNAL_WEIGHTS["phone"],
                            "detail": f"Phone prefix: +{candidate}",
                        }

        return None

    def _detect_language(self, body_text: str) -> dict | None:
        """Detecta la lingua del body con langdetect."""
        if not body_text or len(body_text.strip()) < 20:
            return None

        try:
            from langdetect import detect
            lang = detect(body_text)
        except Exception:
            return None

        lang_lower = lang.lower()
        if lang_lower in LANGUAGE_COUNTRY_MAP:
            country, code = LANGUAGE_COUNTRY_MAP[lang_lower]
            return {
                "method": "language",
                "country": country,
                "country_code": code,
                "confidence": SIGNAL_WEIGHTS["language"],
                "detail": f"Language detected: {lang}",
            }

        return None

    def _detect_from_ip(self, headers: dict) -> dict | None:
        """Estrae IP da header Received/X-Originating-IP e geolocalizza."""
        ip = self._extract_originating_ip(headers)
        if not ip:
            return None

        # Ignora IP privati
        if self._is_private_ip(ip):
            return None

        reader = self._get_geoip_reader()
        if not reader:
            return None

        try:
            response = reader.country(ip)
            country = response.country.name
            code = response.country.iso_code
            if country and code:
                return {
                    "method": "ip_geo",
                    "country": country,
                    "country_code": code,
                    "confidence": SIGNAL_WEIGHTS["ip_geo"],
                    "detail": f"IP: {ip} -> {country}",
                }
        except Exception:
            pass

        return None

    def _resolve_signals(self, signals: list[dict]) -> dict:
        """Combina segnali multipli con confidence pesata, risolve conflitti."""
        if not signals:
            return {
                "country": "Unknown",
                "country_code": None,
                "confidence": 0.0,
                "detection_method": "none",
                "signals": [],
            }

        # Raggruppa per country_code
        country_votes: dict[str, float] = {}
        country_names: dict[str, str] = {}
        country_methods: dict[str, list[str]] = {}

        for signal in signals:
            code = signal["country_code"]
            conf = signal["confidence"]
            country_votes[code] = country_votes.get(code, 0) + conf
            country_names[code] = signal["country"]
            if code not in country_methods:
                country_methods[code] = []
            country_methods[code].append(signal["method"])

        # Seleziona il paese con confidence aggregata massima
        best_code = max(country_votes, key=country_votes.get)
        total_confidence = country_votes[best_code]

        # Normalizza confidence a [0, 1]
        max_possible = sum(SIGNAL_WEIGHTS.values())
        normalized_confidence = min(1.0, round(total_confidence / max_possible, 2))

        methods = country_methods[best_code]
        primary_method = methods[0] if len(methods) == 1 else "+".join(sorted(set(methods)))

        return {
            "country": country_names[best_code],
            "country_code": best_code,
            "confidence": normalized_confidence,
            "detection_method": primary_method,
            "signals": signals,
        }

    def _extract_email(self, from_field: str) -> str | None:
        """Estrae l'indirizzo email puro dal campo From."""
        match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", from_field)
        return match.group(0) if match else None

    def _extract_originating_ip(self, headers: dict) -> str | None:
        """Estrae l'IP di origine dagli header."""
        # X-Originating-IP ha priorita'
        x_orig = headers.get("X-Originating-IP", "")
        if x_orig:
            ip_match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", x_orig)
            if ip_match:
                return ip_match.group(1)

        # Fallback: ultimo IP nella catena Received
        received = headers.get("Received", "")
        if isinstance(received, list):
            received_list = received
        else:
            received_list = [received] if received else []

        for entry in reversed(received_list):
            ips = re.findall(r"\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]", entry)
            for ip in ips:
                if not self._is_private_ip(ip):
                    return ip

        return None

    def _is_private_ip(self, ip: str) -> bool:
        """Verifica se un IP e' privato (RFC 1918)."""
        parts = ip.split(".")
        if len(parts) != 4:
            return True
        try:
            first, second = int(parts[0]), int(parts[1])
        except ValueError:
            return True

        if first == 10:
            return True
        if first == 172 and 16 <= second <= 31:
            return True
        if first == 192 and second == 168:
            return True
        if first == 127:
            return True
        return False

    def _get_geoip_reader(self):
        """Carica il database GeoLite2 (cache dopo prima apertura)."""
        if self._geoip_reader is not None:
            return self._geoip_reader

        if not GEOIP_DB_PATH.exists():
            logger.warning("geoip_db_not_found", path=str(GEOIP_DB_PATH))
            return None

        try:
            import geoip2.database
            self._geoip_reader = geoip2.database.Reader(str(GEOIP_DB_PATH))
            return self._geoip_reader
        except Exception as e:
            logger.warning("geoip_load_failed", error=str(e))
            return None
