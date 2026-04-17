"""
data_ingestion.py - Fetches live news articles for a given region using Google News RSS.

Since NewsAPI is highly restricted, this script uses `feedparser` to query
Google News directly. This provides a completely free, unrestricted, and 
real-time OSINT data feed.

Fallback: If RSS fails, it drops down to the local mock dataset.
"""

import json
import logging
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

MOCK_DATA_PATH = Path(__file__).parent.parent / "data" / "mock_news.json"

# We use precise queries to pull geopolitical / military news from Google News
REGION_QUERIES: dict[str, str] = {
    "South China Sea": '"South China Sea" AND (military OR tension OR navy)',
    "Taiwan": 'Taiwan AND (military OR China OR PLA OR "Taiwan Strait")',
    "Russia-Ukraine": '(Russia OR Russian) AND (Ukraine OR Ukrainian) AND (war OR military OR troops)',
    "Middle East": '"Middle East" AND (Iran OR Israel OR strike OR military)',
    "India-Pakistan": '(India OR Indian) AND (Pakistan OR Pakistani) AND (border OR military OR Kashmir)',
    "Korean Peninsula": '("North Korea" OR "South Korea") AND (missile OR military OR nuclear OR Kim)',
    "Horn of Africa": '(Ethiopia OR Sudan OR Somalia OR Red Sea) AND (conflict OR rebels OR military)',
}


def _clean_html(raw_html: str) -> str:
    """Strip HTML tags from RSS item descriptions to get clean text."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _fetch_rss(region: str, limit: int = 30) -> list[dict]:
    """
    Fetch live news articles via Google News RSS.
    """
    query = REGION_QUERIES.get(region, region)
    encoded_query = urllib.parse.quote(query)
    
    # Google news RSS search URL
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    logger.info("Fetching live OSINT feed for region: %s", region)
    
    try:
        feed = feedparser.parse(rss_url)
    except Exception as exc:
        logger.error("Failed to fetch RSS for %s: %s", region, exc)
        return []

    if getattr(feed, 'bozo', 0) == 1 and not feed.entries:
        logger.error("Malformed feed returned for %s", region)
        return []
        
    articles = []
    
    # Calculate cutoff for old news: we only want recent OSINT (e.g., last 14 days)
    cutoff_date = datetime.utcnow() - timedelta(days=14)

    for idx, entry in enumerate(feed.entries):
        # Stop if we hit our requested limit
        if len(articles) >= limit:
            break

        title = getattr(entry, "title", "").strip()
        link = getattr(entry, "link", "")
        published = getattr(entry, "published", "")
        description_raw = getattr(entry, "description", getattr(entry, "summary", ""))
        
        # Clean up source format: typically Google News appends " - Publisher Name" to the title
        source = "Google News"
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            title = parts[0].strip()
            source = parts[1].strip()

        # Try parsing the published date
        date_str = published
        try:
            # Struct_time to datetime
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_dt = datetime(*entry.published_parsed[:6])
                # Filter out ancient articles if any got through search
                if pub_dt < cutoff_date:
                    continue
                date_str = pub_dt.strftime("%Y-%m-%d")
        except Exception:
            pass # Keep raw string if parsing fails
            
        body = _clean_html(description_raw)

        articles.append({
            "id": f"rss_{idx}_{hash(link)}",
            "title": title,
            "body": body,
            "region": region,
            "countries": [],  # spaCy NER fills this downstream
            "date": date_str,
            "source": source,
            "url": link
        })

    logger.info("RSS Integration: Retrieved %d live articles for '%s'", len(articles), region)
    return articles


def _load_mock_data(region: str) -> list[dict]:
    """Fallback: Load articles from local static JSON."""
    try:
        with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
            all_articles = json.load(f)
    except FileNotFoundError:
        logger.error("Mock dataset not found at %s", MOCK_DATA_PATH)
        return []

    filtered = [
        a for a in all_articles
        if a.get("region", "").lower() == region.lower()
    ]
    logger.info("Mock Fallback: Returning %d static articles for '%s'", len(filtered), region)
    return filtered


def fetch_articles(region: str) -> list[dict]:
    """
    Public entry point for standardizing data extraction.
    Attempts live RSS first, falls back to mock dataset.
    """
    # 1. Primary Live Feed
    articles = _fetch_rss(region, limit=40)
    
    if articles:
        return articles

    # 2. Fallback Storage
    logger.warning("Live feed empty or failed. Defaulting to mock dataset for '%s'", region)
    return _load_mock_data(region)


def get_available_regions() -> list[str]:
    """
    Returns the supported, hardcoded geopolitical hotspots designed.
    """
    return list(REGION_QUERIES.keys())
