# Documento di Analisi Tecnico-Funzionale
## Sistema di Gestione e Routing Automatico delle Email

---

## 1. Executive Summary

### Descrizione del Sistema

Il sistema è una piattaforma di email intelligence che si interpone tra una mailbox e l'utente finale, applicando una pipeline di analisi multi-livello a ogni messaggio in ingresso. Ogni email viene sottoposta a controlli di sicurezza, classificazione geografica del mittente, comlprensione del contenuto e infine instradata secondo regole configurabili.

### Obiettivo

Automatizzare il triage delle email in ingresso, riducendo il rischio di phishing/malware, classificando i messaggi per priorità e contenuto, e instradandoli verso i destinatari appropriati senza intervento manuale.

### Use Cases Principali

| #   | Use Case                     | Attore        | Risultato Atteso                                      |
|-----|------------------------------|---------------|-------------------------------------------------------|
| 1   | Blocco email di phishing     | Sistema       | Email classificata DANGEROUS, quarantena, alert admin |
| 2   | Routing per paese            | Sales Manager | Email da clienti FR → team Francia                    |
| 3   | Classificazione fatture      | Finance Team  | Email con fattura → finance@azienda.com               |
| 4   | Riassunto email per priorità | Manager       | Dashboard con summary e risk score                    |
| 5   | Quarantena allegati sospetti | Security Team | Allegato .exe → sandbox + notifica                    |

---

## 2. Architettura Tecnica

### Diagramma Logico

```
┌─────────────┐     ┌──────────────┐
│  MAILBOX    │────▶│  INGESTION   │
│ (IMAP)      │     │   SERVICE    │
└─────────────┘     └──────┬───────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  SECURITY ENGINE │
                  │  (Step 1)        │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  COUNTRY DETECT  │
                  │  (Step 2)        │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  CONTENT ANALYSIS│
                  │  (Step 3 — NLP)  │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐     ┌──────────────┐
                  │  ROUTING ENGINE  │────▶│  ACTIONS     │
                  │  (Step 4)        │     │  (fwd/block) │
                  └──────────────────┘     └──────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  DATABASE + LOGS │
                  │  (MySQL)         │
                  └──────────────────┘
```

### Componenti Backend

1. **Ingestion Service** — Connessione IMAP (Vianova), polling, parsing MIME
2. **Security Engine** — Analisi header, phishing detection, virus scan
3. **Country Detector** — Geolocalizzazione mittente
4. **Content Analyzer** — NLP, classificazione, summarization
5. **Routing Engine** — Rule engine con priorità e conflict resolution
6. **Action Executor** — Forward, block, quarantine, tag
7. **API Gateway** — REST API per frontend e configurazione
8. **Notification Service** — Alert via email/webhook/Slack

### Frontend (Opzionale)

- Dashboard web (React/Next.js)
- Visualizzazione email con metadata arricchiti
- Configurazione regole di routing (UI drag & drop)
- Grafici: volume email, distribuzione rischio, paesi

### Processing Sincrono

Il sistema processa ogni email in modo sincrono attraverso la pipeline (Security → Country → Content → Routing) all'interno di un singolo processo Python. Questo approccio è adeguato al volume previsto (centinaia di email/giorno) e garantisce:
- Architettura semplice, facile da debuggare e mantenere
- Nessuna infrastruttura aggiuntiva oltre a Python e MySQL
- Retry automatico tramite la libreria `tenacity` in caso di errori transitori
- Tracciamento completo di ogni email nel database (tabella `emails.processing_status`)

### Database Schema (Panoramica)

```sql
-- Core tables
emails              -- raw email data + parsed fields
email_headers       -- full headers key-value
email_attachments   -- attachment metadata + storage ref
security_results    -- risk score, flags, verdict
country_results     -- country, confidence, method used
content_results     -- summary, category, entities
routing_logs        -- action taken, rule matched, timestamp
routing_rules       -- configured rules
audit_log           -- every system event
```

---

## 3. Email Ingestion Layer

### Protocollo Utilizzato

Il sistema si connette a un **singolo account email Vianova** tramite protocollo **IMAP con IMAP IDLE** (push pseudo-real-time). Vianova fornisce un servizio di posta standard con supporto IMAP, autenticazione con username/password e connessione SSL/TLS.

Non sono necessarie API proprietarie (Gmail API, Microsoft Graph) né autenticazione OAuth poiché Vianova espone un server IMAP standard.

### Design IMAP

```python
import imaplib
import email
from email.policy import default as default_policy

class IMAPIngestionService:
    def __init__(self, host: str, port: int, credentials: dict):
        self.host = host
        self.port = port
        self.credentials = credentials
        self._connection = None

    def connect(self) -> None:
        self._connection = imaplib.IMAP4_SSL(self.host, self.port)
        self._connection.login(
            self.credentials["username"],
            self.credentials["password"]
        )
        self._connection.select("INBOX")

    def poll(self) -> list[dict]:
        """Recupera email non lette tramite polling."""
        status, messages = self._connection.search(None, "UNSEEN")
        if status != "OK":
            raise IngestionError("IMAP search failed")

        results = []
        for msg_id in messages[0].split():
            status, data = self._connection.fetch(msg_id, "(RFC822)")
            if status == "OK":
                raw = data[0][1]
                parsed = email.message_from_bytes(raw, policy=default_policy)
                results.append(self._normalize(parsed))
        return results

    def idle_listen(self) -> None:
        """IMAP IDLE per push notification (pseudo-real-time)."""
        self._connection.send(b"IDLE\r\n")
        while True:
            line = self._connection.readline()
            if b"EXISTS" in line:
                self._connection.send(b"DONE\r\n")
                new_emails = self.poll()
                self._process_emails(new_emails)
                self._connection.send(b"IDLE\r\n")

    def _normalize(self, msg) -> dict:
        return {
            "message_id": msg["Message-ID"],
            "from": msg["From"],
            "to": msg["To"],
            "subject": msg["Subject"],
            "date": msg["Date"],
            "headers": dict(msg.items()),
            "body_text": self._extract_body(msg, "text/plain"),
            "body_html": self._extract_body(msg, "text/html"),
            "attachments": self._extract_attachments(msg),
        }

    def _extract_body(self, msg, content_type: str) -> str | None:
        for part in msg.walk():
            if part.get_content_type() == content_type:
                return part.get_content()
        return None

    def _extract_attachments(self, msg) -> list[dict]:
        attachments = []
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                attachments.append({
                    "filename": part.get_filename(),
                    "content_type": part.get_content_type(),
                    "size": len(part.get_payload(decode=True)),
                    "hash_sha256": hashlib.sha256(
                        part.get_payload(decode=True)
                    ).hexdigest(),
                })
        return attachments
```

### Gestione Errori e Retry

```python
from tenacity import retry, stop_after_attempt, wait_exponential

class IngestionRetryPolicy:
    MAX_ATTEMPTS = 5
    BASE_WAIT_SECONDS = 2
    MAX_WAIT_SECONDS = 60

    @retry(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=BASE_WAIT_SECONDS, max=MAX_WAIT_SECONDS),
        reraise=True
    )
    def fetch_with_retry(self, connection, msg_id):
        status, data = connection.fetch(msg_id, "(RFC822)")
        if status != "OK":
            raise TransientError(f"Fetch failed for {msg_id}")
        return data

# Email non processabili dopo N tentativi → status 'failed' in DB + alert admin
```

**Strategie di resilienza:**
- Retry con exponential backoff per errori transitori (network, timeout)
- Circuit breaker per evitare cascading failure verso il mail server
- Email che falliscono tutti i tentativi marcate come `processing_status = 'failed'` nel DB + notifica admin
- Heartbeat monitoring sulla connessione IMAP IDLE
- Reconnection automatica con backoff

---

## 4. Security Layer

### Architettura del Security Engine

Il security engine è il componente più critico. Opera in modalità fail-safe: se l'analisi fallisce, l'email viene trattata come SUSPICIOUS.

```python
from dataclasses import dataclass
from enum import Enum

class SecurityVerdict(Enum):
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    DANGEROUS = "DANGEROUS"

@dataclass
class SecurityResult:
    verdict: SecurityVerdict
    risk_score: int  # 0-100
    flags: list[str]
    details: dict
    analysis_timestamp: str
```

### 4.1 Analisi Header Email

```python
class HeaderAnalyzer:
    def analyze(self, headers: dict) -> dict:
        results = {
            "spf": self._check_spf(headers),
            "dkim": self._check_dkim(headers),
            "dmarc": self._check_dmarc(headers),
            "return_path_mismatch": self._check_return_path(headers),
            "reply_to_mismatch": self._check_reply_to(headers),
            "received_chain": self._analyze_received_chain(headers),
            "x_originating_ip": self._extract_originating_ip(headers),
        }
        return results

    def _check_spf(self, headers: dict) -> dict:
        """
        SPF (Sender Policy Framework) verifica che il server mittente
        sia autorizzato a inviare per quel dominio.
        """
        auth_results = headers.get("Authentication-Results", "")
        spf_pass = "spf=pass" in auth_results.lower()
        return {
            "pass": spf_pass,
            "raw": auth_results,
            "risk_contribution": 0 if spf_pass else 20
        }

    def _check_dkim(self, headers: dict) -> dict:
        """DKIM verifica integrità e autenticità del messaggio."""
        auth_results = headers.get("Authentication-Results", "")
        dkim_pass = "dkim=pass" in auth_results.lower()
        return {
            "pass": dkim_pass,
            "risk_contribution": 0 if dkim_pass else 15
        }

    def _check_dmarc(self, headers: dict) -> dict:
        """DMARC policy alignment check."""
        auth_results = headers.get("Authentication-Results", "")
        dmarc_pass = "dmarc=pass" in auth_results.lower()
        return {
            "pass": dmarc_pass,
            "risk_contribution": 0 if dmarc_pass else 25
        }

    def _check_return_path(self, headers: dict) -> dict:
        """Mismatch tra From e Return-Path indica spoofing."""
        from_addr = self._extract_domain(headers.get("From", ""))
        return_path = self._extract_domain(headers.get("Return-Path", ""))
        mismatch = from_addr != return_path and return_path != ""
        return {
            "mismatch": mismatch,
            "from_domain": from_addr,
            "return_path_domain": return_path,
            "risk_contribution": 15 if mismatch else 0
        }

    def _check_reply_to(self, headers: dict) -> dict:
        """Reply-To diverso da From è sospetto."""
        from_addr = self._extract_domain(headers.get("From", ""))
        reply_to = self._extract_domain(headers.get("Reply-To", ""))
        mismatch = reply_to != "" and from_addr != reply_to
        return {
            "mismatch": mismatch,
            "risk_contribution": 10 if mismatch else 0
        }
```

### 4.2 Algoritmi Anti-Phishing

