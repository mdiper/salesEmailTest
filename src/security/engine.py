from src.security.header_analyzer import HeaderAnalyzer
from src.security.phishing_detector import PhishingDetector
from src.security.malware_scanner import MalwareScanner
from src.security.risk_scorer import RiskScorer, SecurityResult
from src.db.security_repository import SecurityRepository
from src.utils.logger import logger


class SecurityEngine:
    """Orchestratore che esegue l'intera pipeline di sicurezza su una email.

    Componenti:
        1. HeaderAnalyzer  -> analisi header (SPF, DKIM, DMARC, spoofing)
        2. PhishingDetector -> analisi contenuto (URL, pattern, homoglyphs)
        3. MalwareScanner  -> analisi allegati (extension, ClamAV, YARA)
        4. RiskScorer      -> calcolo score pesato e verdetto finale
    """

    def __init__(self):
        self.header_analyzer = HeaderAnalyzer()
        self.phishing_detector = PhishingDetector()
        self.malware_scanner = MalwareScanner()
        self.risk_scorer = RiskScorer()
        self.repository = SecurityRepository()

    def analyze_email(self, email_data: dict, save_to_db: bool = True) -> SecurityResult:
        """Esegue l'analisi di sicurezza completa su una email.

        Args:
            email_data: dict con chiavi 'headers', 'body_html', 'body_text',
                       'from', 'attachments', 'email_id' (opzionale)
            save_to_db: se True, salva il risultato nel DB

        Returns:
            SecurityResult con score, verdict, flags e details.
        """
        logger.info("security_engine_start", email_id=email_data.get("email_id"))

        # 1. Header Analysis
        headers = email_data.get("headers", {})
        header_result = self.header_analyzer.analyze(headers)

        # 2. Phishing Detection
        phishing_result = self.phishing_detector.analyze(email_data)

        # 3. Malware Scan (su tutti gli allegati, prende il worst case)
        attachment_result = self._scan_attachments(email_data.get("attachments", []))

        # 4. Aggregazione e scoring
        analysis = {
            "header": header_result,
            "phishing": phishing_result,
            "attachment": attachment_result,
        }

        security_result = self.risk_scorer.calculate(analysis)

        # Aggiunge dettagli dei singoli componenti
        security_result.details["header_analysis"] = header_result
        security_result.details["phishing_analysis"] = {
            k: v for k, v in phishing_result.items() if k != "details"
        }
        security_result.details["attachment_analysis"] = {
            k: v for k, v in attachment_result.items() if k != "yara"
        }

        # 5. Salvataggio in DB (se richiesto e email_id presente)
        email_id = email_data.get("email_id")
        if save_to_db and email_id:
            try:
                self.repository.save_result(email_id, security_result, header_result)
            except Exception as e:
                logger.error("security_engine_save_failed", email_id=email_id, error=str(e))

        logger.info(
            "security_engine_complete",
            email_id=email_id,
            risk_score=security_result.risk_score,
            verdict=security_result.verdict,
            flags=security_result.flags,
        )

        return security_result

    def _scan_attachments(self, attachments: list[dict]) -> dict:
        """Scansiona tutti gli allegati e restituisce il risultato peggiore."""
        if not attachments:
            return {"overall_risk": 0, "verdict": "clean", "extension_check": {"level": "safe"}}

        worst_result = None
        worst_risk = -1

        for att in attachments:
            att_bytes = att.get("raw_bytes", b"")
            metadata = {
                "filename": att.get("filename", "unknown"),
                "content_type": att.get("content_type", ""),
                "size": att.get("size", 0),
            }

            result = self.malware_scanner.scan_attachment(att_bytes, metadata)

            if result["overall_risk"] > worst_risk:
                worst_risk = result["overall_risk"]
                worst_result = result

        return worst_result if worst_result else {
            "overall_risk": 0, "verdict": "clean", "extension_check": {"level": "safe"}
        }
