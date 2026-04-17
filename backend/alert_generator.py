"""
alert_generator.py - Human-readable alert generation for the AI Early Warning System.

Generates LLM-style explanatory text from structured risk/analysis data.
Uses dynamic template selection based on risk level and dominant signals.
No external LLM API required — entirely template-driven with variable injection.
"""

import random
from typing import Any
from datetime import datetime

# ---------------------------------------------------------------------------
# Alert templates indexed by risk level
# Each template accepts .format(**kwargs) substitution
# ---------------------------------------------------------------------------

CRITICAL_TEMPLATES = [
    (
        "🚨 CRITICAL: Extreme geopolitical volatility detected in {region}. "
        "Analysis of {total_articles} recent articles reveals a crisis-level risk score of {risk_score}/100 "
        "(confidence: {confidence_pct}%). Key indicators: {top_keywords_str}. "
        "Dominant entities: {top_entities_str}. "
        "Mean news sentiment has reached {sentiment_desc} ({mean_sentiment:.2f}), "
        "with {negative_pct}% of coverage classified as negative. "
        "Immediate international attention and de-escalation measures are urgently required."
    ),
    (
        "🚨 CRITICAL ALERT — {region}: Intelligence aggregation across {total_articles} sources "
        "indicates an extreme escalation trajectory. Risk index: {risk_score}/100 (confidence {confidence_pct}%). "
        "Prominent signals include {top_keywords_str}, involving {top_entities_str}. "
        "The overwhelmingly {sentiment_desc} media environment ({negative_pct}% negative coverage) "
        "suggests near-term risk of armed confrontation or major diplomatic breakdown."
    ),
]

HIGH_TEMPLATES = [
    (
        "⚠️ HIGH ALERT — {region}: Elevated conflict indicators detected across {total_articles} news sources. "
        "Risk score: {risk_score}/100 (confidence: {confidence_pct}%). "
        "Significant mentions of {top_keywords_str} involving {top_entities_str} "
        "signal heightened military and political tensions. "
        "Sentiment analysis indicates predominantly {sentiment_desc} coverage ({negative_pct}% negative). "
        "Continued monitoring and diplomatic engagement recommended."
    ),
    (
        "⚠️ Rising tension detected in {region} (Risk: {risk_score}/100, Confidence: {confidence_pct}%). "
        "Increased mentions of {top_keywords_str} by {top_entities_str} across {total_articles} recent reports. "
        "The {sentiment_desc} tone of regional coverage ({negative_pct}% negative articles) "
        "suggests deteriorating security conditions. Stakeholders should prepare contingency plans."
    ),
]

MODERATE_TEMPLATES = [
    (
        "⚡ MODERATE — {region}: Monitoring shows elevated but not critical activity. "
        "Risk score: {risk_score}/100 (confidence: {confidence_pct}%). "
        "Analysis of {total_articles} articles finds notable references to {top_keywords_str} "
        "involving {top_entities_str}. Sentiment is {sentiment_desc} ({mean_sentiment:.2f}). "
        "Situation requires ongoing attention but immediate crisis response is not indicated."
    ),
    (
        "⚡ Moderate tension indicators observed in {region}. "
        "Risk index: {risk_score}/100 (confidence {confidence_pct}%). "
        "{total_articles} recent articles highlight {top_keywords_str}. "
        "Key actors: {top_entities_str}. Coverage tone: {sentiment_desc}. "
        "Diplomatic monitoring advisable."
    ),
]

LOW_TEMPLATES = [
    (
        "✅ LOW — {region}: No significant conflict indicators detected at this time. "
        "Risk score: {risk_score}/100 (confidence: {confidence_pct}%). "
        "Analysis of {total_articles} articles finds limited military or conflict-related content. "
        "Regional sentiment is {sentiment_desc}. Routine monitoring continues."
    ),
    (
        "✅ Situation in {region} assessed as stable. "
        "Risk index: {risk_score}/100 (confidence: {confidence_pct}%). "
        "Sentiment is {sentiment_desc} across {total_articles} analyzed articles. "
        "No significant escalation signals detected."
    ),
]

TEMPLATES_BY_LEVEL = {
    "CRITICAL": CRITICAL_TEMPLATES,
    "HIGH":     HIGH_TEMPLATES,
    "MODERATE": MODERATE_TEMPLATES,
    "LOW":      LOW_TEMPLATES,
}

# ---------------------------------------------------------------------------
# Sentiment description mapper
# ---------------------------------------------------------------------------
def _describe_sentiment(polarity: float) -> str:
    if polarity <= -0.5:
        return "extremely negative"
    elif polarity <= -0.25:
        return "very negative"
    elif polarity <= -0.05:
        return "negative"
    elif polarity <= 0.05:
        return "neutral"
    elif polarity <= 0.25:
        return "slightly positive"
    else:
        return "positive"


# ---------------------------------------------------------------------------
# Main alert generator
# ---------------------------------------------------------------------------
def generate_alert(
    region: str,
    analysis: dict[str, Any],
    scoring: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate a structured alert object for a given region.

    Args:
        region:   Region name (e.g., "South China Sea")
        analysis: Output from analyzer.analyze_batch()
        scoring:  Output from risk_scorer.compute_risk_score()

    Returns:
        {
            "region": str,
            "risk_score": int,
            "risk_level": str,
            "confidence_pct": int,
            "summary": str,          ← human-readable paragraph
            "key_indicators": [...],  ← top keywords driving the alert
            "key_actors": [...],      ← top entities mentioned
            "timestamp": str,
        }
    """
    risk_score     = scoring.get("risk_score", 0)
    risk_level     = scoring.get("risk_level", "LOW")
    confidence_pct = scoring.get("confidence_pct", 0)
    mean_sentiment = analysis.get("mean_sentiment", 0.0)
    total_articles = analysis.get("total_articles", 0)
    negative_ratio = analysis.get("negative_article_ratio", 0.0)

    top_kw_list  = [kw for kw, _ in analysis.get("top_keywords", [])[:5]]
    top_ent_list = [ent for ent, _ in analysis.get("top_entities", [])[:4]]

    top_keywords_str = ", ".join(top_kw_list) if top_kw_list else "general geopolitical activity"
    top_entities_str = ", ".join(top_ent_list) if top_ent_list else "unnamed actors"
    sentiment_desc   = _describe_sentiment(mean_sentiment)
    negative_pct     = int(round(negative_ratio * 100))

    # Select a random template for variety across refreshes
    templates = TEMPLATES_BY_LEVEL.get(risk_level, LOW_TEMPLATES)
    template = random.choice(templates)  # noqa: S311

    summary = template.format(
        region          = region,
        risk_score      = risk_score,
        confidence_pct  = confidence_pct,
        total_articles  = total_articles,
        top_keywords_str= top_keywords_str,
        top_entities_str= top_entities_str,
        sentiment_desc  = sentiment_desc,
        mean_sentiment  = mean_sentiment,
        negative_pct    = negative_pct,
    )

    return {
        "region":          region,
        "risk_score":      risk_score,
        "risk_level":      risk_level,
        "confidence_pct":  confidence_pct,
        "summary":         summary,
        "key_indicators":  top_kw_list,
        "key_actors":      top_ent_list,
        "sentiment":       mean_sentiment,
        "negative_pct":    negative_pct,
        "total_articles":  total_articles,
        "timestamp":       datetime.utcnow().isoformat() + "Z",
    }


def rank_alerts(alerts: list[dict]) -> list[dict]:
    """Sort alerts by risk_score descending, then by confidence_pct."""
    return sorted(alerts, key=lambda a: (a["risk_score"], a["confidence_pct"]), reverse=True)