```python
class PhishingDetector:
    SUSPICIOUS_PATTERNS = [
        r"(?i)(verify|confirm|update|suspend).*(account|password|credentials)",
        r"(?i)(click|act|respond).*(immediately|urgently|within \d+ hours)",
        r"(?i)(won|congratulations|lottery|inheritance|prince)",
        r"(?i)(bank|paypal|amazon|apple|microsoft).*(login|verify|confirm)",
    ]

    HOMOGLYPH_MAP = {
        "а": "a", "е": "e", "о": "o", "р": "p",  # Cyrillic
        "ı": "i", "ɡ": "g", "ɑ": "a",  # Latin lookalikes
    }

    def analyze(self, email_data: dict) -> dict:
        scores = []

        # URL analysis
        urls = self._extract_urls(email_data["body_html"] or email_data["body_text"])
        url_risk = self._analyze_urls(urls)
        scores.append(url_risk)

        # Content pattern matching
        pattern_risk = self._check_patterns(email_data["body_text"])
        scores.append(pattern_risk)

        # Domain homoglyph detection
        homoglyph_risk = self._check_homoglyphs(email_data["from"])
        scores.append(homoglyph_risk)

        # Display name spoofing
        display_spoof = self._check_display_name_spoof(email_data["from"])
        scores.append(display_spoof)

        return {
            "phishing_score": min(100, sum(scores)),
            "url_risk": url_risk,
            "pattern_risk": pattern_risk,
            "homoglyph_detected": homoglyph_risk > 0,
            "display_name_spoof": display_spoof > 0,
        }

    def _analyze_urls(self, urls: list[str]) -> int:
        risk = 0
        for url in urls:
            parsed = urlparse(url)
            # URL shortener detection
            if parsed.netloc in KNOWN_SHORTENERS:
                risk += 10
            # IP address in URL
            if re.match(r"\d+\.\d+\.\d+\.\d+", parsed.netloc):
                risk += 25
            # Excessive subdomains (login.paypal.com.evil.xyz)
            if parsed.netloc.count(".") > 3:
                risk += 15
            # Punycode / IDN domain
            if "xn--" in parsed.netloc:
                risk += 20
            # Mismatch display text vs href
            # (handled at HTML parsing level)
        return min(risk, 50)

    def _check_homoglyphs(self, from_field: str) -> int:
        """Detecta caratteri Unicode simili a ASCII (es: аpple vs apple)."""
        for char in from_field:
            if char in self.HOMOGLYPH_MAP:
                return 30
        return 0
```

### 4.3 Virus/Malware Scanning

**Approcci implementativi:**

| Approccio            | Tool/Servizio  | Pro                             | Contro                    |
|----------------------|----------------|---------------------------------|---------------------------|
| ClamAV (self-hosted) | clamd daemon   | Gratuito, on-premise, privacy   | Signature DB limitato     |
| VirusTotal API       | REST API       | 70+ engine, detection rate alta | Rate limit, dati in cloud |
| YARA Rules           | yara-python    | Custom rules, fast              | Richiede expertise        |
| Sandbox (Cuckoo)     | Cuckoo Sandbox | Analisi comportamentale         | Pesante, lento            |

**Strategia consigliata: approccio ibrido a livelli**

```python
class MalwareScanner:
    def scan_attachment(self, attachment: bytes, metadata: dict) -> dict:
        results = {}

        # Layer 1: Extension blocklist (instant)
        results["extension_check"] = self._check_extension(metadata["filename"])

        # Layer 2: ClamAV signature scan (ms)
        results["clamav"] = self._scan_clamav(attachment)

        # Layer 3: YARA custom rules (ms)
        results["yara"] = self._scan_yara(attachment)

        # Layer 4: VirusTotal (solo se Layer 1-3 non conclusivi) (seconds)
        if self._needs_deep_scan(results):
            results["virustotal"] = self._scan_virustotal(
                metadata["hash_sha256"]
            )

        return results

    DANGEROUS_EXTENSIONS = [
        ".exe", ".bat", ".cmd", ".scr", ".pif", ".com",
        ".vbs", ".js", ".wsf", ".msi", ".dll", ".ps1",
        ".hta", ".cpl", ".reg", ".inf", ".lnk"
    ]

    SUSPICIOUS_EXTENSIONS = [
        ".doc", ".docm", ".xlsm", ".pptm",  # Macro-enabled
        ".zip", ".rar", ".7z", ".iso",       # Archives
        ".html", ".htm",                      # Potential redirect
    ]
```

### 4.4 Risk Scoring Model

Il risk score (0–100) è calcolato con formula pesata:

```python
class RiskScorer:
    WEIGHTS = {
        "header_analysis": 0.25,      # SPF/DKIM/DMARC/return-path
        "phishing_detection": 0.30,   # URL + content pattern + homoglyph
        "attachment_risk": 0.25,      # Malware scan results
        "reputation": 0.10,           # Sender domain reputation
        "anomaly": 0.10,              # Behavioral anomaly (first-time sender, etc.)
    }

    THRESHOLDS = {
        "SAFE": (0, 29),
        "SUSPICIOUS": (30, 69),
        "DANGEROUS": (70, 100),
    }

    def calculate(self, analysis: dict) -> SecurityResult:
        component_scores = {
            "header_analysis": self._score_headers(analysis["headers"]),
            "phishing_detection": analysis["phishing"]["phishing_score"],
            "attachment_risk": self._score_attachments(analysis["attachments"]),
            "reputation": self._score_reputation(analysis["sender_domain"]),
            "anomaly": self._score_anomaly(analysis["behavioral"]),
        }

        weighted_score = sum(
            score * self.WEIGHTS[component]
            for component, score in component_scores.items()
        )

        final_score = int(min(100, weighted_score))
        verdict = self._determine_verdict(final_score)

        return SecurityResult(
            verdict=verdict,
            risk_score=final_score,
            flags=self._collect_flags(analysis),
            details=component_scores,
            analysis_timestamp=datetime.utcnow().isoformat(),
        )

    def _determine_verdict(self, score: int) -> SecurityVerdict:
        for verdict, (low, high) in self.THRESHOLDS.items():
            if low <= score <= high:
                return SecurityVerdict(verdict)
        return SecurityVerdict.DANGEROUS  # fail-safe
```

**Formula:**

```
risk_score = Σ (component_score_i × weight_i)

dove:
  header_analysis    = (SPF_fail×20 + DKIM_fail×15 + DMARC_fail×25 + return_path_mismatch×15 + reply_to_mismatch×10) / 85 × 100
  phishing_detection = url_risk + pattern_risk + homoglyph_risk + display_spoof_risk (cap 100)
  attachment_risk    = max(extension_risk, clamav_risk, yara_risk, vt_risk)
  reputation         = lookup da DB reputazione (0=nuovo/sconosciuto → 50, noto buono → 0, noto cattivo → 100)
  anomaly            = first_time_sender×30 + unusual_time×10 + volume_spike×20
```

---

## 5. Country Detection Module

### 5.1 Logica Dominio Email

```python
import tldextract

COUNTRY_TLD_MAP = {
    "it": "Italy", "fr": "France", "de": "Germany", "es": "Spain",
    "br": "Brazil", "uk": "United Kingdom", "jp": "Japan",
    "cn": "China", "ru": "Russia", "kr": "South Korea",
    "nl": "Netherlands", "be": "Belgium", "pt": "Portugal",
    "au": "Australia", "ca": "Canada", "in": "India",
    # ... 200+ country TLDs
}

class CountryDetector:
    def detect(self, email_data: dict) -> dict:
        signals = []

        # Signal 1: TLD del dominio email
        tld_result = self._detect_from_tld(email_data["from"])
        if tld_result:
            signals.append(("tld", tld_result, 0.7))

        # Signal 2: Prefisso telefonico nella firma
        phone_result = self._detect_from_phone(email_data["body_text"])
        if phone_result:
            signals.append(("phone", phone_result, 0.8))

        # Signal 3: Lingua del corpo email
        lang_result = self._detect_language(email_data["body_text"])
        if lang_result:
            signals.append(("language", lang_result, 0.5))

        # Signal 4: IP geolocation (dal header Received)
        ip_result = self._detect_from_ip(email_data["headers"])
        if ip_result:
            signals.append(("ip_geo", ip_result, 0.6))

        return self._resolve_signals(signals)

    def _detect_from_tld(self, from_address: str) -> str | None:
        extracted = tldextract.extract(from_address.split("@")[-1])
        suffix = extracted.suffix.split(".")[-1]  # handle co.uk → uk
        return COUNTRY_TLD_MAP.get(suffix)

    def _detect_from_phone(self, body: str) -> str | None:
        """Estrae prefisso internazionale dalla firma."""
        phone_patterns = [
            r"\+(\d{1,3})[\s\-\.]?\d",       # +39 ...
            r"\(00(\d{1,3})\)",                # (0039)
            r"tel[:\.]?\s*\+(\d{1,3})",        # tel: +39
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, body[-500:])  # solo ultimi 500 char (firma)
            if match:
                prefix = match.group(1)
                return PHONE_PREFIX_MAP.get(prefix)
        return None

    def _detect_language(self, body: str) -> str | None:
        """Usa langdetect per identificare la lingua dominante."""
        from langdetect import detect
        try:
            lang = detect(body)
            return LANGUAGE_COUNTRY_MAP.get(lang)  # "it" → "Italy"
        except:
            return None
```

### 5.2 Risoluzione Segnali Multipli

```python
    def _resolve_signals(self, signals: list[tuple]) -> dict:
        """
        Combina segnali multipli con confidence pesata.
        Se tutti concordano → alta confidence.
        Se discordano → confidence ridotta, vince il segnale con peso maggiore.
        """
        if not signals:
            return {"country": "Unknown", "confidence": 0.0, "method": "none"}

        country_scores = {}
        for method, country, weight in signals:
            country_scores[country] = country_scores.get(country, 0) + weight

        best_country = max(country_scores, key=country_scores.get)
        total_weight = sum(w for _, _, w in signals)
        confidence = country_scores[best_country] / total_weight

        return {
            "country": best_country,
            "confidence": round(confidence, 2),
            "signals_used": [(m, c) for m, c, _ in signals],
            "method": "multi_signal_weighted",
        }
```

### 5.3 Euristiche e Fallback

1. **gTLD senza segnale** (.com, .org, .net): fallback su lingua + telefono
2. **Lingua ambigua** (es: spagnolo → Spagna O Latam): usa IP geolocation come tie-breaker
3. **Nessun segnale**: restituisce `"Unknown"` con confidence `0.0`
4. **Domini aziendali noti**: lookup su database aziende (es: `siemens.com` → Germany)

---

## 6. Content Analysis Module

### 6.1 NLP Pipeline (Locale)

