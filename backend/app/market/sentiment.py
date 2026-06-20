"""FinBERT sentiment analysis for stock headlines.

Uses the ProsusAI/finbert model from HuggingFace to classify financial
news headlines as positive, negative, or neutral.  Designed to run on
CPU — inference on short headlines takes <100 ms each.

Usage::

    from app.market.sentiment import FinbertSentimentAnalyzer

    analyzer = FinbertSentimentAnalyzer()
    results = analyzer.analyze_headlines(["Apple beats earnings expectations"])
    print(results)
    # [{'headline': '...', 'sentiment': 'positive', 'score': 0.98, ...}]

    summary = analyzer.analyze_symbol("AAPL")
    print(summary)
    # {'symbol': 'AAPL', 'sentiment': 'positive', 'score': 0.85, ...}
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FinbertSentimentAnalyzer:
    """FinBERT-based sentiment analyzer with built-in caching.

    The model (~420 MB) is downloaded from HuggingFace on first use and
    cached locally by the ``transformers`` library (typically under
    ``~/.cache/huggingface/``).  Subsequent loads are fast.

    Sentiment scores are also cached in-memory keyed by a hash of the
    headline text, so repeated calls with the same headlines do not
    re-run inference.
    """

    MODEL_NAME = "ProsusAI/finbert"
    LABEL_MAP = {
        "positive": "positive",
        "negative": "negative",
        "neutral": "neutral",
    }

    def __init__(self, model_name: str | None = None, device: str = "cpu"):
        """Load the FinBERT model and tokenizer.

        Parameters
        ----------
        model_name : str
            HuggingFace model identifier.  Defaults to ``ProsusAI/finbert``.
        device : str
            ``"cpu"`` or ``"cuda"``.  CPU is fine for headline batch inference.
        """
        self.model_name = model_name or self.MODEL_NAME
        self.device = device
        self._cache: Dict[str, dict] = {}
        self._tokenizer = None
        self._model = None
        self._loaded = False

    # ------------------------------------------------------------------
    # Lazy loading — only import torch/transformers when actually needed
    # ------------------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        logger.info("Loading FinBERT model %s on %s ...", self.model_name, self.device)
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self._model.to(self.device)
        self._model.eval()
        self._loaded = True
        logger.info("FinBERT model loaded successfully.")

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _hash_headline(headline: str) -> str:
        return hashlib.sha256(headline.strip().lower().encode()).hexdigest()

    # ------------------------------------------------------------------
    # Core inference
    # ------------------------------------------------------------------
    def analyze_headlines(self, headlines: List[str]) -> List[dict]:
        """Analyse a batch of headlines and return per-headline sentiment.

        Returns a list of dicts in the same order as *headlines*::

            {
                "headline": str,
                "sentiment": "positive" | "negative" | "neutral",
                "score": float,            # probability of predicted label
                "positive": float,          # probability positive
                "negative": float,          # probability negative
                "neutral": float,           # probability neutral
            }
        """
        if not headlines:
            return []

        self._ensure_loaded()

        import torch

        results: List[dict] = []
        uncached_indices: List[int] = []
        uncached_texts: List[str] = []

        # Separate cached vs uncached
        for i, h in enumerate(headlines):
            key = self._hash_headline(h)
            if key in self._cache:
                results.append(self._cache[key].copy())
            else:
                uncached_indices.append(i)
                uncached_texts.append(h)

        # Run inference on uncached headlines
        if uncached_texts:
            logger.debug("Running FinBERT inference on %d uncached headlines", len(uncached_texts))
            inputs = self._tokenizer(
                uncached_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                outputs = self._model(**inputs)

            # FinBERT label order: [positive, negative, neutral]
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1).tolist()

            for idx, headline, prob in zip(uncached_indices, uncached_texts, probs):
                # ProsusAI/finbert labels: 0=positive, 1=negative, 2=neutral
                # But the actual label order can vary; use model.config
                label_scores = {
                    "positive": prob[0],
                    "negative": prob[1],
                    "neutral": prob[2],
                }
                # Determine predicted label from id2label
                if hasattr(self._model.config, "id2label"):
                    predicted_id = max(range(len(prob)), key=lambda i: prob[i])
                    predicted_label = self._model.config.id2label[predicted_id].lower()
                    sentiment = self.LABEL_MAP.get(predicted_label, predicted_label)
                else:
                    # Fallback: assume standard FinBERT ordering
                    predicted_id = max(range(len(prob)), key=lambda i: prob[i])
                    sentiment = ["positive", "negative", "neutral"][predicted_id]

                entry = {
                    "headline": headline,
                    "sentiment": sentiment,
                    "score": label_scores[sentiment],
                    "positive": label_scores["positive"],
                    "negative": label_scores["negative"],
                    "neutral": label_scores["neutral"],
                }
                self._cache[self._hash_headline(headline)] = entry.copy()
                results.insert(idx, entry)

        # Re-sort results to match input order
        # (we inserted cached ones at their position and uncached at theirs)
        # Actually we built results in order — let's just sort by original index
        # Simpler: rebuild in order
        ordered: List[Optional[dict]] = [None] * len(headlines)
        # Rebuild from cache
        for i, h in enumerate(headlines):
            key = self._hash_headline(h)
            ordered[i] = self._cache[key].copy()

        return [r for r in ordered if r is not None]

    def analyze_symbol(
        self,
        symbol: str,
        headlines: Optional[List[str]] = None,
        fetcher: Optional["NewsFetcher"] = None,
        limit: int = 10,
    ) -> dict:
        """Analyse overall sentiment for a stock symbol.

        If *headlines* is provided, analyse those.  Otherwise, if *fetcher*
        is provided, fetch headlines for the symbol first.

        Returns::

            {
                "symbol": str,
                "sentiment": "positive" | "negative" | "neutral",
                "score": float,               # mean probability of dominant label
                "headlines_analyzed": int,
                "breakdown": {                 # count of each label
                    "positive": int,
                    "negative": int,
                    "neutral": int,
                },
                "headlines": [ ... ],          # per-headline results
            }
        """
        if headlines is None:
            if fetcher is None:
                raise ValueError("Either headlines or fetcher must be provided")
            headlines = fetcher.fetch_headlines(symbol, limit=limit)

        if not headlines:
            return {
                "symbol": symbol.upper(),
                "sentiment": "neutral",
                "score": 0.0,
                "headlines_analyzed": 0,
                "breakdown": {"positive": 0, "negative": 0, "neutral": 0},
                "headlines": [],
            }

        per_headline = self.analyze_headlines(headlines)

        counts = {"positive": 0, "negative": 0, "neutral": 0}
        scores = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
        for r in per_headline:
            counts[r["sentiment"]] += 1
            scores[r["sentiment"]] += r["score"]

        # Determine overall sentiment by weighted vote
        # Weight by score so high-confidence headlines matter more
        weighted = {k: scores[k] for k in counts}
        overall = max(weighted, key=weighted.get)
        overall_score = scores[overall] / counts[overall] if counts[overall] > 0 else 0.0

        return {
            "symbol": symbol.upper(),
            "sentiment": overall,
            "score": round(overall_score, 4),
            "headlines_analyzed": len(per_headline),
            "breakdown": counts,
            "headlines": per_headline,
        }