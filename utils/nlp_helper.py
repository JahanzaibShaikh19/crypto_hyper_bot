"""
utils/nlp_helper.py — NLP sentiment analysis using TextBlob.

Scores any text -1.0 (negative) to +1.0 (positive).
Also handles keyword detection for emergency overrides.
"""
from textblob import TextBlob
from config import BEARISH_KEYWORDS, BULLISH_KEYWORDS
from loguru import logger
from typing import Optional


def sentiment_score(text: str) -> float:
    """
    Returns polarity score: -1.0 to +1.0.
    TextBlob uses a trained sentiment lexicon.
    """
    if not text or not text.strip():
        return 0.0
    try:
        blob = TextBlob(text.lower())
        return blob.sentiment.polarity  # -1 to 1
    except Exception as e:
        logger.warning(f"Sentiment error: {e}")
        return 0.0


def detect_bearish_keywords(text: str) -> list[str]:
    """Returns list of bearish keywords found in text."""
    text_lower = text.lower()
    return [kw for kw in BEARISH_KEYWORDS if kw in text_lower]


def detect_bullish_keywords(text: str) -> list[str]:
    """Returns list of bullish keywords found in text."""
    text_lower = text.lower()
    return [kw for kw in BULLISH_KEYWORDS if kw in text_lower]


def keyword_score(text: str) -> float:
    """
    Returns a keyword-based score: +1.5 if bullish, -2 if bearish.
    Bearish overrides are stronger (risk management principle).
    """
    bearish = detect_bearish_keywords(text)
    bullish = detect_bullish_keywords(text)

    if bearish:
        logger.warning(f"Bearish keywords detected: {bearish}")
        return -2.0
    if bullish:
        logger.info(f"Bullish keywords detected: {bullish}")
        return 1.5
    return 0.0


def combined_score(text: str) -> dict:
    """
    Returns both NLP polarity and keyword score with metadata.
    """
    polarity = sentiment_score(text)
    kw_score  = keyword_score(text)
    bearish_kw = detect_bearish_keywords(text)
    bullish_kw = detect_bullish_keywords(text)

    # If keyword override is present, weight it 70% vs NLP 30%
    if bearish_kw or bullish_kw:
        final = (kw_score * 0.7) + (polarity * 0.3)
    else:
        final = polarity

    return {
        "polarity": polarity,
        "keyword_score": kw_score,
        "final": final,
        "bearish_keywords": bearish_kw,
        "bullish_keywords": bullish_kw,
        "has_emergency": bool(bearish_kw),
    }


def batch_sentiment(texts: list[str]) -> float:
    """Average sentiment across multiple texts."""
    if not texts:
        return 0.0
    scores = [sentiment_score(t) for t in texts]
    return sum(scores) / len(scores)