L'intera pipeline di content analysis opera in locale senza dipendenze da API cloud. L'integrazione con LLM (OpenAI, Anthropic) è prevista come **feature futura** opzionale.

```
Email Body → Preprocessing → Language Detection → Classification (rule-based + ML) → Summarization (estrattiva) → Entity Extraction (spaCy)
```

### 6.2 Preprocessing

```python
import re
from bs4 import BeautifulSoup

class EmailPreprocessor:
    def process(self, email_data: dict) -> str:
        body = email_data["body_html"] or email_data["body_text"] or ""

        # Strip HTML
        if "<html" in body.lower():
            soup = BeautifulSoup(body, "html.parser")
            for tag in soup(["script", "style", "head"]):
                tag.decompose()
            body = soup.get_text(separator="\n")

        # Normalize whitespace
        body = re.sub(r"\n{3,}", "\n\n", body)
        body = re.sub(r"[ \t]+", " ", body)

        # Remove email thread (quoted replies)
        body = self._remove_quoted_text(body)

        return body.strip()

    def _remove_quoted_text(self, text: str) -> str:
        """Rimuove il testo citato (> ...) e i separatori di reply."""
        lines = text.split("\n")
        clean_lines = []
        for line in lines:
            if line.startswith(">") or line.startswith("On ") and "wrote:" in line:
                break
            if re.match(r"-{3,}.*Original Message.*-{3,}", line):
                break
            clean_lines.append(line)
        return "\n".join(clean_lines)
```

### 6.3 Classificazione

Categorie supportate:

| Categoria   | Descrizione             | Esempio                               |
|-------------|-------------------------|---------------------------------------|
| `marketing` | Newsletter, promo, DEM  | "20% di sconto fino a venerdì"        |
| `support`   | Richieste assistenza    | "Ho un problema con l'ordine #123"    |
| `invoice`   | Fatture, pagamenti      | "In allegato la fattura n. 456"       |
| `spam`      | Junk, non richieste     | "Congratulations you won!"            |
| `personal`  | Comunicazioni personali | "Ciao, ci vediamo domani?"            |
| `legal`     | Contratti, legale       | "In allegato il contratto da firmare" |
| `hr`        | Risorse umane           | "Candidatura per posizione..."        |
| `sales`     | Offerte commerciali     | "Proposta commerciale per..."         |
| `other`     | Non classificabile      | —                                     |

**Approccio ibrido locale: rule-based + ML (scikit-learn)**

```python
class ContentClassifier:
    RULE_BASED_SIGNALS = {
        "invoice": [
            r"(?i)(fattura|invoice|pagamento|payment|bonifico|wire transfer)",
            r"(?i)(importo|amount|totale|total).*\d+[.,]\d{2}",
            r"(?i)(iban|swift|bic)",
        ],
        "marketing": [
            r"(?i)(unsubscribe|disiscriviti|newsletter)",
            r"(?i)(sconto|discount|offerta|promo|deal)",
            r"(?i)(clicca qui|click here|scopri|discover)",
        ],
        "spam": [
            r"(?i)(viagra|casino|lottery|inheritance|prince|won \$)",
        ],
    }

    def __init__(self, model_path: str = "models/classifier.pkl"):
        self.ml_model = joblib.load(model_path) if os.path.exists(model_path) else None

    def classify(self, text: str) -> dict:
        # Step 1: Rule-based fast check
        rule_result = self._rule_based_classify(text)
        if rule_result["confidence"] > 0.85:
            return rule_result

        # Step 2: Classificazione ML locale (TF-IDF + SVM)
        if self.ml_model:
            return self._ml_classify(text)

        return rule_result

    def _ml_classify(self, text: str) -> dict:
        """Classificazione con modello scikit-learn locale."""
        prediction = self.ml_model.predict([text])[0]
        probabilities = self.ml_model.predict_proba([text])[0]
        confidence = max(probabilities)
        return {
            "category": prediction,
            "confidence": round(float(confidence), 2),
            "method": "ml_local",
        }
```

### 6.4 Summarization Estrattiva (Locale)

Invece di un LLM cloud, la summarization viene fatta in locale con un approccio estrattivo: si identificano le frasi piu rilevanti del corpo email tramite TF-IDF e si compone un riassunto.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

class ContentSummarizer:
    def summarize(self, text: str, num_sentences: int = 4) -> str:
        """Summarization estrattiva: seleziona le frasi più rilevanti."""
        sentences = self._split_sentences(text)
        if len(sentences) <= num_sentences:
            return text

        vectorizer = TfidfVectorizer(stop_words=self._get_stopwords())
        tfidf_matrix = vectorizer.fit_transform(sentences)

        sentence_scores = np.array(tfidf_matrix.sum(axis=1)).flatten()
        top_indices = sentence_scores.argsort()[-num_sentences:]
        top_indices = sorted(top_indices)

        return " ".join(sentences[i] for i in top_indices)

    def _split_sentences(self, text: str) -> list[str]:
        """Divide il testo in frasi."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s for s in sentences if len(s.strip()) > 10]

    def _get_stopwords(self) -> list[str]:
        """Stopwords italiano + inglese per TF-IDF."""
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        italian_stops = ["di", "a", "da", "in", "con", "su", "per", "tra",
                         "il", "lo", "la", "i", "gli", "le", "un", "uno",
                         "una", "e", "è", "che", "non", "si", "del", "al"]
        return list(ENGLISH_STOP_WORDS) + italian_stops
```

### 6.5 Entity Extraction (spaCy — Locale)

L'estrazione entità avviene interamente in locale tramite spaCy, senza chiamate a servizi esterni.

```python
import spacy
import re

class EntityExtractor:
    def __init__(self, model_name: str = "it_core_news_lg"):
        self.nlp = spacy.load(model_name)

    def extract(self, text: str) -> dict:
        doc = self.nlp(text[:5000])

        return {
            "persons": list(set(
                ent.text for ent in doc.ents if ent.label_ == "PER"
            )),
            "companies": list(set(
                ent.text for ent in doc.ents if ent.label_ == "ORG"
            )),
            "dates": list(set(
                ent.text for ent in doc.ents if ent.label_ in ("DATE", "TIME")
            )),
            "amounts": self._extract_amounts(text),
            "action_items": [],
            "references": self._extract_references(text),
        }

    def _extract_amounts(self, text: str) -> list[dict]:
        pattern = r'[€$£]\s*[\d.,]+|\d+[.,]\d{2}\s*(?:EUR|USD|GBP|euro|dollari)'
        matches = re.findall(pattern, text, re.IGNORECASE)
        return [{"raw": m.strip()} for m in matches]

    def _extract_references(self, text: str) -> list[str]:
        patterns = [
            r'(?:fattura|invoice|ordine|order|ticket)\s*[#n°.:]*\s*(\w+[\d]+\w*)',
            r'#(\d{3,})',
        ]
        refs = []
        for pattern in patterns:
            refs.extend(re.findall(pattern, text, re.IGNORECASE))
        return list(set(refs))
```

### 6.6 [FEATURE FUTURA] Integrazione LLM Cloud (OpenAI / Anthropic)

> **Nota**: questa sezione descrive l'evoluzione futura del modulo Content Analysis. L'integrazione con LLM cloud (OpenAI GPT-4o-mini, Anthropic Claude) verra implementata in una fase successiva per migliorare la qualita di classificazione, summarization ed entity extraction rispetto all'approccio locale.

Quando attivata, una singola chiamata LLM sostituira i tre step locali con un'analisi unificata:

```python
FULL_ANALYSIS_PROMPT = """Analizza la seguente email e restituisci un JSON strutturato.

## Istruzioni
1. Classifica la categoria dell'email tra: marketing, support, invoice, spam, personal, legal, hr, sales, other
2. Genera un riassunto di 3-6 righe
3. Estrai tutte le entità rilevanti
4. Indica il sentiment (positive, neutral, negative)
5. Indica l'urgenza (low, medium, high, critical)

## Output Format (JSON)
{
  "category": "string",
  "category_confidence": 0.0-1.0,
  "summary": "string (3-6 righe)",
  "sentiment": "positive|neutral|negative",
  "urgency": "low|medium|high|critical",
  "entities": {
    "persons": ["..."],
    "companies": ["..."],
    "dates": ["YYYY-MM-DD"],
    "amounts": [{"value": 0, "currency": "EUR"}],
    "action_items": ["..."],
    "references": ["..."]
  },
  "language": "ISO 639-1 code"
}

## Email
From: {from_address}
Subject: {subject}
Date: {date}
Body:
---
{body}
---

