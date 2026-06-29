import math
import re
from collections import Counter

from src.utils.logger import logger

# Stopwords italiano + inglese (set compatto per TF-IDF)
STOPWORDS_IT = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "del",
    "dello", "della", "dei", "degli", "delle", "a", "al", "allo", "alla",
    "ai", "agli", "alle", "da", "dal", "dallo", "dalla", "dai", "dagli",
    "dalle", "in", "nel", "nello", "nella", "nei", "negli", "nelle", "con",
    "su", "sul", "sullo", "sulla", "sui", "sugli", "sulle", "per", "tra",
    "fra", "e", "o", "ma", "che", "chi", "cui", "non", "ne", "se", "si",
    "come", "dove", "quando", "quanto", "perche", "questo", "quello",
    "questa", "quella", "questi", "quelli", "queste", "quelle", "sono",
    "essere", "avere", "ha", "ho", "hai", "hanno", "stato", "stata",
    "stati", "state", "era", "erano", "molto", "anche", "piu", "suo",
    "sua", "suoi", "sue", "nostro", "nostra", "nostri", "nostre", "loro",
    "quale", "quali", "ogni", "tutto", "tutti", "tutta", "tutte", "altro",
    "altri", "altra", "altre", "stesso", "stessa", "stessi", "stesse",
    "ancora", "gia", "sempre", "mai", "poi", "prima", "dopo", "ora",
    "qui", "li", "ci", "vi", "me", "te", "noi", "voi", "mio", "mia",
    "miei", "mie", "tuo", "tua", "tuoi", "tue",
}

STOPWORDS_EN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must", "need", "dare",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "about", "up",
    "that", "this", "these", "those", "it", "its", "he", "she", "they",
    "them", "his", "her", "their", "we", "you", "i", "me", "my", "your",
    "our", "what", "which", "who", "whom",
}

STOPWORDS = STOPWORDS_IT | STOPWORDS_EN


class ContentSummarizer:
    """Riassume il contenuto email selezionando le frasi piu' rilevanti con TF-IDF."""

    def summarize(self, text: str, num_sentences: int = 4) -> str:
        """Genera un riassunto estrattivo selezionando le N frasi con TF-IDF score piu' alto.

        Args:
            text: testo preprocessato
            num_sentences: numero di frasi da includere nel riassunto

        Returns:
            Riassunto come stringa di frasi selezionate in ordine originale.
        """
        if not text or len(text.strip()) < 30:
            return text.strip() if text else ""

        sentences = self._split_sentences(text)

        if len(sentences) <= num_sentences:
            return text.strip()

        # Calcola TF-IDF per ogni frase
        scores = self._score_sentences(sentences)

        # Seleziona le top N frasi per score
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = sorted([idx for idx, _ in indexed_scores[:num_sentences]])

        # Ricomponi in ordine originale
        summary = " ".join(sentences[i] for i in top_indices)

        logger.debug(
            "text_summarized",
            input_sentences=len(sentences),
            output_sentences=num_sentences,
            input_len=len(text),
            output_len=len(summary),
        )

        return summary

    def _split_sentences(self, text: str) -> list[str]:
        """Divide il testo in frasi tramite regex."""
        # Split su punto, punto esclamativo, punto interrogativo seguiti da spazio/newline
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)

        sentences = []
        for s in raw_sentences:
            s = s.strip()
            if len(s) >= 10:
                sentences.append(s)

        return sentences

    def _get_stopwords(self) -> set[str]:
        """Restituisce il set combinato di stopwords IT + EN."""
        return STOPWORDS

    def _score_sentences(self, sentences: list[str]) -> list[float]:
        """Calcola lo score TF-IDF per ogni frase."""
        stopwords = self._get_stopwords()

        # Tokenizza ogni frase
        tokenized = []
        for sentence in sentences:
            words = re.findall(r"\b[a-zA-Zaeiou\u00e0-\u00ff]{2,}\b", sentence.lower())
            filtered = [w for w in words if w not in stopwords]
            tokenized.append(filtered)

        # Calcola IDF (Inverse Document Frequency)
        num_docs = len(sentences)
        df: Counter = Counter()
        for words in tokenized:
            unique_words = set(words)
            for word in unique_words:
                df[word] += 1

        idf = {}
        for word, count in df.items():
            idf[word] = math.log(num_docs / (1 + count)) + 1

        # Calcola TF-IDF score per frase
        scores = []
        for words in tokenized:
            if not words:
                scores.append(0.0)
                continue

            tf = Counter(words)
            sentence_score = 0.0
            for word, count in tf.items():
                tf_val = count / len(words)
                sentence_score += tf_val * idf.get(word, 0)

            # Normalizza per lunghezza frase (penalizza frasi troppo corte)
            length_factor = min(1.0, len(words) / 5)
            scores.append(sentence_score * length_factor)

        return scores
