import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from src.utils.logger import logger


KNOWN_SHORTENERS = {
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly",
    "is.gd", "buff.ly", "adf.ly", "bl.ink", "lnkd.in",
    "rb.gy", "cutt.ly", "shorturl.at",
}

SUSPICIOUS_PATTERNS = [
    r"(?i)(verify|confirm|update|suspend).*(account|password|credentials)",
    r"(?i)(click|act|respond).*(immediately|urgently|within \d+ hours)",
    r"(?i)(won|congratulations|lottery|inheritance|prince)",
    r"(?i)(bank|paypal|amazon|apple|microsoft|google).*(login|verify|confirm|secure)",
    r"(?i)(your account).*(has been|will be).*(suspended|closed|locked|limited)",
    r"(?i)(unusual|suspicious).*(activity|sign-in|login)",
    r"(?i)(reset your password|change your password).*(click|link)",
    r"(?i)(invoice|payment|wire transfer).*(attached|overdue|pending)",
]

HOMOGLYPH_MAP = {
    "\u0430": "a", "\u0435": "e", "\u043e": "o", "\u0440": "p",
    "\u0441": "c", "\u0443": "y", "\u0445": "x", "\u0456": "i",
    "\u0458": "j", "\u04bb": "h", "\u0501": "d",
    "\u0131": "i", "\u0261": "g", "\u0251": "a",
    "\u1d00": "a", "\u1d04": "c", "\u1d07": "e",
}

SPOOFED_BRANDS = [
    "paypal", "apple", "microsoft", "google", "amazon",
    "netflix", "facebook", "instagram", "whatsapp", "dhl",
    "fedex", "ups", "bank", "wells fargo", "chase",
    "dropbox", "linkedin", "twitter", "outlook", "office365",
]


class PhishingDetector:
    """Analizza email per indicatori di phishing: URL, pattern, homoglyph, spoofing."""

    def analyze(self, email_data: dict) -> dict:
        """Analisi completa phishing. Restituisce dict con phishing_score aggregato (0-100)."""
        body_html = email_data.get("body_html") or ""
        body_text = email_data.get("body_text") or ""
        from_field = email_data.get("from", "")

        urls = self._extract_urls(body_html, body_text)
        url_risk = self._analyze_urls(urls)
        pattern_risk = self._check_patterns(body_text or body_html)
        homoglyph_risk = self._check_homoglyphs(from_field)
        display_spoof_risk = self._check_display_name_spoof(from_field)

        phishing_score = min(100, url_risk + pattern_risk + homoglyph_risk + display_spoof_risk)

        result = {
            "phishing_score": phishing_score,
            "url_risk": url_risk,
            "urls_found": len(urls),
            "pattern_risk": pattern_risk,
            "homoglyph_detected": homoglyph_risk > 0,
            "display_name_spoof": display_spoof_risk > 0,
            "details": {
                "urls_analyzed": urls[:10],
                "patterns_matched": self._get_matched_patterns(body_text or body_html),
            },
        }

        logger.info(
            "phishing_analysis_complete",
            phishing_score=phishing_score,
            url_risk=url_risk,
            pattern_risk=pattern_risk,
            homoglyph=homoglyph_risk > 0,
            spoof=display_spoof_risk > 0,
        )

        return result

    def _extract_urls(self, body_html: str, body_text: str) -> list[str]:
        """Estrae URL dal body HTML (href) e dal testo (regex)."""
        urls = set()

        # Estrazione da HTML href
        if body_html:
            try:
                soup = BeautifulSoup(body_html, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"].strip()
                    if href.startswith(("http://", "https://")):
                        urls.add(href)
            except Exception:
                pass

        # Estrazione da testo con regex
        text = body_text or body_html
        if text:
            url_pattern = r"https?://[^\s<>\"'\)]+";
            for match in re.findall(url_pattern, text):
                urls.add(match.rstrip(".,;:"))

        return list(urls)

    def _analyze_urls(self, urls: list[str]) -> int:
        """Analizza gli URL estratti per indicatori di phishing. Risk cap: 50."""
        if not urls:
            return 0

        risk = 0
        for url in urls:
            try:
                parsed = urlparse(url)
                netloc = parsed.netloc.lower()

                # URL shortener
                if netloc in KNOWN_SHORTENERS:
                    risk += 10

                # IP address in URL
                if re.match(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", netloc):
                    risk += 25

                # Subdomain eccessivi (login.paypal.com.evil.xyz)
                if netloc.count(".") > 3:
                    risk += 15

                # Punycode / IDN domain
                if "xn--" in netloc:
                    risk += 20

                # Porta non standard
                if parsed.port and parsed.port not in (80, 443):
                    risk += 10

                # Path con keyword sospette
                path_lower = parsed.path.lower()
                if any(kw in path_lower for kw in ("/login", "/signin", "/verify", "/secure", "/update")):
                    risk += 5

            except Exception:
                continue

        return min(risk, 50)

    def _check_patterns(self, text: str) -> int:
        """Matching pattern regex sospetti nel body. Ogni match +8, cap 40."""
        if not text:
            return 0

        risk = 0
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, text):
                risk += 8

        return min(risk, 40)

    def _check_homoglyphs(self, from_field: str) -> int:
        """Detecta caratteri Unicode simili a ASCII nel campo From. Risk: 30 se trovato."""
        for char in from_field:
            if char in HOMOGLYPH_MAP:
                return 30
        return 0

    def _check_display_name_spoof(self, from_field: str) -> int:
        """Detecta display name che imita brand noti con email non correlata.
        Es: 'PayPal Security <random@evil.com>' -> risk 25."""
        if "<" not in from_field:
            return 0

        display_name = from_field.split("<")[0].strip().lower()
        email_part = from_field.split("<")[1].split(">")[0].lower() if ">" in from_field else ""

        for brand in SPOOFED_BRANDS:
            if brand in display_name:
                # Verifica se il dominio email corrisponde al brand
                brand_in_email = brand in email_part
                if not brand_in_email:
                    return 25

        return 0

    def _get_matched_patterns(self, text: str) -> list[str]:
        """Restituisce i pattern che hanno matchato (per logging/debug)."""
        if not text:
            return []
        matched = []
        for pattern in SUSPICIOUS_PATTERNS:
            match = re.search(pattern, text)
            if match:
                matched.append(match.group(0)[:80])
        return matched
