"""
risk_scorer.py - Composite risk scoring for the AI Early Warning System v2.

Scoring pipeline:
  1. Sentiment anomaly (Z-score or raw mean if insufficient data)
  2. Keyword spike score (weighted keyword density)
  3. Article volume / mention frequency
  4. Combine into a 0–100 risk score with confidence %

Also computes 6-axis threat dimension radar data.
"""

import math
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import IsolationForest
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not available. Using Z-score only.")

# ---------------------------------------------------------------------------
# Weight constants
# ---------------------------------------------------------------------------
WEIGHT_SENTIMENT = 0.40
WEIGHT_KEYWORD   = 0.40
WEIGHT_VOLUME    = 0.20

BASELINE_MEAN_KEYWORD_SCORE = 5.0
BASELINE_STD_KEYWORD_SCORE  = 3.0
BASELINE_MEAN_SENTIMENT     = -0.10
BASELINE_STD_SENTIMENT      = 0.25

MIN_ARTICLES_FOR_CONCERN   = 3
HIGH_ARTICLE_COUNT_CEILING = 20

# ---------------------------------------------------------------------------
# Threat dimension keyword groups (for radar chart)
# ---------------------------------------------------------------------------
THREAT_DIMENSIONS = {
    "Military Activity": [
        "troop", "troops", "military", "airstrike", "bombardment", "warship",
        "artillery", "missile", "invasion", "armed forces", "navy", "fighter jet",
        "military exercises", "mobilization", "combat readiness",
    ],
    "Diplomatic Tension": [
        "sanction", "sanctions", "embargo", "diplomatic crisis", "protest",
        "condemnation", "ceasefire collapse", "tensions", "confrontation",
        "provocation", "expel", "recall ambassador", "Travel advisory",
    ],
    "Nuclear Risk": [
        "nuclear", "nuclear weapon", "nuclear strike", "icbm", "nuclear test",
        "weapons-grade", "nuclear enrichment", "nuclear detonation", "ballistic missile",
        "nuclear alert", "warhead",
    ],
    "Proxy Conflict": [
        "proxy war", "militia", "armed group", "insurgency", "terrorist",
        "Houthi", "Hezbollah", "backed forces", "non-state actor", "covert",
    ],
    "Economic Pressure": [
        "sanctions", "trade war", "embargo", "blockade", "economic pressure",
        "energy crisis", "oil", "supply chain", "export ban",
    ],
    "Humanitarian Crisis": [
        "civilian", "refugee", "displacement", "famine", "casualties",
        "humanitarian", "ceasefire", "aid blocked", "atrocity",
    ],
}


def _sigmoid(x: float, steepness: float = 3.0) -> float:
    return 1.0 / (1.0 + math.exp(-steepness * x))


