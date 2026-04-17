"""
analyzer.py - NLP pipeline for the AI Early Conflict Warning System.

Pipeline steps:
  1. NER  - Extract countries and organizations using spaCy en_core_web_sm
  2. Sentiment - Polarity scoring per article using TextBlob
  3. Keyword extraction - Count military/conflict keywords from a curated list
  4. Aggregate statistics per batch of articles

spaCy model download (run once):
  python -m spacy download en_core_web_sm
"""

import re
import logging
from collections import Counter
from typing import Any

from textblob import TextBlob

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Military / conflict keyword lexicon (50+ terms)
# Grouped by severity tier for weighted scoring
# ---------------------------------------------------------------------------
MILITARY_KEYWORDS: dict[str, float] = {
    # Tier 3 — extreme (weight 3.0)
    "nuclear": 3.0,
    "nuclear weapon": 3.0,
    "nuclear strike": 3.0,
    "nuclear detonation": 3.0,
    "nuclear test": 3.0,
    "icbm": 3.0,
    "intercontinental ballistic missile": 3.0,
    "weapons of mass destruction": 3.0,
    "wmd": 3.0,
    "chemical weapon": 3.0,
    "biological weapon": 3.0,
    "nuclear enrichment": 2.5,
    "weapons-grade": 2.5,
    # Tier 2 — serious (weight 2.0)
    "missile": 2.0,
    "missile strike": 2.0,
    "ballistic missile": 2.0,
    "airstrike": 2.0,
    "airstrikes": 2.0,
    "bombardment": 2.0,
    "armed conflict": 2.0,
    "military strike": 2.0,
    "preemptive strike": 2.0,
    "military escalation": 2.0,
    "military invasion": 2.0,
    "military offensive": 2.0,
    "invasion": 2.0,
    "armed attack": 2.0,
    "warship": 2.0,
    "destroyer": 1.8,
    "carrier strike group": 1.8,
    "combat readiness": 1.8,
    "special alert": 1.8,
    "nuclear alert": 3.0,
    # Tier 1 — elevated (weight 1.0)
    "troop": 1.0,
    "troop movement": 1.0,
    "troop deployment": 1.0,
    "troops": 1.0,
    "military": 1.0,
    "military exercises": 1.0,
    "military buildup": 1.5,
    "tension": 1.0,
    "tensions": 1.0,
    "border tension": 1.5,
    "escalation": 1.5,
    "confrontation": 1.2,
    "provocation": 1.2,
    "sanctions": 0.8,
    "embargo": 0.8,
    "diplomatic crisis": 1.2,
    "blockade": 1.8,
    "maritime dispute": 1.2,
    "territorial dispute": 1.2,
    "incursion": 1.3,
    "mobilization": 1.5,
    "arms sale": 1.0,
    "artillery": 1.5,
    "drone": 1.0,
    "naval patrol": 1.2,
    "fighter jet": 1.2,
    "coast guard": 0.8,
    "navy": 0.8,
    "military readiness": 1.3,
    "ceasefire collapse": 1.8,
    "war": 2.0,
    "conflict": 1.0,
    "skirmish": 1.2,
    "casualties": 1.5,
    "displacement": 0.8,
    "refugee": 0.6,
    "proxy war": 1.8,
    "armed forces": 1.0,
    "defense budget": 0.7,
    "military spending": 0.7,
}

# Compile regex patterns for efficient multi-word matching
_KEYWORD_PATTERNS = {
    kw: re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
    for kw in MILITARY_KEYWORDS
}


# ---------------------------------------------------------------------------
# Attempt to load spaCy; fall back to regex-based NER if unavailable
# ---------------------------------------------------------------------------
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    _SPACY_AVAILABLE = True
    logger.info("spaCy en_core_web_sm loaded successfully.")
except (ImportError, OSError):
    _nlp = None
    _SPACY_AVAILABLE = False
    logger.warning(
        "spaCy not available or model not installed. "
        "Using regex-based NER fallback. "
        "Run: python -m spacy download en_core_web_sm"
    )

# Well-known country/region names for regex fallback
_KNOWN_ENTITIES = [
    "China", "Taiwan", "Philippines", "Vietnam", "Malaysia", "Russia",
    "Ukraine", "USA", "United States", "NATO", "Israel", "Iran", "Saudi Arabia",
    "Yemen", "Syria", "Iraq", "India", "Pakistan", "North Korea", "South Korea",
    "Japan", "Ethiopia", "Eritrea", "Sudan", "Somalia", "Germany", "Poland",
    "Belarus", "Turkey", "UAE", "Qatar", "Lebanon", "Hezbollah", "ASEAN",
]
_ENTITY_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(e) for e in _KNOWN_ENTITIES) + r')\b'
)