JSON:"""
```

---

## 7. Routing Engine

### 7.1 Rule Engine Design

Il routing engine usa un sistema di regole dichiarative con priorità, condizioni composte e azioni multiple.

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class RoutingRule:
    id: str
    name: str
    priority: int                # 1 = highest, 1000 = lowest
    enabled: bool
    conditions: list[dict]       # AND logic tra condizioni
    condition_logic: str         # "AND" | "OR"
    actions: list[dict]          # Azioni da eseguire
    stop_processing: bool        # Se True, non valuta regole successive

class RoutingEngine:
    def __init__(self, rules: list[RoutingRule]):
        self.rules = sorted(
            [r for r in rules if r.enabled],
            key=lambda r: r.priority
        )

    def evaluate(self, email_context: dict) -> list[dict]:
        """
        Valuta tutte le regole in ordine di priorità.
        email_context contiene: security_result, country_result, content_result, email_data
        """
        actions_to_execute = []

        for rule in self.rules:
            if self._matches(rule, email_context):
                actions_to_execute.extend(rule.actions)
                if rule.stop_processing:
                    break

        return self._deduplicate_actions(actions_to_execute)

    def _matches(self, rule: RoutingRule, ctx: dict) -> bool:
        evaluator = ConditionEvaluator(ctx)
        results = [evaluator.evaluate(c) for c in rule.conditions]

        if rule.condition_logic == "AND":
            return all(results)
        return any(results)


class ConditionEvaluator:
    OPERATORS = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "lt": lambda a, b: a < b,
        "contains": lambda a, b: b in a,
        "matches": lambda a, b: re.search(b, a) is not None,
        "in": lambda a, b: a in b,
        "not_in": lambda a, b: a not in b,
    }

    def __init__(self, context: dict):
        self.context = context

    def evaluate(self, condition: dict) -> bool:
        field_value = self._resolve_field(condition["field"])
        operator = self.OPERATORS[condition["operator"]]
        return operator(field_value, condition["value"])

    def _resolve_field(self, field_path: str) -> Any:
        """Risolve campo dot-notation: 'security.risk_score' → ctx['security']['risk_score']"""
        parts = field_path.split(".")
        value = self.context
        for part in parts:
            value = value[part]
        return value
```

### 7.2 Esempi di Regole

```json
[
  {
    "id": "rule_001",
    "name": "Block dangerous emails",
    "priority": 1,
    "enabled": true,
    "conditions": [
      {"field": "security.verdict", "operator": "eq", "value": "DANGEROUS"}
    ],
    "condition_logic": "AND",
    "actions": [
      {"type": "quarantine", "folder": "DANGEROUS"},
      {"type": "notify", "channel": "security-alerts", "urgency": "high"},
      {"type": "tag", "tags": ["blocked", "security-threat"]}
    ],
    "stop_processing": true
  },
  {
    "id": "rule_002",
    "name": "Route French clients to France team",
    "priority": 10,
    "enabled": true,
    "conditions": [
      {"field": "country.country", "operator": "eq", "value": "France"},
      {"field": "content.category", "operator": "in", "value": ["sales", "support"]}
    ],
    "condition_logic": "AND",
    "actions": [
      {"type": "forward", "to": "team-france@company.com"},
      {"type": "tag", "tags": ["france", "routed"]}
    ],
    "stop_processing": false
  },
  {
    "id": "rule_003",
    "name": "Forward invoices to finance",
    "priority": 20,
    "enabled": true,
    "conditions": [
      {"field": "content.category", "operator": "eq", "value": "invoice"},
      {"field": "security.verdict", "operator": "neq", "value": "DANGEROUS"}
    ],
    "condition_logic": "AND",
    "actions": [
      {"type": "forward", "to": "finance@company.com"},
      {"type": "tag", "tags": ["invoice", "finance"]}
    ],
    "stop_processing": false
  },
  {
    "id": "rule_004",
    "name": "Quarantine suspicious with high risk",
    "priority": 5,
    "enabled": true,
    "conditions": [
      {"field": "security.verdict", "operator": "eq", "value": "SUSPICIOUS"},
      {"field": "security.risk_score", "operator": "gte", "value": 60}
    ],
    "condition_logic": "AND",
    "actions": [
      {"type": "quarantine", "folder": "REVIEW"},
      {"type": "notify", "channel": "security-review", "urgency": "medium"},
      {"type": "tag", "tags": ["needs-review"]}
    ],
    "stop_processing": true
  },
  {
    "id": "rule_005",
    "name": "Auto-delete spam",
    "priority": 3,
    "enabled": true,
    "conditions": [
      {"field": "content.category", "operator": "eq", "value": "spam"},
      {"field": "security.risk_score", "operator": "lt", "value": 70}
    ],
    "condition_logic": "AND",
    "actions": [
      {"type": "move", "folder": "SPAM"},
      {"type": "tag", "tags": ["spam", "auto-deleted"]}
    ],
    "stop_processing": true
  }
]
```

### 7.3 Priorità delle Regole

```
Priority 1-5:    SECURITY (block/quarantine) — non-overridable
Priority 6-9:    COMPLIANCE (legal routing, data residency)
Priority 10-49:  BUSINESS LOGIC (country routing, team routing)
Priority 50-99:  CONTENT-BASED (category routing, tagging)
Priority 100+:   DEFAULT (catch-all, logging)
```

### 7.4 Conflict Resolution

Quando più regole matchano la stessa email:

1. **Priorità wins**: regole con priority più basso vengono eseguite prima
2. **Stop processing**: se una regola ha `stop_processing: true`, le successive non vengono valutate
3. **Action deduplication**: stessa action (es: forward allo stesso indirizzo) non viene eseguita due volte
4. **Conflitti bloccanti**: `block` override `forward` (non puoi forwardare un'email bloccata)
5. **Audit**: ogni decisione di routing viene loggata con la regola che l'ha determinata

```python
ACTION_PRIORITY = {
    "block": 1,
    "quarantine": 2,
    "forward": 3,
    "move": 4,
    "tag": 5,
    "notify": 6,
}

def _deduplicate_actions(self, actions: list[dict]) -> list[dict]:
    has_block = any(a["type"] == "block" for a in actions)
    if has_block:
        return [a for a in actions if a["type"] in ("block", "notify", "tag")]

    seen = set()
    deduped = []
    for action in sorted(actions, key=lambda a: ACTION_PRIORITY.get(a["type"], 99)):
        key = (action["type"], action.get("to"), action.get("folder"))
        if key not in seen:
            seen.add(key)
            deduped.append(action)
    return deduped
```

---

## 8. Data Model

### 8.1 Schema SQL Completo (MySQL 5.0.67)

```sql
-- === NOTE MySQL 5.0.67 ===
-- UUID generati lato applicazione (Python uuid4) poiché MySQL 5.0 non ha UUID nativo come tipo.
-- CHAR(36) per colonne UUID. Nessun supporto nativo per array (TEXT[] → TEXT separato da virgole
-- o tabella di join) e per JSON/JSONB (→ TEXT, parsing lato applicazione).
-- Solo una colonna TIMESTAMP con auto-init per tabella; le altre date gestite via applicazione.

-- === ACCOUNTS (creata per prima perché referenziata da emails) ===

-- Singolo account Vianova IMAP. La tabella permette di gestire
-- la configurazione di connessione in modo strutturato.
CREATE TABLE accounts (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    email_address   VARCHAR(255) NOT NULL,
    imap_host       VARCHAR(255) NOT NULL,             -- es: imap.vianova.it
    imap_port       INT NOT NULL DEFAULT 993,
    imap_username   VARCHAR(255) NOT NULL,
    imap_password   VARCHAR(255) NOT NULL,             -- encrypted lato app
    status          VARCHAR(20) DEFAULT 'active',
    last_sync_at    DATETIME,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_accounts_email (email_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === CORE TABLES ===

CREATE TABLE emails (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    message_id      VARCHAR(255) NOT NULL,             -- RFC Message-ID header
    account_id      CHAR(36) NOT NULL,
    from_address    VARCHAR(320) NOT NULL,
    from_display    VARCHAR(255),
    to_addresses    TEXT NOT NULL,                      -- lista separata da virgole
    cc_addresses    TEXT,                               -- lista separata da virgole
    subject         TEXT,
    date_sent       DATETIME,
    date_received   DATETIME NOT NULL,
    body_text       MEDIUMTEXT,
    body_html       MEDIUMTEXT,
    raw_size_bytes  INT,
    has_attachments TINYINT(1) DEFAULT 0,
    processing_status VARCHAR(20) DEFAULT 'pending',   -- pending, processing, completed, failed
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME,
    UNIQUE KEY uq_emails_message_id (message_id),
    KEY idx_emails_account_date (account_id, date_received),
    KEY idx_emails_from (from_address),
    KEY idx_emails_status (processing_status),
    CONSTRAINT fk_emails_account FOREIGN KEY (account_id) REFERENCES accounts(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === HEADERS ===

CREATE TABLE email_headers (
    id          CHAR(36) NOT NULL PRIMARY KEY,
    email_id    CHAR(36) NOT NULL,
    header_name VARCHAR(255) NOT NULL,
    header_value TEXT NOT NULL,
    KEY idx_headers_email (email_id),
    CONSTRAINT fk_headers_email FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === ATTACHMENTS ===

CREATE TABLE email_attachments (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    email_id        CHAR(36) NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    content_type    VARCHAR(127) NOT NULL,
    size_bytes      INT NOT NULL,
    hash_sha256     CHAR(64) NOT NULL,
    storage_path    VARCHAR(512),                      -- path relativo nella cartella allegati del progetto
    scan_status     VARCHAR(20) DEFAULT 'pending',     -- pending, clean, infected, error
    scan_result     TEXT,                               -- JSON lato app
    KEY idx_attachments_email (email_id),
    CONSTRAINT fk_attachments_email FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === SECURITY RESULTS ===

CREATE TABLE security_results (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    email_id        CHAR(36) NOT NULL,
    verdict         VARCHAR(20) NOT NULL,              -- SAFE, SUSPICIOUS, DANGEROUS
    risk_score      TINYINT UNSIGNED NOT NULL,          -- 0-100, validazione lato app
    spf_pass        TINYINT(1),
    dkim_pass       TINYINT(1),
    dmarc_pass      TINYINT(1),
    phishing_score  TINYINT UNSIGNED,
    flags           TEXT,                               -- lista separata da virgole
    details         TEXT,                               -- JSON lato app
    analyzed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_security_email (email_id),
    CONSTRAINT fk_security_email FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === COUNTRY RESULTS ===

CREATE TABLE country_results (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    email_id        CHAR(36) NOT NULL,
    country         VARCHAR(100) NOT NULL,
    country_code    CHAR(2),                           -- ISO 3166-1 alpha-2
    confidence      DECIMAL(3,2) NOT NULL,
    detection_method VARCHAR(50) NOT NULL,
    signals         TEXT,                               -- JSON lato app
    analyzed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_country_email (email_id),
    CONSTRAINT fk_country_email FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === CONTENT RESULTS ===

CREATE TABLE content_results (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    email_id        CHAR(36) NOT NULL,
    category        VARCHAR(50) NOT NULL,
    category_confidence DECIMAL(3,2),
    summary         TEXT,
    sentiment       VARCHAR(20),
    urgency         VARCHAR(20),
    entities        TEXT,                               -- JSON lato app
    language        VARCHAR(10),
    analyzed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_content_email (email_id),
    CONSTRAINT fk_content_email FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === ROUTING ===

CREATE TABLE routing_rules (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    priority        INT NOT NULL,
    enabled         TINYINT(1) DEFAULT 1,
    conditions      TEXT NOT NULL,                     -- JSON lato app
    condition_logic VARCHAR(10) DEFAULT 'AND',
    actions         TEXT NOT NULL,                     -- JSON lato app
    stop_processing TINYINT(1) DEFAULT 0,
    created_by      CHAR(36),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME,
    KEY idx_rules_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE routing_logs (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    email_id        CHAR(36) NOT NULL,
    rule_id         CHAR(36),
    rule_name       VARCHAR(255),
    action_type     VARCHAR(50) NOT NULL,
    action_details  TEXT,                               -- JSON lato app
    executed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success         TINYINT(1) DEFAULT 1,
    error_message   TEXT,
    KEY idx_routing_logs_email (email_id),
    CONSTRAINT fk_routing_logs_email FOREIGN KEY (email_id) REFERENCES emails(id),
    CONSTRAINT fk_routing_logs_rule FOREIGN KEY (rule_id) REFERENCES routing_rules(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- === AUDIT LOG ===

CREATE TABLE audit_log (
    id              CHAR(36) NOT NULL PRIMARY KEY,
    event_type      VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(100),
    entity_id       CHAR(36),
    actor           VARCHAR(255),
    details         TEXT,                               -- JSON lato app
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_audit_time (created_at),
    KEY idx_audit_entity (entity_type, entity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
```

### 8.2 Storage Decision: SQL vs NoSQL

| Aspetto          | MySQL 5.0.67 (scelto)                         | MongoDB                 | Motivazione                                              |
|------------------|-----------------------------------------------|-------------------------|----------------------------------------------------------|
| Schema email     | ✅ Strutturato, TEXT per dati semi-strutturati | ✅ Flessibile            | JSON parsing lato applicazione, schema rigido dove serve |
| Query complesse  | ✅ JOIN, aggregazioni                          | ⚠️ Aggregation pipeline | Routing rules richiedono query composte                  |
| Transazioni      | ✅ ACID (InnoDB)                               | ⚠️ Limitato             | Audit log richiede consistenza                           |
| Full-text search | ✅ FULLTEXT index (MyISAM/InnoDB)              | ✅ Text index            | Entrambi adeguati                                        |
| Scale            | ✅ Replication master-slave                    | ✅ Sharding              | Replication sufficiente per i volumi previsti            |

**Decisione**: MySQL 5.0.67 come unico datastore. Il rate limiting delle API AI è gestito in-process con librerie Python (`tenacity`, `asyncio.Semaphore`). Il caching non è necessario per il volume previsto (centinaia di email/giorno).

> **Nota**: MySQL 5.0.67 non supporta nativamente JSON (introdotto in 5.7) né tipi array. I campi semi-strutturati (conditions, actions, entities, details, signals) sono memorizzati come TEXT e serializzati/deserializzati lato applicazione (Python `json.dumps`/`json.loads`). La validazione dei dati JSON è responsabilità del layer applicativo.

---

## 9. Processing e Performance

### 9.1 Volume Previsto

**Target**: centinaia di email/giorno su un singolo account Vianova. Un singolo processo Python gestisce agevolmente questo volume con processing sincrono sequenziale.

### 9.2 Pipeline Sincrona

Ogni email viene processata in sequenza attraverso tutti gli step della pipeline all'interno dello stesso processo. Con la pipeline NLP locale, il processing di ogni email richiede ~1-3s (spaCy + classificazione ML), ampiamente sostenibile per il volume previsto.

```python
class EmailPipeline:
    def __init__(self, db, security_engine, country_detector,
                 content_analyzer, routing_engine):
        self.db = db
        self.security = security_engine
        self.country = country_detector
        self.content = content_analyzer
        self.routing = routing_engine

    def process(self, email_data: dict) -> dict:
        """Pipeline sincrona: ogni email attraversa tutti gli step in sequenza."""
        email_id = self.db.save_email(email_data)

        try:
            self.db.update_status(email_id, "processing")

            # Step 1: Security
            security_result = self.security.analyze(email_data)
            self.db.save_security_result(email_id, security_result)

            if security_result.verdict == SecurityVerdict.DANGEROUS:
                actions = self.routing.evaluate_fast_track(email_id, security_result)
                self._execute_actions(email_id, actions)
                self.db.update_status(email_id, "completed")
                return {"email_id": email_id, "fast_track": True}

            # Step 2: Country Detection
            country_result = self.country.detect(email_data)
            self.db.save_country_result(email_id, country_result)

            # Step 3: Content Analysis (NLP locale)
            content_result = self.content.analyze(email_data)
            self.db.save_content_result(email_id, content_result)

            # Step 4: Routing
            context = {
                "security": security_result,
                "country": country_result,
                "content": content_result,
                "email": email_data,
            }
            actions = self.routing.evaluate(context)
            self._execute_actions(email_id, actions)

            self.db.update_status(email_id, "completed")
            return {"email_id": email_id, "actions": actions}

        except Exception as e:
            self.db.update_status(email_id, "failed")
            self.db.log_error(email_id, str(e))
            raise

    def _execute_actions(self, email_id: str, actions: list[dict]):
        for action in actions:
            try:
                self.routing.execute_action(email_id, action)
                self.db.log_routing(email_id, action, success=True)
            except Exception as e:
                self.db.log_routing(email_id, action, success=False, error=str(e))
```

### 9.3 Background Processing con FastAPI

Le email vengono processate in background tramite `BackgroundTasks` di FastAPI, senza bloccare le API REST:

```python
from fastapi import BackgroundTasks

@app.post("/webhooks/new-email")
async def on_new_email(email_data: dict, background_tasks: BackgroundTasks):
    """Riceve notifica di nuova email e avvia processing in background."""
    background_tasks.add_task(pipeline.process, email_data)
    return {"status": "accepted"}
```

Per il polling IMAP, un loop periodico processa le email una alla volta:

```python
import schedule
import time

def poll_and_process():
    ingestion = IMAPIngestionService(host, port, credentials)
    ingestion.connect()
    new_emails = ingestion.poll()
    for email_data in new_emails:
        try:
            pipeline.process(email_data)
        except Exception as e:
            logger.error(f"Failed to process {email_data['message_id']}: {e}")

schedule.every(60).seconds.do(poll_and_process)

while True:
    schedule.run_pending()
    time.sleep(1)
```

### 9.4 [FEATURE FUTURA] Rate Limiting per API AI

> **Nota**: questa sezione diventa rilevante solo quando verra attivata l'integrazione con LLM cloud (OpenAI / Anthropic). Con l'approccio locale attuale, non sono necessarie chiamate API esterne per la content analysis.

Quando l'integrazione LLM sara attiva, il rate limiting delle chiamate sara gestito in-process:

```python
import time
import threading

class SimpleRateLimiter:
    def __init__(self, max_calls_per_minute: int = 50):
        self.max_calls = max_calls_per_minute
        self.calls = []
        self.lock = threading.Lock()

    def acquire(self):
        """Blocca finché non è possibile effettuare una chiamata."""
        while True:
            with self.lock:
                now = time.time()
                self.calls = [t for t in self.calls if now - t < 60]
                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return
            time.sleep(1)
```

---

## 10. Tech Stack Consigliato

### Backend

| Layer         | Tecnologia       | Motivazione                              |
|---------------|------------------|------------------------------------------|
| Language      | **Python 3.12+** | Ecosistema NLP/ML, librerie email mature |
| Framework API | **FastAPI**      | Async native, auto-docs, type safety     |

### NLP (Locale)

| Funzione            | Tecnologia                      | Motivazione                                      |
|---------------------|---------------------------------|--------------------------------------------------|
| Entity Extraction   | **spaCy** (`it_core_news_lg`)   | NER locale, veloce, nessuna dipendenza esterna   |
| Text Classification | **scikit-learn** (TF-IDF + SVM) | Classificazione ML locale + rule-based           |
| Summarization       | **scikit-learn** (TF-IDF)       | Summarization estrattiva locale                  |
| Language Detection  | **langdetect** / **fasttext**   | Leggero, accurato                                |

### [FUTURO] AI Cloud

| Funzione     | Tecnologia                   | Motivazione                                    |
|--------------|------------------------------|------------------------------------------------|
| LLM API      | **OpenAI GPT-4o-mini**       | Costo/performance ottimale per classificazione |
| LLM Fallback | **Anthropic Claude 3 Haiku** | Diversificazione provider                      |

### Database & Storage

| Funzione           | Tecnologia                       | Motivazione                                |
|--------------------|----------------------------------|--------------------------------------------|
| Primary DB         | **MySQL 5.0.67**                 | ACID (InnoDB), ampia compatibilità, maturo                |
| Allegati & raw     | **Filesystem locale**            | Cartella nel progetto sul server, nessuna dipendenza esterna |

### Infrastructure

| Funzione   | Tecnologia                                    | Motivazione                 |
|------------|-----------------------------------------------|-----------------------------|
| CI/CD      | **GitHub Actions**                            | Automazione test e deploy   |
| Monitoring | **Prometheus + Grafana**                      | Metriche, alerting          |
| Logging    | **Loki** o **ELK Stack**                      | Log centralizzati           |
| Secrets    | **File `.env`** + encryption applicativa       | Credenziali IMAP, API keys  |

### Security Tools

| Funzione      | Tecnologia                                              |
|---------------|---------------------------------------------------------|
| Antivirus     | **ClamAV** (daemon)                                     |
| Malware Rules | **YARA**                                                |
| Deep Scan     | **VirusTotal API** (tier 2)                             |
| Email Auth    | **authheaders** (Python lib per SPF/DKIM/DMARC parsing) |

---

## 11. Rischi e Mitigazioni

### 11.1 Falsi Positivi Phishing

| Rischio                                | Impatto                             | Mitigazione                                                    |
|----------------------------------------|-------------------------------------|----------------------------------------------------------------|
| Email legittima classificata DANGEROUS | Mancata ricezione, perdita business | Quarantena (non delete), review queue, whitelist domini fidati |
| Newsletter legittima → spam            | Comunicazioni perse                 | Learning from user feedback, sender reputation DB              |

**Mitigazione tecnica:**
- Whitelist configurabile per dominio/mittente
- Feedback loop: utente marca "non phishing" → aggiorna modello
- Quarantena con notifica (mai silent block)
- Double-threshold: SUSPICIOUS → review umano, solo DANGEROUS → auto-block

### 11.2 Errori Routing

| Rischio                            | Impatto                     | Mitigazione                                             |
|------------------------------------|-----------------------------|---------------------------------------------------------|
| Email instradata al team sbagliato | Ritardo, data leak interno  | Audit log completo, undo action entro 5 min             |
| Regole in conflitto                | Comportamento imprevedibile | Rule validator, dry-run mode, test suite                |
| Rule loop (forward → re-ingestion) | Infinite loop               | Loop detection (max 3 hops), `X-Forwarded-Count` header |

### 11.3 Performance NLP Locale

| Rischio                                   | Impatto                             | Mitigazione                                                         |
|-------------------------------------------|-------------------------------------|---------------------------------------------------------------------|
| Modello spaCy lento su email molto lunghe | Ritardo nel processing              | Troncare body a 5000 caratteri, timeout per singola email           |
| Modello ML non ancora trainato            | Classificazione solo rule-based     | Rule-based come fallback affidabile, training incrementale          |
| Qualità summarization estrattiva limitata | Riassunti meno precisi rispetto LLM | Accettabile per volume attuale, LLM cloud come evoluzione futura   |

### 11.3.1 [FUTURO] Rischi API AI Cloud

> Quando verra attivata l'integrazione LLM cloud:

| Rischio                   | Impatto                      | Mitigazione                                                      |
|---------------------------|------------------------------|------------------------------------------------------------------|
| OpenAI API timeout (>10s) | Backlog email non processate | Timeout 15s, fallback a classificazione locale                   |
| API down per ore          | Nessuna content analysis AI  | Circuit breaker, fallback automatico su pipeline locale          |
| Costi imprevisti          | Budget overrun               | Rate limiting, batch processing, monitoring costi                |

**Pattern circuit breaker (da implementare con integrazione LLM):**
```python
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def call_openai(prompt: str) -> str:
    """Se 5 failure consecutive, apri circuito per 60s e usa fallback."""
    response = await openai_client.chat(...)
    return response

async def analyze_content(text: str) -> dict:
    try:
        return await call_openai(text)
    except CircuitBreakerError:
        return rule_based_classify(text)  # fallback locale
```

### 11.4 Sicurezza Dati

| Rischio                       | Impatto                           | Mitigazione                                            |
|-------------------------------|-----------------------------------|--------------------------------------------------------|
| Leak credenziali IMAP         | Accesso non autorizzato a mailbox | Encryption at rest (AES-256), password non in chiaro   |
| Email in transit non cifrate  | Intercettazione                   | TLS everywhere per ogni comunicazione                  |
| Accesso non autorizzato al DB | Data breach                       | RBAC, audit log, network isolation, encryption         |
| LLM data retention            | Contenuto email inviato a terzi   | API terms (no-training clause), anonymization pre-send |

**Misure di sicurezza obbligatorie:**
- Credenziali IMAP Vianova cifrate con AES-256-GCM a riposo
- TLS 1.3 per ogni comunicazione inter-servizio
- Network segmentation: DB non esposto pubblicamente
- Audit log immutabile (append-only)
- PII masking nei log applicativi
- Retention policy: email raw cancellate dopo 90 giorni (configurabile)

---

## 12. Implementation Path — Step by Step (Dettagliato)

> Ogni punto va implementato singolarmente e verificato prima di procedere al successivo.
> Il formato è `Fase.Step` (es: 0.1, 0.2, ...). Ogni step è un'unità atomica di lavoro.

---

### Fase 0: Setup Progetto

- [x] **0.1** — Creare la cartella radice del progetto e inizializzare il repository Git
- [x] **0.2** — Creare il file `.gitignore` (escludere `.env`, `__pycache__/`, `*.pyc`, `data/attachments/`, `models/*.pkl`, `venv/`)
- [x] **0.3** — Definire la struttura directory del progetto:
  ```
  project/
  ├── src/
  │   ├── ingestion/        # Fase 1
  │   ├── security/         # Fase 2
  │   ├── country/          # Fase 3
  │   ├── content/          # Fase 4
  │   ├── routing/          # Fase 5
  │   ├── api/              # Fase 7
  │   ├── db/               # connessione e query MySQL
  │   └── utils/            # logging, config, helpers
  ├── tests/
  ├── data/
  │   └── attachments/      # storage locale allegati
  ├── models/               # modelli ML serializzati (.pkl)
  ├── config/
  ├── requirements.txt
  ├── .env.example
  └── main.py
  ```
- [x] **0.4** — Creare il file `requirements.txt` con le dipendenze base:
  ```
  # Core
  fastapi
  uvicorn
  python-dotenv
  structlog
  # Database
  mysql-connector-python
  # NLP locale
  spacy
  scikit-learn
  langdetect
  beautifulsoup4
  joblib
  # Security
  yara-python
  tldextract
  # Utilities
  tenacity
  schedule
  ```
- [x] **0.5** — Creare il virtual environment e installare le dipendenze da `requirements.txt`
- [x] **0.6** — Scaricare il modello spaCy italiano: `python -m spacy download it_core_news_lg`
- [x] **0.7** — Creare il file `.env.example` con tutte le variabili necessarie:
  ```
  # Database
  DB_HOST=
  DB_PORT=3306
  DB_USER=
  DB_PASSWORD=
  DB_NAME=
  # IMAP Vianova
  IMAP_HOST=
  IMAP_PORT=993
  IMAP_USERNAME=
  IMAP_PASSWORD=
  # App
  LOG_LEVEL=INFO
  ATTACHMENTS_DIR=data/attachments
  POLL_INTERVAL_SECONDS=60
  ```
- [x] **0.8** — Creare il file `.env` con i valori reali (copiare da `.env.example` e compilare)
- [x] **0.9** — Creare il modulo `src/utils/config.py`: caricamento `.env` con `python-dotenv`, validazione che tutte le variabili obbligatorie siano presenti, esposizione come oggetto config
- [x] **0.10** — Creare il modulo `src/utils/logger.py`: configurazione `structlog` con output JSON, livello da config, timestamp ISO
- [x] **0.11** — Creare il modulo `src/db/connection.py`: connessione a MySQL con `mysql-connector-python`, funzione `get_connection()` che legge parametri da config
- [x] **0.12** — Creare lo script `src/db/init_schema.sql` con tutto lo schema SQL dalla sezione 8 del documento (tabelle: accounts, emails, email_headers, email_attachments, security_results, country_results, content_results, routing_rules, routing_logs, audit_log)
- [x] **0.13** — Creare lo script `src/db/init_db.py` che legge `init_schema.sql` e lo esegue su MySQL per creare tutte le tabelle
- [x] **0.14** — Eseguire `init_db.py` e verificare che tutte le tabelle siano state create correttamente nel database
- [x] **0.15** — Inserire il record del singolo account Vianova nella tabella `accounts` (tramite script o manualmente)
- [x] **0.16** — Creare `main.py` come entry point: carica config, inizializza logger, testa connessione DB, stampa messaggio di avvio
- [x] **0.17** — Verificare che `python main.py` si avvia senza errori e logga correttamente

---

### Fase 1: Email Ingestion

- [x] **1.1** — Creare il file `src/ingestion/__init__.py`
- [x] **1.2** — Creare la classe `IMAPClient` in `src/ingestion/imap_client.py` con `__init__` che accetta host, port, username, password da config
- [x] **1.3** — Implementare il metodo `connect()`: connessione IMAP4_SSL, login con credenziali, selezione INBOX
- [x] **1.4** — Implementare il metodo `disconnect()`: logout e chiusura connessione sicura
- [x] **1.5** — Testare manualmente: connettersi all'account Vianova e verificare che il login riesca
- [x] **1.6** — Implementare il metodo `poll()`: ricerca email non lette (`UNSEEN`), fetch dei dati grezzi (RFC822), restituzione lista di bytes
- [x] **1.7** — Testare `poll()`: verificare che recuperi correttamente le email non lette dall'account Vianova
- [x] **1.8** — Creare la classe `MIMEParser` in `src/ingestion/mime_parser.py`
- [x] **1.9** — Implementare il metodo `parse(raw_bytes)` → dict: parsing con `email.message_from_bytes`, estrazione `message_id`, `from`, `to`, `cc`, `subject`, `date`
- [x] **1.10** — Implementare il metodo `_extract_headers(msg)` → dict: iterazione su tutti gli header del messaggio, restituzione come dizionario chiave-valore
- [x] **1.11** — Implementare il metodo `_extract_body(msg, content_type)` → str: walk delle parti MIME, estrazione body `text/plain` e `text/html`
- [x] **1.12** — Implementare il metodo `_extract_attachments(msg)` → list[dict]: walk delle parti con `content_disposition == "attachment"`, per ciascuna estrarre filename, content_type, size, hash SHA256, raw bytes
- [x] **1.13** — Testare `MIMEParser` con almeno 3 email reali diverse: solo testo, HTML, con allegato
- [x] **1.14** — Creare il modulo `src/db/email_repository.py` con la classe `EmailRepository`
- [x] **1.15** — Implementare il metodo `save_email(parsed_data)`: INSERT nella tabella `emails`, restituire l'`id` generato (UUID4)
- [x] **1.16** — Implementare il metodo `save_headers(email_id, headers_dict)`: INSERT multiplo nella tabella `email_headers`
- [x] **1.17** — Testare: parsare un'email e salvarla in DB, verificare i dati nelle tabelle `emails` e `email_headers`
- [x] **1.18** — Creare la cartella `data/attachments/` se non esiste (con creazione automatica all'avvio)
- [x] **1.19** — Creare il modulo `src/ingestion/attachment_storage.py` con la classe `AttachmentStorage`
- [x] **1.20** — Implementare il metodo `save(email_id, attachment_data)`: salvare il file su disco in `data/attachments/{email_id}/{filename}`, restituire il path relativo
- [x] **1.21** — Implementare il metodo `save_metadata(email_id, attachment_meta, storage_path)`: INSERT nella tabella `email_attachments`
- [x] **1.22** — Testare: inviare email con allegato all'account Vianova, verificare che file e metadata siano salvati correttamente
- [x] **1.23** — Implementare il metodo `idle_listen()` in `IMAPClient`: invio comando IMAP IDLE, ascolto continuo, trigger `poll()` quando arriva un EXISTS
- [x] **1.24** — Testare IMAP IDLE: avviare il listener, inviare un'email all'account Vianova, verificare che venga rilevata automaticamente
- [x] **1.25** — Implementare retry logic con `tenacity` nel metodo `poll()`: exponential backoff, max 5 tentativi, log degli errori
- [x] **1.26** — Implementare reconnection automatica in `idle_listen()`: se la connessione cade, riconnettere con backoff
- [x] **1.27** — Implementare il metodo `update_status(email_id, status)` in `EmailRepository` per aggiornare `processing_status`
- [x] **1.28** — Creare la classe `IngestionService` in `src/ingestion/service.py` che orchestra: `IMAPClient` → `MIMEParser` → `EmailRepository` + `AttachmentStorage`, aggiornando lo status (`pending` → `processing` → `completed`/`failed`)
- [x] **1.29** — Integrare `IngestionService` in `main.py` con loop di polling tramite `schedule`
- [x] **1.30** — Test end-to-end completo: avviare il sistema, inviare 5 email diverse all'account Vianova (solo testo, HTML, con allegato, con CC, con header complessi), verificare che tutte siano salvate in DB e su filesystem

---

### Fase 2: Security Engine

**Header Analysis:**
- [x] **2.1** — Creare il file `src/security/__init__.py`
- [x] **2.2** — Creare la classe `HeaderAnalyzer` in `src/security/header_analyzer.py`
- [x] **2.3** — Implementare `_check_spf(headers)`: parsing campo `Authentication-Results`, verificare presenza `spf=pass`, assegnare risk_contribution (0 se pass, 20 se fail)
- [x] **2.4** — Implementare `_check_dkim(headers)`: parsing `dkim=pass/fail` da `Authentication-Results`, risk_contribution 0/15
- [x] **2.5** — Implementare `_check_dmarc(headers)`: parsing `dmarc=pass/fail` da `Authentication-Results`, risk_contribution 0/25
- [x] **2.6** — Implementare `_check_return_path(headers)`: confronto dominio `From` vs `Return-Path`, risk_contribution 0/15 se mismatch
- [x] **2.7** — Implementare `_check_reply_to(headers)`: confronto dominio `From` vs `Reply-To`, risk_contribution 0/10 se mismatch
- [x] **2.8** — Implementare `_analyze_received_chain(headers)`: parsing chain degli header `Received`, estrazione IP originante
- [x] **2.9** — Implementare il metodo pubblico `analyze(headers)` → dict che chiama tutti i check e restituisce i risultati aggregati
- [x] **2.10** — Testare `HeaderAnalyzer` con header di email reali ricevute sull'account Vianova

**Phishing Detection:**
- [x] **2.11** — Creare la classe `PhishingDetector` in `src/security/phishing_detector.py`
- [x] **2.12** — Implementare `_extract_urls(body_html)`: estrazione di tutti gli URL dal body (regex + parsing href da HTML)
- [x] **2.13** — Implementare `_analyze_urls(urls)`: controllo URL shortener, IP in URL, subdomain eccessivi, punycode/IDN, calcolo risk score (cap 50)
- [x] **2.14** — Implementare `_check_patterns(body_text)`: matching con pattern regex sospetti (urgenza, credenziali, premi), calcolo risk score
- [x] **2.15** — Implementare `_check_homoglyphs(from_field)`: mappa caratteri Cyrillic/lookalike → ASCII, detection di sostituzione, risk score 30 se trovato
- [x] **2.16** — Implementare `_check_display_name_spoof(from_field)`: detection di display name che imita domini noti (es: "PayPal Security <random@evil.com>")
- [x] **2.17** — Implementare il metodo pubblico `analyze(email_data)` → dict con phishing_score aggregato
- [x] **2.18** — Testare `PhishingDetector` con email di phishing note (campioni da PhishTank o creati ad hoc)

**Malware Scanning:**
- [x] **2.19** — Creare la classe `MalwareScanner` in `src/security/malware_scanner.py`
- [x] **2.20** — Definire le liste `DANGEROUS_EXTENSIONS` e `SUSPICIOUS_EXTENSIONS` come costanti
- [x] **2.21** — Implementare `_check_extension(filename)`: confronto estensione con blocklist, restituire livello di rischio
- [x] **2.22** — Implementare integrazione ClamAV: connessione al daemon `clamd`, scan allegato tramite socket, parsing risultato
- [x] **2.23** — Implementare `_scan_yara(attachment_bytes)`: caricamento regole YARA base, scanning allegato, restituzione matches
- [x] **2.24** — Definire un set iniziale di regole YARA per pattern comuni (macro in Office, script embedded, PE headers)
- [x] **2.25** — Implementare il metodo pubblico `scan_attachment(attachment_bytes, metadata)` → dict che orchestra i 3 livelli di scan
- [x] **2.26** — Testare `MalwareScanner` con file di test: `.exe`, `.pdf` pulito, `.docm` con macro, file rinominato

**Risk Scoring:**
- [x] **2.27** — Creare la classe `RiskScorer` in `src/security/risk_scorer.py`
- [x] **2.28** — Definire i pesi per ogni componente: header 25%, phishing 30%, attachment 25%, reputation 10%, anomaly 10%
- [x] **2.29** — Definire le soglie: SAFE (0-29), SUSPICIOUS (30-69), DANGEROUS (70-100)
- [x] **2.30** — Implementare il metodo `calculate(analysis)` → `SecurityResult`: calcolo score pesato, determinazione verdetto
- [x] **2.31** — Implementare `_collect_flags(analysis)`: raccolta di tutti i flag attivi (es: `spf_fail`, `homoglyph_detected`, `dangerous_extension`)
- [x] **2.32** — Creare il modulo `src/db/security_repository.py` con metodo `save_result(email_id, security_result)`: INSERT nella tabella `security_results`
- [x] **2.33** — Creare la classe `SecurityEngine` in `src/security/engine.py` che orchestra `HeaderAnalyzer` + `PhishingDetector` + `MalwareScanner` + `RiskScorer`, salva risultato in DB
- [x] **2.34** — Testare `SecurityEngine` end-to-end: passare email reali (sicure e sospette), verificare verdetti e score in DB

---

### Fase 3: Country Detection

- [x] **3.1** — Creare il file `src/country/__init__.py`
- [x] **3.2** — Creare la classe `CountryDetector` in `src/country/detector.py`
- [x] **3.3** — Creare il file `src/country/maps.py` con la mappa `COUNTRY_TLD_MAP`: almeno 200 TLD country code → nome paese (it → Italy, fr → France, de → Germany, ecc.)
- [x] **3.4** — Implementare `_detect_from_tld(from_address)`: estrazione TLD con `tldextract`, lookup in `COUNTRY_TLD_MAP`, gestione TLD composti (es: `co.uk` → uk)
- [x] **3.5** — Implementare il controllo dominio email completo: per domini gTLD (.com, .org, .net), verificare se il dominio di posta (es: `poste.it`, `laposte.fr`) contiene un TLD riconoscibile come segnale aggiuntivo
- [x] **3.6** — Testare TLD detection e domain detection con almeno 10 indirizzi email di paesi diversi (`.it`, `.fr`, `.de`, `.es`, `.co.uk`, `.com`, ecc.)
- [x] **3.7** — Creare la mappa `PHONE_PREFIX_MAP` in `src/country/maps.py`: prefisso telefonico → paese (39 → Italy, 33 → France, ecc.)
- [x] **3.8** — Implementare `_detect_from_phone(body_text)`: ricerca pattern prefisso telefonico negli ultimi 500 caratteri (firma), lookup in mappa
- [x] **3.9** — Testare phone prefix detection con firme email contenenti numeri di telefono internazionali
- [x] **3.10** — Creare la mappa `LANGUAGE_COUNTRY_MAP` in `src/country/maps.py`: codice lingua → paese primario (it → Italy, fr → France, ecc.)
- [x] **3.11** — Implementare `_detect_language(body_text)`: detection lingua con `langdetect`, lookup in mappa
- [x] **3.12** — Testare language detection con email in italiano, inglese, francese, tedesco, spagnolo
- [x] **3.13** — Implementare `_detect_from_ip(headers)`: estrazione IP da header `Received` e `X-Originating-IP`, geolocalizzazione con database GeoLite2 locale
- [x] **3.14** — Implementare `_resolve_signals(signals)`: combinazione segnali multipli con confidence pesata (TLD 0.7, phone 0.8, language 0.5, IP 0.6), risoluzione conflitti
- [x] **3.15** — Creare il modulo `src/db/country_repository.py` con metodo `save_result(email_id, country_result)`: INSERT nella tabella `country_results`
- [x] **3.16** — Implementare il metodo pubblico `detect(email_data)` → dict che orchestra tutti i segnali e salva in DB
- [x] **3.17** — Testare country detection end-to-end con email di almeno 5 paesi diversi, verificare risultati in DB

---

### Fase 4: Content Analysis (Locale)

**Preprocessing:**
- [x] **4.1** — Creare il file `src/content/__init__.py`
- [x] **4.2** — Creare la classe `EmailPreprocessor` in `src/content/preprocessor.py`
- [x] **4.3** — Implementare strip HTML: parsing con `BeautifulSoup`, rimozione tag `script`/`style`/`head`, estrazione testo
- [x] **4.4** — Implementare normalizzazione whitespace: rimozione righe vuote multiple, normalizzazione spazi/tab
- [x] **4.5** — Implementare rimozione testo citato: detection di `>`, `On ... wrote:`, `--- Original Message ---` e troncamento
- [x] **4.6** — Implementare il metodo pubblico `process(email_data)` → str che orchestra i 3 step
- [x] **4.7** — Testare preprocessing con email HTML complesse, email con thread citati, email solo testo

**Classificazione:**
- [ ] **4.8** — Creare la classe `ContentClassifier` in `src/content/classifier.py`
- [ ] **4.9** — Definire i pattern regex `RULE_BASED_SIGNALS` per ogni categoria: invoice, marketing, spam, support, legal, hr, sales, personal
- [ ] **4.10** — Implementare `_rule_based_classify(text)` → dict: matching pattern per categoria, calcolo confidence in base al numero e forza dei match
- [ ] **4.11** — Testare classificazione rule-based con almeno 2 email per ogni categoria
- [ ] **4.12** — Preparare un dataset di training: raccogliere almeno 50-100 email etichettate per categoria (possono essere raccolte incrementalmente)
- [ ] **4.13** — Creare lo script `src/content/train_classifier.py`: caricamento dataset, pipeline TF-IDF + SVM con scikit-learn, salvataggio modello in `models/classifier.pkl`
- [ ] **4.14** — Trainare il modello e salvare il file `.pkl`
- [ ] **4.15** — Implementare `_ml_classify(text)` → dict: caricamento modello con `joblib.load`, predict + predict_proba, restituzione categoria e confidence
- [ ] **4.16** — Implementare il metodo pubblico `classify(text)` → dict: prima rule-based (se confidence > 0.85 → usa quello), altrimenti ML locale come fallback
- [ ] **4.17** — Testare classificazione ibrida end-to-end con email di ogni categoria

**Summarization:**
- [ ] **4.18** — Creare la classe `ContentSummarizer` in `src/content/summarizer.py`
- [ ] **4.19** — Implementare `_split_sentences(text)` → list: divisione testo in frasi tramite regex
- [ ] **4.20** — Implementare `_get_stopwords()` → list: stopwords italiano + inglese per TF-IDF
- [ ] **4.21** — Implementare `summarize(text, num_sentences=4)` → str: calcolo TF-IDF per frase, selezione delle N frasi con score piu alto, ricomposizione in ordine originale
- [ ] **4.22** — Testare summarization con email di diversa lunghezza (corte, medie, molto lunghe)

**Entity Extraction:**
- [ ] **4.23** — Creare la classe `EntityExtractor` in `src/content/entity_extractor.py`
- [ ] **4.24** — Implementare caricamento modello spaCy `it_core_news_lg` nel costruttore
- [ ] **4.25** — Implementare estrazione persone (`PER`) e organizzazioni (`ORG`) tramite spaCy NER
- [ ] **4.26** — Implementare estrazione date (`DATE`/`TIME`) tramite spaCy NER
- [ ] **4.27** — Implementare `_extract_amounts(text)` con regex: pattern per importi con simbolo valuta (€, $, £) e con codice valuta (EUR, USD)
- [ ] **4.28** — Implementare `_extract_references(text)` con regex: numeri fattura, ordine, ticket
- [ ] **4.29** — Implementare il metodo pubblico `extract(text)` → dict che orchestra tutte le estrazioni
- [ ] **4.30** — Testare entity extraction con email contenenti nomi, aziende, date, importi, riferimenti

**Integrazione:**
- [ ] **4.31** — Creare il modulo `src/db/content_repository.py` con metodo `save_result(email_id, content_result)`: INSERT nella tabella `content_results`
- [ ] **4.32** — Creare la classe `ContentAnalyzer` in `src/content/analyzer.py` che orchestra: `EmailPreprocessor` → `ContentClassifier` → `ContentSummarizer` → `EntityExtractor` → salvataggio DB
- [ ] **4.33** — Testare `ContentAnalyzer` end-to-end con email reali, verificare risultati in tabella `content_results`

---

### Fase 5: Routing Engine

**Condition Evaluator:**
- [ ] **5.1** — Creare il file `src/routing/__init__.py`
- [ ] **5.2** — Creare la classe `ConditionEvaluator` in `src/routing/condition_evaluator.py`
- [ ] **5.3** — Implementare gli operatori di confronto: `eq`, `neq`, `gt`, `gte`, `lt`, `contains`, `matches`, `in`, `not_in`
- [ ] **5.4** — Implementare `_resolve_field(field_path, context)`: risoluzione campi dot-notation (es: `security.risk_score` → `context["security"]["risk_score"]`)
- [ ] **5.5** — Implementare il metodo `evaluate(condition, context)` → bool
- [ ] **5.6** — Testare `ConditionEvaluator` con condizioni diverse su un contesto di esempio

**Rule Engine:**
- [ ] **5.7** — Creare la classe `RoutingEngine` in `src/routing/engine.py`
- [ ] **5.8** — Creare il modulo `src/db/routing_repository.py` con metodo `get_active_rules()` → list: SELECT regole attive ordinate per priority
- [ ] **5.9** — Implementare caricamento regole da DB nel costruttore di `RoutingEngine`
- [ ] **5.10** — Implementare `_matches(rule, email_context)` → bool: valutazione condizioni con logica AND/OR
- [ ] **5.11** — Implementare `evaluate(email_context)` → list[dict]: iterazione regole per priorità, raccolta azioni, gestione `stop_processing`
- [ ] **5.12** — Implementare `_deduplicate_actions(actions)`: rimozione azioni duplicate, risoluzione conflitti (block override forward)
- [ ] **5.13** — Testare rule engine con set di regole di esempio e diversi contesti email

**Action Executor:**
- [ ] **5.14** — Creare la classe `ActionExecutor` in `src/routing/action_executor.py`
- [ ] **5.15** — Implementare azione `block`: marcatura email come bloccata nel DB (`processing_status = 'blocked'`)
- [ ] **5.16** — Implementare azione `quarantine`: spostamento email nella cartella IMAP di review + flag nel DB
- [ ] **5.17** — Implementare azione `tag`: salvataggio tag associati all'email nel DB
- [ ] **5.18** — Implementare azione `notify`: invio notifica all'admin (email di alert tramite SMTP)
- [ ] **5.19** — Implementare azione `forward` come **stub disabilitato**: il metodo esiste ma logga un warning "forward action disabled — future feature" senza eseguire nulla
- [ ] **5.20** — Implementare il metodo pubblico `execute(email_id, action)` → bool che smista verso l'azione corretta
- [ ] **5.21** — Testare ogni azione singolarmente con email di test

**Logging e CRUD:**
- [ ] **5.22** — Implementare metodo `save_routing_log(email_id, rule_id, action, success, error)` in `routing_repository.py`: INSERT in `routing_logs`
- [ ] **5.23** — Implementare metodo `save_audit_log(event_type, entity_type, entity_id, actor, details)` in `src/db/audit_repository.py`: INSERT in `audit_log`
- [ ] **5.24** — Integrare logging automatico in `ActionExecutor`: ogni azione eseguita scrive in `routing_logs` e `audit_log`
- [ ] **5.25** — Creare API CRUD per regole di routing (`src/api/routing_rules.py`): GET lista, GET singola, POST crea, PUT modifica, DELETE elimina
- [ ] **5.26** — Implementare dry-run mode: endpoint che simula la valutazione delle regole su un'email senza eseguire azioni, restituendo le azioni che verrebbero applicate
- [ ] **5.27** — Testare CRUD regole via API (creare, modificare, disabilitare, eliminare una regola)
- [ ] **5.28** — Inserire nel DB le regole iniziali di routing (block DANGEROUS, quarantine SUSPICIOUS con score >= 60, auto-delete spam)

---

### Fase 6: Pipeline Completa e Integrazione

- [ ] **6.1** — Creare la classe `EmailPipeline` in `src/pipeline.py` che orchestra in sequenza: `IngestionService` → `SecurityEngine` → `CountryDetector` → `ContentAnalyzer` → `RoutingEngine` + `ActionExecutor`
- [ ] **6.2** — Implementare gestione degli errori nella pipeline: se uno step fallisce, marcare email come `failed` nel DB con dettaglio dell'errore, continuare con le email successive
- [ ] **6.3** — Implementare fast-track per email DANGEROUS: se il security engine da verdetto DANGEROUS, saltare country + content e andare direttamente al routing
- [ ] **6.4** — Integrare `EmailPipeline` in `main.py`: il loop di polling chiama `pipeline.process()` per ogni nuova email
- [ ] **6.5** — Test end-to-end pipeline completa: inviare email di diversi tipi (pulita, sospetta, con allegato pericoloso, in lingue diverse, con fattura) e verificare che ogni email attraversi tutti gli step con risultati corretti in DB

---

### Fase 7: API & Dashboard

**API REST:**
- [ ] **7.1** — Creare l'app FastAPI in `src/api/app.py` con configurazione CORS e middleware
- [ ] **7.2** — Implementare endpoint `GET /api/emails`: lista email con paginazione e filtri (status, date range, category)
- [ ] **7.3** — Implementare endpoint `GET /api/emails/{id}`: dettaglio singola email con tutti i risultati di analisi (security, country, content, routing logs)
- [ ] **7.4** — Implementare endpoint `GET /api/stats`: statistiche aggregate (email per giorno, distribuzione per categoria, distribuzione risk score, email per paese)
- [ ] **7.5** — Implementare endpoint `GET /api/routing-rules` + `POST` + `PUT` + `DELETE`: CRUD regole (collegare al codice già implementato in Fase 5)
- [ ] **7.6** — Implementare autenticazione JWT: endpoint `POST /api/auth/login`, middleware di verifica token su tutti gli endpoint protetti
- [ ] **7.7** — Testare tutti gli endpoint API con tool (curl, Postman, httpie)

**Frontend (React):**
- [ ] **7.8** — Inizializzare progetto frontend React nella cartella `frontend/`
- [ ] **7.9** — Implementare pagina login con form username/password
- [ ] **7.10** — Implementare pagina lista email: tabella con colonne (data, mittente, oggetto, categoria, risk score, paese, stato), paginazione, filtri
- [ ] **7.11** — Implementare pagina dettaglio email: visualizzazione body, metadata arricchiti (security verdict, country, summary, entities), routing log
- [ ] **7.12** — Implementare pagina gestione regole di routing: lista regole, form creazione/modifica, toggle abilita/disabilita, dry-run
- [ ] **7.13** — Implementare dashboard analytics: grafici volume email per giorno, distribuzione risk score, distribuzione per paese, distribuzione per categoria
- [ ] **7.14** — Testare frontend collegato alle API: navigazione completa, visualizzazione dati reali

---

### Fase 8: Testing & Hardening

- [ ] **8.1** — Scrivere unit test per `IMAPClient` e `MIMEParser` (mock connessione IMAP)
- [ ] **8.2** — Scrivere unit test per `HeaderAnalyzer`, `PhishingDetector`, `MalwareScanner`, `RiskScorer`
- [ ] **8.3** — Scrivere unit test per `CountryDetector` (tutti i segnali)
- [ ] **8.4** — Scrivere unit test per `ContentClassifier`, `ContentSummarizer`, `EntityExtractor`
- [ ] **8.5** — Scrivere unit test per `ConditionEvaluator`, `RoutingEngine`, `ActionExecutor`
- [ ] **8.6** — Verificare unit test coverage >= 80%
- [ ] **8.7** — Scrivere integration test della pipeline end-to-end: email in input → tutti gli step → risultato in DB
- [ ] **8.8** — Scrivere integration test per ogni endpoint API
- [ ] **8.9** — Load test: simulare 1000 email in un giorno, misurare tempi di processing e consumo risorse
- [ ] **8.10** — Security audit: verificare che credenziali IMAP siano cifrate, SQL injection non possibile (prepared statements), input sanitizzato
- [ ] **8.11** — Verifica sicurezza credenziali: password IMAP cifrata nel `.env`, nessuna credenziale in chiaro nei log, nessun dato sensibile esposto nelle API

---

### Fase 9: Deploy sul Server di Produzione

- [ ] **9.1** — Preparare il server: verificare che Python 3.12+, MySQL 5.0.67 e ClamAV siano installati e funzionanti
- [ ] **9.2** — Clonare il repository sul server
- [ ] **9.3** — Creare virtual environment e installare dipendenze
- [ ] **9.4** — Scaricare modello spaCy sul server
- [ ] **9.5** — Configurare file `.env` con credenziali di produzione (DB, IMAP Vianova)
- [ ] **9.6** — Eseguire `init_db.py` per creare le tabelle nel database di produzione
- [ ] **9.7** — Inserire il record dell'account Vianova nel DB di produzione
- [ ] **9.8** — Inserire le regole di routing iniziali nel DB di produzione
- [ ] **9.9** — Avviare il sistema e verificare che si connetta correttamente a IMAP Vianova e MySQL
- [ ] **9.10** — Inviare 5 email di test e verificare processing completo dalla ricezione alla dashboard
- [ ] **9.11** — Configurare il processo come servizio (systemd o supervisor) per riavvio automatico
- [ ] **9.12** — Configurare backup periodico del database e della cartella allegati
- [ ] **9.13** — Configurare logging su file con rotazione
- [ ] **9.14** — Monitorare il sistema per 24-48 ore in osservazione, verificare stabilità

---

### [FUTURO] Evoluzioni Pianificate

Le seguenti funzionalità sono previste per fasi successive:

- [ ] **F.1** — Integrazione OpenAI GPT-4o-mini per classificazione, summarization ed entity extraction avanzate (sostituzione/affiancamento pipeline locale)
- [ ] **F.2** — Implementare azione `forward` nel routing engine (inoltro email verso destinatari configurati)
- [ ] **F.3** — Rate limiting per API AI cloud (sezione 9.4 del documento)
- [ ] **F.4** — Circuit breaker per fallback automatico da LLM cloud a pipeline locale
- [ ] **F.5** — WebSocket per aggiornamenti real-time sulla dashboard
- [ ] **F.6** — Feedback loop: utente marca "non phishing" / "categoria errata" → aggiornamento modello ML

---

**Tempo totale stimato**: 14–18 settimane (3.5–4.5 mesi) con 1-2 sviluppatori.
**Totale step implementativi**: 170+ punti singoli, ciascuno verificabile indipendentemente.

---

*Documento generato come base di sviluppo. Ogni step (es: 0.1, 1.5, 2.13) è un'unità atomica: va implementato, verificato con test manuale o automatico, e approvato prima di procedere al successivo.*
