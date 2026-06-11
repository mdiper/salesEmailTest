import re

from src.utils.logger import logger


class HeaderAnalyzer:
    """Analizza gli header email per verifiche di sicurezza (SPF, DKIM, DMARC, spoofing)."""

    def analyze(self, headers: dict) -> dict:
        """Esegue tutti i check sugli header e restituisce i risultati aggregati."""
        results = {
            "spf": self._check_spf(headers),
            "dkim": self._check_dkim(headers),
            "dmarc": self._check_dmarc(headers),
            "return_path_mismatch": self._check_return_path(headers),
            "reply_to_mismatch": self._check_reply_to(headers),
            "received_chain": self._analyze_received_chain(headers),
        }

        total_risk = sum(
            r.get("risk_contribution", 0) for r in results.values()
        )
        results["total_risk_contribution"] = min(total_risk, 100)

        logger.info(
            "header_analysis_complete",
            total_risk=results["total_risk_contribution"],
            spf_pass=results["spf"]["pass"],
            dkim_pass=results["dkim"]["pass"],
            dmarc_pass=results["dmarc"]["pass"],
        )

        return results

    def _check_spf(self, headers: dict) -> dict:
        """Verifica SPF (Sender Policy Framework) da Authentication-Results.
        Risk: 0 se pass, 20 se fail/none."""
        auth_results = self._get_auth_results(headers)
        spf_pass = bool(re.search(r"spf=pass", auth_results, re.IGNORECASE))
        spf_fail = bool(re.search(r"spf=(fail|softfail|none|temperror|permerror)", auth_results, re.IGNORECASE))

        return {
            "pass": spf_pass,
            "fail": spf_fail,
            "raw": self._extract_spf_detail(auth_results),
            "risk_contribution": 0 if spf_pass else 20,
        }

    def _check_dkim(self, headers: dict) -> dict:
        """Verifica DKIM da Authentication-Results.
        Risk: 0 se pass, 15 se fail/none."""
        auth_results = self._get_auth_results(headers)
        dkim_pass = bool(re.search(r"dkim=pass", auth_results, re.IGNORECASE))

        return {
            "pass": dkim_pass,
            "raw": self._extract_dkim_detail(auth_results),
            "risk_contribution": 0 if dkim_pass else 15,
        }

    def _check_dmarc(self, headers: dict) -> dict:
        """Verifica DMARC da Authentication-Results.
        Risk: 0 se pass, 25 se fail/none."""
        auth_results = self._get_auth_results(headers)
        dmarc_pass = bool(re.search(r"dmarc=pass", auth_results, re.IGNORECASE))

        return {
            "pass": dmarc_pass,
            "raw": self._extract_dmarc_detail(auth_results),
            "risk_contribution": 0 if dmarc_pass else 25,
        }

    def _check_return_path(self, headers: dict) -> dict:
        """Confronta dominio From vs Return-Path. Mismatch indica possibile spoofing.
        Risk: 0 se OK, 15 se mismatch."""
        from_domain = self._extract_domain(headers.get("From", ""))
        return_path = headers.get("Return-Path", "")
        return_path_domain = self._extract_domain(return_path)

        if not return_path_domain:
            return {"mismatch": False, "from_domain": from_domain, "return_path_domain": "", "risk_contribution": 0}

        mismatch = from_domain.lower() != return_path_domain.lower()

        return {
            "mismatch": mismatch,
            "from_domain": from_domain,
            "return_path_domain": return_path_domain,
            "risk_contribution": 15 if mismatch else 0,
        }

    def _check_reply_to(self, headers: dict) -> dict:
        """Confronta dominio From vs Reply-To. Mismatch e' sospetto.
        Risk: 0 se OK, 10 se mismatch."""
        from_domain = self._extract_domain(headers.get("From", ""))
        reply_to = headers.get("Reply-To", "")
        reply_to_domain = self._extract_domain(reply_to)

        if not reply_to_domain:
            return {"mismatch": False, "from_domain": from_domain, "reply_to_domain": "", "risk_contribution": 0}

        mismatch = from_domain.lower() != reply_to_domain.lower()

        return {
            "mismatch": mismatch,
            "from_domain": from_domain,
            "reply_to_domain": reply_to_domain,
            "risk_contribution": 10 if mismatch else 0,
        }

    def _analyze_received_chain(self, headers: dict) -> dict:
        """Analizza la catena degli header Received per estrarre l'IP originante."""
        received = headers.get("Received", "")
        if isinstance(received, list):
            received_list = received
        else:
            received_list = [received] if received else []

        ips = []
        for entry in received_list:
            found_ips = re.findall(r"\[(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\]", entry)
            ips.extend(found_ips)

        originating_ip = ips[-1] if ips else None
        hop_count = len(received_list)

        return {
            "originating_ip": originating_ip,
            "all_ips": ips,
            "hop_count": hop_count,
            "risk_contribution": 0,
        }

    def _get_auth_results(self, headers: dict) -> str:
        """Recupera il campo Authentication-Results (puo' essere multiplo)."""
        auth = headers.get("Authentication-Results", "")
        if isinstance(auth, list):
            return " ".join(auth)
        return auth

    def _extract_domain(self, field: str) -> str:
        """Estrae il dominio da un campo email (From, Reply-To, Return-Path)."""
        match = re.search(r"@([\w.-]+)", field)
        return match.group(1) if match else ""

    def _extract_spf_detail(self, auth_results: str) -> str:
        match = re.search(r"spf=\w+[^;]*", auth_results, re.IGNORECASE)
        return match.group(0).strip() if match else ""

    def _extract_dkim_detail(self, auth_results: str) -> str:
        match = re.search(r"dkim=\w+[^;]*", auth_results, re.IGNORECASE)
        return match.group(0).strip() if match else ""

    def _extract_dmarc_detail(self, auth_results: str) -> str:
        match = re.search(r"dmarc=\w+[^;]*", auth_results, re.IGNORECASE)
        return match.group(0).strip() if match else ""
