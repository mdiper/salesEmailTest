from dataclasses import dataclass, field

from src.utils.logger import logger


# Pesi per ogni componente di analisi
WEIGHTS = {
    "header": 0.25,
    "phishing": 0.30,
    "attachment": 0.25,
    "reputation": 0.10,
    "anomaly": 0.10,
}

# Soglie di classificazione
THRESHOLDS = {
    "SAFE": (0, 29),
    "SUSPICIOUS": (30, 69),
    "DANGEROUS": (70, 100),
}


@dataclass
class SecurityResult:
    """Risultato finale dell'analisi di sicurezza."""
    risk_score: int
    verdict: str
    flags: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


class RiskScorer:
    """Calcola lo score di rischio pesato aggregando i risultati di tutti i componenti."""

    def calculate(self, analysis: dict) -> SecurityResult:
        """Calcola lo score pesato e determina il verdetto.

        Args:
            analysis: dict con chiavi 'header', 'phishing', 'attachment'
                      (opzionali: 'reputation', 'anomaly')

        Returns:
            SecurityResult con score, verdict e flags.
        """
        header_score = analysis.get("header", {}).get("total_risk_contribution", 0)
        phishing_score = analysis.get("phishing", {}).get("phishing_score", 0)
        attachment_score = analysis.get("attachment", {}).get("overall_risk", 0)
        reputation_score = analysis.get("reputation", {}).get("risk_score", 0)
        anomaly_score = analysis.get("anomaly", {}).get("risk_score", 0)

        weighted_score = (
            header_score * WEIGHTS["header"]
            + phishing_score * WEIGHTS["phishing"]
            + attachment_score * WEIGHTS["attachment"]
            + reputation_score * WEIGHTS["reputation"]
            + anomaly_score * WEIGHTS["anomaly"]
        )

        risk_score = min(100, round(weighted_score))

        # Override: se ClamAV rileva infezione, score minimo 90
        if analysis.get("attachment", {}).get("verdict") == "infected":
            risk_score = max(risk_score, 90)

        # Override: estensione pericolosa + indicatori phishing => minimo 70
        if analysis.get("attachment", {}).get("verdict") == "dangerous_extension":
            if phishing_score >= 30 or header_score >= 50:
                risk_score = max(risk_score, 75)
            else:
                risk_score = max(risk_score, 70)

        verdict = self._determine_verdict(risk_score)
        flags = self._collect_flags(analysis)

        details = {
            "component_scores": {
                "header": header_score,
                "phishing": phishing_score,
                "attachment": attachment_score,
                "reputation": reputation_score,
                "anomaly": anomaly_score,
            },
            "weights": WEIGHTS,
        }

        result = SecurityResult(
            risk_score=risk_score,
            verdict=verdict,
            flags=flags,
            details=details,
        )

        logger.info(
            "risk_score_calculated",
            risk_score=risk_score,
            verdict=verdict,
            flags_count=len(flags),
            header=header_score,
            phishing=phishing_score,
            attachment=attachment_score,
        )

        return result

    def _determine_verdict(self, score: int) -> str:
        """Determina il verdetto in base alle soglie."""
        if score <= THRESHOLDS["SAFE"][1]:
            return "SAFE"
        elif score <= THRESHOLDS["SUSPICIOUS"][1]:
            return "SUSPICIOUS"
        else:
            return "DANGEROUS"

    def _collect_flags(self, analysis: dict) -> list[str]:
        """Raccoglie tutti i flag attivi dall'analisi completa."""
        flags = []

        # Flags da Header Analysis
        header = analysis.get("header", {})
        if header.get("spf", {}).get("fail"):
            flags.append("spf_fail")
        if not header.get("spf", {}).get("pass"):
            flags.append("spf_not_pass")
        if not header.get("dkim", {}).get("pass"):
            flags.append("dkim_fail")
        if not header.get("dmarc", {}).get("pass"):
            flags.append("dmarc_fail")
        if header.get("return_path_mismatch", {}).get("mismatch"):
            flags.append("return_path_mismatch")
        if header.get("reply_to_mismatch", {}).get("mismatch"):
            flags.append("reply_to_mismatch")

        # Flags da Phishing Detection
        phishing = analysis.get("phishing", {})
        if phishing.get("phishing_score", 0) >= 30:
            flags.append("phishing_indicators")
        if phishing.get("homoglyph_detected"):
            flags.append("homoglyph_detected")
        if phishing.get("display_name_spoof"):
            flags.append("display_name_spoof")
        if phishing.get("url_risk", 0) >= 25:
            flags.append("suspicious_urls")

        # Flags da Attachment/Malware Scan
        attachment = analysis.get("attachment", {})
        if attachment.get("verdict") == "infected":
            flags.append("malware_detected")
        if attachment.get("verdict") == "dangerous_extension":
            flags.append("dangerous_extension")
        if attachment.get("verdict") == "suspicious_content":
            flags.append("suspicious_content")
        ext_check = attachment.get("extension_check", {})
        if ext_check.get("level") == "dangerous":
            flags.append("blocked_extension")
        if attachment.get("yara", {}).get("matches"):
            flags.append("yara_match")

        return flags