# ---------------------------------------------------------------------------
# Core NLP functions
# ---------------------------------------------------------------------------

def extract_entities(text: str) -> list[str]:
    """
    Extract geopolitical entities (GPE / ORG) from text.
    Uses spaCy NER if available, otherwise falls back to regex matching.
    """
    if _SPACY_AVAILABLE and _nlp:
        doc = _nlp(text[:1_000_000])  # spaCy has internal limits
        entities = [
            ent.text for ent in doc.ents
            if ent.label_ in ("GPE", "NORP", "ORG", "LOC")
        ]
        # De-duplicate preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for e in entities:
            if e not in seen:
                seen.add(e)
                unique.append(e)
        return unique
    else:
        # Regex fallback
        return list(dict.fromkeys(_ENTITY_PATTERN.findall(text)))


def analyze_sentiment(text: str) -> float:
    """
    Return mean sentiment polarity for the text.
    TextBlob polarity: -1.0 (very negative) to +1.0 (very positive).
    """
    if not text.strip():
        return 0.0
    blob = TextBlob(text)
    return round(blob.sentiment.polarity, 4)


def extract_keywords(text: str) -> dict[str, float]:
    """
    Count occurrences of military keywords in text.
    Returns {keyword: weighted_count} where count is multiplied by tier weight.
    """
    text_lower = text.lower()
    hits: dict[str, float] = {}
    for kw, weight in MILITARY_KEYWORDS.items():
        matches = _KEYWORD_PATTERNS[kw].findall(text_lower)
        if matches:
            hits[kw] = round(len(matches) * weight, 2)
    return hits


def analyze_article(article: dict) -> dict:
    """
    Run the full NLP pipeline on a single article.
    Returns an enriched dict with sentiment, entities, and keyword data.
    """
    combined_text = f"{article.get('title', '')} {article.get('body', '')}"

    sentiment = analyze_sentiment(combined_text)
    entities = extract_entities(combined_text)
    keywords = extract_keywords(combined_text)
    keyword_score = sum(keywords.values())

    return {
        **article,
        "sentiment": sentiment,
        "entities": entities,
        "keywords": keywords,
        "keyword_score": keyword_score,
    }


def analyze_batch(articles: list[dict]) -> dict[str, Any]:
    """
    Analyze a batch of articles and return aggregate statistics.

    Returns:
        {
            "articles": [enriched_article, ...],
            "mean_sentiment": float,
            "sentiment_timeline": [{date, sentiment}, ...],
            "top_keywords": [(kw, total_weight), ...],
            "top_entities": [(entity, count), ...],
            "total_articles": int,
            "negative_article_ratio": float,
        }
    """
    if not articles:
        return {
            "articles": [],
            "mean_sentiment": 0.0,
            "sentiment_timeline": [],
            "top_keywords": [],
            "top_entities": [],
            "total_articles": 0,
            "negative_article_ratio": 0.0,
        }

    enriched = [analyze_article(a) for a in articles]

    # --- Aggregate sentiment ---
    sentiments = [a["sentiment"] for a in enriched]
    mean_sentiment = round(sum(sentiments) / len(sentiments), 4)

    # --- Sentiment timeline (grouped by date) ---
    date_buckets: dict[str, list[float]] = {}
    for a in enriched:
        date = a.get("date", "unknown")
        date_buckets.setdefault(date, []).append(a["sentiment"])
    sentiment_timeline = [
        {"date": d, "sentiment": round(sum(v) / len(v), 4), "count": len(v)}
        for d, v in sorted(date_buckets.items())
    ]

    # --- Keyword aggregation ---
    keyword_totals: Counter = Counter()
    for a in enriched:
        for kw, score in a["keywords"].items():
            keyword_totals[kw] += score
    top_keywords = keyword_totals.most_common(15)

    # --- Entity aggregation ---
    entity_counter: Counter = Counter()
    for a in enriched:
        entity_counter.update(a["entities"])
    top_entities = entity_counter.most_common(10)

    # --- Negative ratio ---
    negative_count = sum(1 for s in sentiments if s < -0.05)
    negative_ratio = round(negative_count / max(len(sentiments), 1), 4)

    return {
        "articles": enriched,
        "mean_sentiment": mean_sentiment,
        "sentiment_timeline": sentiment_timeline,
        "top_keywords": top_keywords,
        "top_entities": top_entities,
        "total_articles": len(enriched),
        "negative_article_ratio": negative_ratio,
    }
