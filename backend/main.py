"""
main.py - FastAPI application for the AI Early Conflict Warning System v2.

Endpoints:
  GET /                             → Health check + API info
  GET /regions                      → List all available regions
  GET /analyze?region=...           → Full analysis pipeline for a region
  GET /alerts?limit=N               → Top alerts across all regions
  GET /data?region=...              → Raw article data + statistics
  GET /summary                      → Global aggregate statistics
  GET /compare?regions=A,B,C        → Side-by-side multi-region comparison
  GET /trend?region=...             → 14-day synthesized risk trend
  GET /hotspots                     → Regions with highest escalation delta
  DELETE /cache                     → Clear the analysis cache

Run with:
  uvicorn main:app --reload --port 8000
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from data_ingestion import fetch_articles, get_available_regions
from analyzer import analyze_batch
from risk_scorer import compute_risk_score
from alert_generator import generate_alert, rank_alerts
from cache import cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Early Conflict Warning System v2",
    description=(
        "Real-time geopolitical tension detection using NLP, "
        "anomaly detection, and multi-source news analysis."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────── Pipeline helper ────────────────────────────────

def _run_pipeline(region: str) -> dict:
    cache_key = f"analysis:{region.lower()}"
    cached = cache.get(cache_key)
    if cached:
        logger.info("Cache HIT for region '%s'", region)
        return cached

    logger.info("Cache MISS — running pipeline for region '%s'", region)

    articles = fetch_articles(region)
    if not articles:
        raise HTTPException(
            status_code=404,
            detail=f"No articles found for region '{region}'.",
        )

    analysis = analyze_batch(articles)
    scoring  = compute_risk_score(analysis)
    alert    = generate_alert(region, analysis, scoring)

    result = {
        "region":   region,
        "analysis": analysis,
        "scoring":  scoring,
        "alert":    alert,
    }
    cache.set(cache_key, result)
    return result


def _trimmed_articles(analysis: dict, limit: int = 10) -> list[dict]:
    return [
        {
            "id":            a.get("id"),
            "title":         a.get("title"),
            "date":          a.get("date"),
            "source":        a.get("source"),
            "region":        a.get("region"),
            "sentiment":     a.get("sentiment"),
            "keyword_score": a.get("keyword_score"),
            "entities":      a.get("entities", [])[:4],
            "keywords":      list(a.get("keywords", {}).keys())[:5],
        }
        for a in analysis.get("articles", [])[:limit]
    ]


# ─────────────────────────────── Routes ─────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "status":     "online",
        "service":    "AI Early Conflict Warning System",
        "version":    "2.0.0",
        "endpoints":  {
            "/regions":  "List all regions",
            "/analyze":  "Full pipeline for a region",
            "/alerts":   "Global ranked alerts",
            "/summary":  "Global aggregate statistics",
            "/compare":  "Multi-region comparison",
            "/trend":    "14-day risk trend for a region",
            "/hotspots": "Top escalating regions",
            "/data":     "Raw article data",
            "/docs":     "Interactive API docs",
        },
        "cache_stats": cache.stats(),
        "timestamp":   datetime.utcnow().isoformat() + "Z",
    }


@app.get("/regions", tags=["Data"])
async def list_regions():
    regions = get_available_regions()
    return {"regions": regions, "count": len(regions)}


@app.get("/analyze", tags=["Analysis"])
async def analyze_region(
    region: str = Query(..., description="Region to analyze"),
):
    pipeline = _run_pipeline(region)
    analysis = pipeline["analysis"]
    scoring  = pipeline["scoring"]
    alert    = pipeline["alert"]

    return {
        "region":              region,
        "risk_score":          scoring["risk_score"],
        "risk_level":          scoring["risk_level"],
        "confidence_pct":      scoring["confidence_pct"],
        "trend_direction":     scoring["trend_direction"],
        "trend_delta":         scoring["trend_delta"],
        "alert":               alert,
        "component_scores":    scoring["component_scores"],
        "threat_dimensions":   scoring["threat_dimensions"],
        "mean_sentiment":      analysis["mean_sentiment"],
        "negative_pct":        int(analysis["negative_article_ratio"] * 100),
        "total_articles":      analysis["total_articles"],
        "top_keywords":        analysis["top_keywords"],
        "top_entities":        analysis["top_entities"],
        "sentiment_timeline":  analysis["sentiment_timeline"],
        "articles":            _trimmed_articles(analysis, 10),
        "isolation_forest":    scoring["isolation_forest_used"],
        "cached":              cache.get(f"analysis:{region.lower()}") is not None,
        "analyzed_at":         datetime.utcnow().isoformat() + "Z",
    }


@app.get("/alerts", tags=["Alerts"])
async def get_all_alerts(
    limit: int = Query(default=10, ge=1, le=50),
    min_level: str = Query(default="LOW", description="Minimum risk level: LOW, MODERATE, HIGH, CRITICAL"),
):
    level_order = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "CRITICAL": 3}
    min_num = level_order.get(min_level.upper(), 0)

    regions = get_available_regions()
    alerts: list[dict] = []

    for region in regions:
        try:
            pipeline = _run_pipeline(region)
            a = pipeline["alert"]
            a["trend_direction"] = pipeline["scoring"]["trend_direction"]
            a["trend_delta"]     = pipeline["scoring"]["trend_delta"]
            alerts.append(a)
        except HTTPException:
            pass
        except Exception as exc:
            logger.error("Pipeline error for '%s': %s", region, exc)

    ranked = rank_alerts(alerts)
    filtered = [a for a in ranked if level_order.get(a["risk_level"], 0) >= min_num][:limit]

    return {
        "alerts":          filtered,
        "total_regions":   len(regions),
        "high_risk_count": sum(1 for a in ranked if a["risk_level"] in ("HIGH", "CRITICAL")),
        "critical_count":  sum(1 for a in ranked if a["risk_level"] == "CRITICAL"),
        "moderate_count":  sum(1 for a in ranked if a["risk_level"] == "MODERATE"),
        "low_count":       sum(1 for a in ranked if a["risk_level"] == "LOW"),
        "generated_at":    datetime.utcnow().isoformat() + "Z",
    }


@app.get("/summary", tags=["Analysis"])
async def get_global_summary():
    """
    Run pipeline for all regions and return global aggregate statistics.
    Used for the Overview page counters.
    """
    regions = get_available_regions()
    all_data: list[dict] = []

    for region in regions:
        try:
            pipeline = _run_pipeline(region)
            all_data.append({
                "region":          region,
                "risk_score":      pipeline["scoring"]["risk_score"],
                "risk_level":      pipeline["scoring"]["risk_level"],
                "trend_direction": pipeline["scoring"]["trend_direction"],
                "confidence_pct":  pipeline["scoring"]["confidence_pct"],
                "total_articles":  pipeline["analysis"]["total_articles"],
                "mean_sentiment":  pipeline["analysis"]["mean_sentiment"],
            })
        except Exception as exc:
            logger.error("Summary error for '%s': %s", region, exc)

    if not all_data:
        raise HTTPException(status_code=503, detail="No regions could be analyzed.")

    scores = [d["risk_score"] for d in all_data]
    worst  = max(all_data, key=lambda x: x["risk_score"])

    escalating = [d["region"] for d in all_data if d["trend_direction"] == "escalating"]
    total_articles = sum(d["total_articles"] for d in all_data)

    return {
        "regions":           all_data,
        "global_avg_risk":   round(sum(scores) / len(scores), 1),
        "max_risk_score":    max(scores),
        "min_risk_score":    min(scores),
        "worst_region":      worst,
        "critical_count":    sum(1 for d in all_data if d["risk_level"] == "CRITICAL"),
        "high_count":        sum(1 for d in all_data if d["risk_level"] == "HIGH"),
        "moderate_count":    sum(1 for d in all_data if d["risk_level"] == "MODERATE"),
        "low_count":         sum(1 for d in all_data if d["risk_level"] == "LOW"),
        "escalating_regions": escalating,
        "total_articles":    total_articles,
        "generated_at":      datetime.utcnow().isoformat() + "Z",
    }


@app.get("/compare", tags=["Analysis"])
async def compare_regions(
    regions: str = Query(..., description="Comma-separated regions e.g. 'Taiwan,Russia-Ukraine'"),
):
    """
    Run pipeline for multiple regions and return side-by-side data.
    """
    region_list = [r.strip() for r in regions.split(",") if r.strip()]
    if len(region_list) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 comma-separated regions.")
    if len(region_list) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 regions for comparison.")

    results = []
    for region in region_list:
        try:
            pipeline = _run_pipeline(region)
            analysis = pipeline["analysis"]
            scoring  = pipeline["scoring"]
            results.append({
                "region":            region,
                "risk_score":        scoring["risk_score"],
                "risk_level":        scoring["risk_level"],
                "confidence_pct":    scoring["confidence_pct"],
                "trend_direction":   scoring["trend_direction"],
                "trend_delta":       scoring["trend_delta"],
                "mean_sentiment":    analysis["mean_sentiment"],
                "negative_pct":      int(analysis["negative_article_ratio"] * 100),
                "total_articles":    analysis["total_articles"],
                "top_keywords":      analysis["top_keywords"][:8],
                "top_entities":      analysis["top_entities"][:5],
                "component_scores":  scoring["component_scores"],
                "threat_dimensions": scoring["threat_dimensions"],
                "alert_summary":     pipeline["alert"]["summary"],
                "sentiment_timeline": analysis["sentiment_timeline"],
            })
        except HTTPException as exc:
            results.append({"region": region, "error": exc.detail})
        except Exception as exc:
            results.append({"region": region, "error": str(exc)})

    return {
        "regions":      region_list,
        "results":      results,
        "compared_at":  datetime.utcnow().isoformat() + "Z",
    }


@app.get("/trend", tags=["Analysis"])
async def get_trend(region: str = Query(..., description="Region to get trend data for")):
    """
    Return a synthesized 14-day risk score trend for a region.
    Built from per-day article sentiment/keyword distribution in the dataset.
    """
    pipeline = _run_pipeline(region)
    analysis = pipeline["analysis"]
    scoring  = pipeline["scoring"]

    # Build day-by-day data from sentiment_timeline
    timeline = analysis.get("sentiment_timeline", [])

    # Generate synthetic daily risk scores from the sentiment data
    # We scale from sentiment → risk approximation
    trend_data = []
    base_risk = scoring["risk_score"]

    for point in timeline:
        sent   = point["sentiment"]
        count  = point.get("count", 1)
        # Convert sentiment to approximate daily risk
        negativity = max(0, -sent)
        daily_risk = min(100, int(base_risk * 0.6 + negativity * 40 + min(count, 5) * 3))
        trend_data.append({
            "date":  point["date"],
            "risk":  daily_risk,
            "sentiment": sent,
            "articles": count,
        })

    # If fewer than 5 days, pad with slightly varied historical values
    if len(trend_data) < 5:
        today = datetime.utcnow()
        existing_dates = {d["date"] for d in trend_data}
        for i in range(14, -1, -1):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            if d not in existing_dates:
                jitter = (-i * 1.5 + (i % 3) * 2)
                synthetic_risk = max(0, min(100, int(base_risk + jitter)))
                trend_data.append({
                    "date":      d,
                    "risk":      synthetic_risk,
                    "sentiment": round(-synthetic_risk / 100 * 0.5, 3),
                    "articles":  0,
                })

    trend_data.sort(key=lambda x: x["date"])
    trend_data = trend_data[-14:]  # last 14 days

    return {
        "region":          region,
        "trend":           trend_data,
        "current_risk":    base_risk,
        "risk_level":      scoring["risk_level"],
        "trend_direction": scoring["trend_direction"],
        "generated_at":    datetime.utcnow().isoformat() + "Z",
    }


@app.get("/hotspots", tags=["Analysis"])
async def get_hotspots(limit: int = Query(default=5, ge=1, le=20)):
    """
    Return regions with the highest positive trend delta (escalating).
    Useful for 'watch-this-region' highlights.
    """
    regions = get_available_regions()
    hotspots = []

    for region in regions:
        try:
            pipeline = _run_pipeline(region)
            s = pipeline["scoring"]
            hotspots.append({
                "region":          region,
                "risk_score":      s["risk_score"],
                "risk_level":      s["risk_level"],
                "trend_delta":     s["trend_delta"],
                "trend_direction": s["trend_direction"],
                "confidence_pct":  s["confidence_pct"],
            })
        except Exception:
            pass

    # Sort by trend_delta descending (most escalating first)
    hotspots.sort(key=lambda x: x["trend_delta"], reverse=True)
    return {
        "hotspots":    hotspots[:limit],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/data", tags=["Data"])
async def get_raw_data(
    region: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
):
    pipeline = _run_pipeline(region)
    analysis = pipeline["analysis"]
    return {
        "region":             region,
        "articles":           _trimmed_articles(analysis, limit),
        "total_articles":     analysis["total_articles"],
        "mean_sentiment":     analysis["mean_sentiment"],
        "negative_ratio":     analysis["negative_article_ratio"],
        "top_keywords":       analysis["top_keywords"],
        "sentiment_timeline": analysis["sentiment_timeline"],
    }


@app.delete("/cache", tags=["Admin"])
async def clear_cache():
    cache.clear()
    return {"status": "cache cleared"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
