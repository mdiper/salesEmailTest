import re
from pathlib import Path

from src.utils.logger import logger

MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "classifier.pkl"

# Pattern regex per classificazione rule-based per ogni categoria.
# Ogni entry: (pattern_compilato, peso). Peso piu' alto = segnale piu' forte.
RULE_BASED_SIGNALS: dict[str, list[tuple[re.Pattern, float]]] = {
    "invoice": [
        (re.compile(r"fattura\s*(n\.?|numero|nr)", re.IGNORECASE), 1.0),
        (re.compile(r"invoice\s*(n\.?|number|no)", re.IGNORECASE), 1.0),
        (re.compile(r"importo\s*(totale|dovuto|da pagare)", re.IGNORECASE), 0.8),
        (re.compile(r"(scadenza|pagamento).{0,30}(entro|data)", re.IGNORECASE), 0.7),
        (re.compile(r"(bonifico|iban|coordinate bancarie)", re.IGNORECASE), 0.7),
        (re.compile(r"(total|amount|due|payment).{0,20}(eur|usd|\$|€)", re.IGNORECASE), 0.8),
        (re.compile(r"partita iva|p\.?\s?iva|vat", re.IGNORECASE), 0.5),
        (re.compile(r"(nota di credito|credit note)", re.IGNORECASE), 0.9),
    ],
    "marketing": [
        (re.compile(r"(offerta|promozione|sconto)\s*(speciale|esclusiv|limitata)", re.IGNORECASE), 1.0),
        (re.compile(r"(unsubscribe|disiscriviti|cancella iscrizione)", re.IGNORECASE), 0.9),
        (re.compile(r"(newsletter|mailing list)", re.IGNORECASE), 0.8),
        (re.compile(r"(special offer|limited time|exclusive deal)", re.IGNORECASE), 1.0),
        (re.compile(r"(approfitta|scopri|non perdere)", re.IGNORECASE), 0.5),
        (re.compile(r"(free trial|prova gratuita)", re.IGNORECASE), 0.7),
        (re.compile(r"(% off|% di sconto)", re.IGNORECASE), 0.8),
    ],
    "spam": [
        (re.compile(r"(vinto|won|winner|lottery|lotteria)", re.IGNORECASE), 1.0),
        (re.compile(r"(click here|clicca qui).{0,30}(now|subito|immediately)", re.IGNORECASE), 0.9),
        (re.compile(r"(million|milion).{0,20}(dollar|euro|usd|eur)", re.IGNORECASE), 1.0),
        (re.compile(r"(nigerian prince|eredita|inheritance)", re.IGNORECASE), 1.0),
        (re.compile(r"(make money|guadagna).{0,20}(fast|quick|facile|subito)", re.IGNORECASE), 0.9),
        (re.compile(r"(viagra|cialis|pills|farmaci online)", re.IGNORECASE), 1.0),
        (re.compile(r"(act now|agisci ora|urgente).{0,30}(expire|scade)", re.IGNORECASE), 0.7),
    ],
    "support": [
        (re.compile(r"(ticket|caso|case)\s*[#:]?\s*\d+", re.IGNORECASE), 1.0),
        (re.compile(r"(assistenza|support|help desk)", re.IGNORECASE), 0.7),
        (re.compile(r"(problema|issue|bug|errore|error)", re.IGNORECASE), 0.6),
        (re.compile(r"(risolto|resolved|fixed|chiuso|closed)", re.IGNORECASE), 0.6),
        (re.compile(r"(segnalazione|report|incident)", re.IGNORECASE), 0.5),
        (re.compile(r"(priorit[ay]|urgenz[ae]|severity)", re.IGNORECASE), 0.5),
    ],
    "legal": [
        (re.compile(r"(contratto|contract|agreement)", re.IGNORECASE), 0.8),
        (re.compile(r"(clausol[ae]|terms|conditions)", re.IGNORECASE), 0.7),
        (re.compile(r"(avvocato|lawyer|attorney|legale)", re.IGNORECASE), 0.8),
        (re.compile(r"(gdpr|privacy|trattamento dati)", re.IGNORECASE), 0.7),
        (re.compile(r"(normativa|regulation|compliance)", re.IGNORECASE), 0.6),
        (re.compile(r"(firma|signature|sottoscri)", re.IGNORECASE), 0.5),
        (re.compile(r"(tribunale|court|giudizio|cause)", re.IGNORECASE), 0.9),
    ],
    "hr": [
        (re.compile(r"(candidatura|application|resume|cv|curriculum)", re.IGNORECASE), 0.9),
        (re.compile(r"(colloquio|interview|selezione)", re.IGNORECASE), 0.8),
        (re.compile(r"(assunzione|hiring|posizione aperta|job opening)", re.IGNORECASE), 0.9),
        (re.compile(r"(ferie|vacanz[ae]|permesso|leave|holiday)", re.IGNORECASE), 0.7),
        (re.compile(r"(stipendio|salary|retribuzione|payroll)", re.IGNORECASE), 0.7),
        (re.compile(r"(formazione|training|onboarding)", re.IGNORECASE), 0.6),
        (re.compile(r"(dimission[ie]|resignation|licenziamento)", re.IGNORECASE), 0.9),
    ],
    "sales": [
        (re.compile(r"(preventivo|quotation|quote|offerta commerciale)", re.IGNORECASE), 1.0),
        (re.compile(r"(ordine|order)\s*(n\.?|numero|#)", re.IGNORECASE), 0.9),
        (re.compile(r"(listino|price list|catalogo|catalog)", re.IGNORECASE), 0.7),
        (re.compile(r"(spedizione|shipping|consegna|delivery)", re.IGNORECASE), 0.6),
        (re.compile(r"(trattativa|negotiation|deal)", re.IGNORECASE), 0.7),
        (re.compile(r"(cliente|customer|prospect)", re.IGNORECASE), 0.4),
        (re.compile(r"(campion[ei]|sample|prototip[oi])", re.IGNORECASE), 0.6),
        (re.compile(r"(disponibilit[ay]|availability|stock|magazzino)", re.IGNORECASE), 0.5),
    ],
    "personal": [
        (re.compile(r"(come stai|how are you|come va)", re.IGNORECASE), 0.7),
        (re.compile(r"(buon compleanno|happy birthday|auguri)", re.IGNORECASE), 0.9),
        (re.compile(r"(pranzo|cena|aperitivo|dinner|lunch)", re.IGNORECASE), 0.5),
        (re.compile(r"(vacanz[ae]|weekend|ferie).{0,30}(bel|divert|relax)", re.IGNORECASE), 0.6),
        (re.compile(r"(ci vediamo|see you|a presto)", re.IGNORECASE), 0.4),
        (re.compile(r"(grazie mille|thank you so much|sei gentilissim)", re.IGNORECASE), 0.4),
    ],
}


