from src.content.preprocessor import EmailPreprocessor
from src.content.classifier import ContentClassifier
from src.content.summarizer import ContentSummarizer
from src.content.entity_extractor import EntityExtractor
from src.db.content_repository import ContentRepository
from src.utils.logger import logger


class ContentAnalyzer:
    """Orchestratore pipeline di analisi contenuto:
    Preprocessor -> Classifier -> Summarizer -> EntityExtractor -> DB
    """

    def __init__(self):
        self.preprocessor = EmailPreprocessor()
        self.classifier = ContentClassifier()
        self.summarizer = ContentSummarizer()
        self.entity_extractor = EntityExtractor()
        self.repository = ContentRepository()

    def analyze(self, email_data: dict, save_to_db: bool = True) -> dict:
        """Esegue la pipeline completa di content analysis.

        Args:
            email_data: dict con 'body_html', 'body_text', 'email_id' (opzionale)

        Returns:
            dict con category, confidence, summary, entities, clean_text
        """
        logger.info("content_analysis_start", email_id=email_data.get("email_id"))

        # Step 1: Preprocessing
        clean_text = self.preprocessor.process(email_data)

        # Step 2: Classification
        classification = self.classifier.classify(clean_text)

        # Step 3: Summarization
        summary = self.summarizer.summarize(clean_text)

        # Step 4: Entity Extraction
        entities = self.entity_extractor.extract(clean_text)

        result = {
            "category": classification["category"],
            "category_confidence": classification["confidence"],
            "classification_method": classification["method"],
            "summary": summary,
            "sentiment": None,  # Predisposto per fase futura
            "urgency": None,    # Predisposto per fase futura
            "entities": entities,
            "clean_text": clean_text,
            "scores": classification.get("scores", {}),
        }

        # Salvataggio DB
        email_id = email_data.get("email_id")
        if save_to_db and email_id:
            try:
                self.repository.save_result(email_id, result)
            except Exception as e:
                logger.error("content_analysis_save_failed", email_id=email_id, error=str(e))

        logger.info(
            "content_analysis_complete",
            email_id=email_id,
            category=result["category"],
            confidence=result["category_confidence"],
            summary_len=len(summary),
            entities_count=sum(len(v) for v in entities.values() if isinstance(v, list)),
        )

        return result