def _z_score_anomaly(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.5 if value > mean else 0.0
    z = (value - mean) / std
    return round(_sigmoid(z), 4)


def _isolation_forest_scores(keyword_scores: list[float]) -> list[float]:
    if not _SKLEARN_AVAILABLE or len(keyword_scores) < 4:
        return [0.0] * len(keyword_scores)
    X = np.array(keyword_scores).reshape(-1, 1)
    try:
        clf = IsolationForest(contamination=0.2, random_state=42)
        clf.fit(X)
        raw = clf.decision_function(X)
        normalized = 1.0 - (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
        return [round(float(s), 4) for s in normalized]
    except Exception as exc:
        logger.warning("IsolationForest failed: %s", exc)
        return [0.0] * len(keyword_scores)


def compute_threat_dimensions(articles: list[dict]) -> dict[str, float]:
    """
    Compute per-axis threat dimension scores (0–100).
    Based on keyword presence weighted by tier.
    """
    if not articles:
        return {dim: 0.0 for dim in THREAT_DIMENSIONS}

    dim_scores: dict[str, float] = {dim: 0.0 for dim in THREAT_DIMENSIONS}

    for article in articles:
        text = (article.get("title", "") + " " + article.get("body", "")).lower()
        for dim, keywords in THREAT_DIMENSIONS.items():
            for kw in keywords:
                if kw.lower() in text:
                    dim_scores[dim] += 1.0

    # Normalize each dimension to 0–100
    max_possible = len(articles) * 3  # rough ceiling
    result = {}
    for dim, score in dim_scores.items():
        normalized = min(100.0, (score / max(max_possible, 1)) * 100 * 2.5)
        result[dim] = round(normalized, 1)

    return result


def compute_risk_score(analysis: dict[str, Any]) -> dict[str, Any]:
    """
    Compute composite risk score from NLP analysis output.
    """
    articles = analysis.get("articles", [])
    total = len(articles)

    if total == 0:
        return _empty_result()

    mean_sentiment    = analysis.get("mean_sentiment", 0.0)
    negative_ratio    = analysis.get("negative_article_ratio", 0.0)
    keyword_scores    = [a.get("keyword_score", 0.0) for a in articles]
    mean_kw_score     = np.mean(keyword_scores) if keyword_scores else 0.0

    # Sentiment score
    negativity = max(0.0, -mean_sentiment)
    weighted_negativity = negativity * 0.7 + negative_ratio * 0.3
    sentiment_anomaly = _z_score_anomaly(
        -mean_sentiment,
        -BASELINE_MEAN_SENTIMENT,
        BASELINE_STD_SENTIMENT,
    )
    sentiment_score = round(0.6 * sentiment_anomaly + 0.4 * weighted_negativity, 4)

    # Keyword score
    keyword_anomaly = _z_score_anomaly(
        mean_kw_score,
        BASELINE_MEAN_KEYWORD_SCORE,
        BASELINE_STD_KEYWORD_SCORE,
    )
    if_scores = _isolation_forest_scores(keyword_scores)
    mean_if_score = float(np.mean(if_scores)) if if_scores else 0.0
    keyword_score = round(0.7 * keyword_anomaly + 0.3 * mean_if_score, 4)

    per_article_z = [
        _z_score_anomaly(ks, BASELINE_MEAN_KEYWORD_SCORE, BASELINE_STD_KEYWORD_SCORE)
        for ks in keyword_scores
    ]
    anomalous_indices = [
        i for i, (z, ifs) in enumerate(zip(per_article_z, if_scores))
        if z > 0.7 or ifs > 0.7
    ]

    # Volume score
    volume_score = round(
        min(1.0, max(0.0, (total - MIN_ARTICLES_FOR_CONCERN) / HIGH_ARTICLE_COUNT_CEILING)),
        4,
    )

    # Composite
    raw_composite = (
        WEIGHT_SENTIMENT * sentiment_score
        + WEIGHT_KEYWORD   * keyword_score
        + WEIGHT_VOLUME    * volume_score
    )
    risk_score = int(round(min(100, max(0, raw_composite * 100))))

    # Confidence
    data_confidence   = min(1.0, total / 10)
    score_consistency = 1.0 - abs(sentiment_score - keyword_score) / 2
    confidence = round(0.6 * data_confidence + 0.4 * score_consistency, 4)

    # Level
    if risk_score >= 75:
        risk_level = "CRITICAL"
    elif risk_score >= 50:
        risk_level = "HIGH"
    elif risk_score >= 25:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    # Threat dimensions
    threat_dims = compute_threat_dimensions(articles)

    # Trend delta (compare first half vs second half of articles)
    mid = max(1, total // 2)
    early_kw = float(np.mean(keyword_scores[:mid])) if keyword_scores[:mid] else 0.0
    late_kw  = float(np.mean(keyword_scores[mid:])) if keyword_scores[mid:] else 0.0
    trend_delta = round(late_kw - early_kw, 2)  # positive = escalating

    return {
        "risk_score":       risk_score,
        "confidence":       confidence,
        "confidence_pct":   int(round(confidence * 100)),
        "sentiment_anomaly": sentiment_anomaly,
        "keyword_anomaly":  keyword_anomaly,
        "volume_score":     volume_score,
        "anomalous_article_indices": anomalous_indices,
        "risk_level":       risk_level,
        "component_scores": {
            "sentiment": round(sentiment_score * 100, 1),
            "keyword":   round(keyword_score * 100, 1),
            "volume":    round(volume_score * 100, 1),
        },
        "threat_dimensions": threat_dims,
        "trend_delta":       trend_delta,
        "trend_direction":   "escalating" if trend_delta > 0.5 else "de-escalating" if trend_delta < -0.5 else "stable",
        "mean_keyword_score": round(float(mean_kw_score), 2),
        "mean_sentiment":    mean_sentiment,
        "isolation_forest_used": _SKLEARN_AVAILABLE and len(keyword_scores) >= 4,
    }


def _empty_result() -> dict[str, Any]:
    return {
        "risk_score":       0,
        "confidence":       0.0,
        "confidence_pct":   0,
        "sentiment_anomaly": 0.0,
        "keyword_anomaly":  0.0,
        "volume_score":     0.0,
        "anomalous_article_indices": [],
        "risk_level":       "LOW",
        "component_scores": {"sentiment": 0, "keyword": 0, "volume": 0},
        "threat_dimensions": {dim: 0.0 for dim in THREAT_DIMENSIONS},
        "trend_delta":       0.0,
        "trend_direction":   "stable",
        "mean_keyword_score": 0.0,
        "mean_sentiment":    0.0,
        "isolation_forest_used": False,
    }