class ContentClassifier:
    """Classificatore ibrido: rule-based (alta confidence) + ML locale (fallback)."""

    def __init__(self):
        self._ml_model = None
        self._ml_vectorizer = None

    def classify(self, text: str) -> dict:
        """Classifica il testo: rule-based se confidence > 0.85, altrimenti ML fallback.

        Returns:
            dict con category, confidence, method, scores (per ogni categoria)
        """
        if not text or len(text.strip()) < 10:
            return {
                "category": "unknown",
                "confidence": 0.0,
                "method": "none",
                "scores": {},
            }

        # Step 1: classificazione rule-based
        rule_result = self._rule_based_classify(text)

        if rule_result["confidence"] >= 0.85:
            logger.info(
                "content_classified",
                category=rule_result["category"],
                confidence=rule_result["confidence"],
                method="rule_based",
            )
            return rule_result

        # Step 2: prova ML se disponibile
        ml_result = self._ml_classify(text)

        if ml_result and ml_result["confidence"] > rule_result["confidence"]:
            logger.info(
                "content_classified",
                category=ml_result["category"],
                confidence=ml_result["confidence"],
                method="ml",
            )
            return ml_result

        # Fallback: usa rule-based anche se confidence < 0.85
        logger.info(
            "content_classified",
            category=rule_result["category"],
            confidence=rule_result["confidence"],
            method="rule_based_fallback",
        )
        return rule_result

    def _rule_based_classify(self, text: str) -> dict:
        """Classificazione basata su pattern regex. Calcola score per ogni categoria."""
        scores: dict[str, float] = {}

        for category, signals in RULE_BASED_SIGNALS.items():
            category_score = 0.0
            matches_count = 0

            for pattern, weight in signals:
                found = pattern.findall(text)
                if found:
                    category_score += weight * len(found)
                    matches_count += len(found)

            scores[category] = round(category_score, 2)

        if not any(scores.values()):
            return {
                "category": "unknown",
                "confidence": 0.0,
                "method": "rule_based",
                "scores": scores,
            }

        # Categoria con score piu' alto
        best_category = max(scores, key=scores.get)
        best_score = scores[best_category]

        # Normalizza confidence: score / max_possible_per_categoria
        max_possible = sum(w for _, w in RULE_BASED_SIGNALS[best_category])
        confidence = min(1.0, round(best_score / max_possible, 2))

        return {
            "category": best_category,
            "confidence": confidence,
            "method": "rule_based",
            "scores": scores,
        }

    def _ml_classify(self, text: str) -> dict | None:
        """Classificazione ML con modello TF-IDF + SVM. Restituisce None se non disponibile."""
        model, vectorizer = self._load_ml_model()
        if model is None or vectorizer is None:
            return None

        try:
            text_vectorized = vectorizer.transform([text])
            prediction = model.predict(text_vectorized)[0]
            probabilities = model.predict_proba(text_vectorized)[0]
            confidence = round(float(max(probabilities)), 2)

            return {
                "category": prediction,
                "confidence": confidence,
                "method": "ml",
                "scores": {
                    cat: round(float(prob), 3)
                    for cat, prob in zip(model.classes_, probabilities)
                },
            }
        except Exception as e:
            logger.warning("ml_classify_failed", error=str(e))
            return None

    def _load_ml_model(self):
        """Carica il modello ML (cache dopo prima lettura)."""
        if self._ml_model is not None:
            return self._ml_model, self._ml_vectorizer

        if not MODEL_PATH.exists():
            return None, None

        try:
            import joblib
            data = joblib.load(MODEL_PATH)
            self._ml_model = data["model"]
            self._ml_vectorizer = data["vectorizer"]
            logger.info("ml_model_loaded", path=str(MODEL_PATH))
            return self._ml_model, self._ml_vectorizer
        except Exception as e:
            logger.warning("ml_model_load_failed", error=str(e))
            return None, None
