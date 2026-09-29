import httpx
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

class NewsService:
    @staticmethod
    async def fetch_agricultural_news(state: str = "tamil_nadu", language: str = "english") -> List[Dict[str, Any]]:
        """
        Fetches REAL agricultural news from live Uzhavan AI news service.
        Applies deterministic filtering to reject irrelevant articles.
        """
        url = f"{settings.UZHAVAN_LIVE_API_BASE}/api/news/cards?language={language}&state={state}&crop="
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    raw_cards = data.get("cards", [])
                    filtered_news = []

                    for card in raw_cards:
                        scored = NewsService.evaluate_article_relevance(card)
                        if scored["relevance_score"] >= 60: # Threshold for agricultural relevance
                            filtered_news.append(scored)

                    return filtered_news
                else:
                    logger.error(f"News API returned HTTP {res.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Failed to fetch agricultural news: {e}")
            return []

    @staticmethod
    def evaluate_article_relevance(card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministic rule-based relevance scoring:
        - Agricultural/department announcements: +30
        - Weather / flood / drought / rainfall: +25
        - Government scheme / MSP / subsidy: +25
        - Pest attack / crop advisory: +30
        - Irrelevant/entertainment: 0
        """
        title = card.get("title", "").lower()
        summary = card.get("summary", "").lower()
        tag = card.get("tag", "general").lower()
        full_text = f"{title} {summary}"

        score = 40 # Base score for articles from agri news endpoint

        if tag in ["weather", "monsoon", "rainfall", "drought"]:
            score += 30
        elif tag in ["scheme", "subsidy", "kisan", "msp"]:
            score += 25
        elif tag in ["pest", "disease", "fertilizer"]:
            score += 35

        # Keywords boost
        high_importance_keywords = [
            "tnau", "agriculture department", "minister", "procurement",
            "paddy", "tomato", "cotton", "direct purchase", "monsoon forecast",
            "drought hotspot", "emergency", "alert", "subsidy"
        ]
        for kw in high_importance_keywords:
            if kw in full_text:
                score += 10
                break

        # Generate stable event ID
        h = hashlib.md5(f"{card.get('source','')}_{card.get('date','')}_{title[:30]}".encode()).hexdigest()[:8]
        event_id = f"NEWS_{card.get('source','').upper()}_{card.get('date','').replace('-', '_')}_{h}"

        return {
            "title": card.get("title", ""),
            "summary": card.get("summary", ""),
            "source": card.get("source", "PIB / Govt"),
            "tag": tag,
            "date": card.get("date", datetime.now().strftime("%Y-%m-%d")),
            "image_url": card.get("image_url"),
            "relevance_score": min(score, 100),
            "event_id": event_id,
            "eligible_for_voice": score >= 75
        }
