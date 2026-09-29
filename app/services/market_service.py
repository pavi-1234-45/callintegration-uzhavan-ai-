import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

class MarketService:
    @staticmethod
    async def fetch_market_prices(state: str = "Tamil Nadu", crop: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches REAL daily agricultural market prices from live Uzhavan AI backend (Agmarknet 2.0).
        Strictly avoids mock/fake data.
        """
        url = f"{settings.UZHAVAN_LIVE_API_BASE}/api/market/prices?state={state}&lang=en&category=all"
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    prices_dict = data.get("prices", {})
                    source = data.get("source", "Agmarknet 2.0 & Agmart.in (Govt of India)")
                    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))

                    all_items = []
                    for cat in ["vegetables", "fruits", "grains"]:
                        for item in prices_dict.get(cat, []):
                            item_copy = dict(item)
                            item_copy["category"] = cat
                            item_copy["source"] = source
                            item_copy["state"] = state
                            item_copy["date"] = date_str
                            all_items.append(item_copy)

                    if crop:
                        # Case-insensitive commodity filter
                        crop_clean = crop.strip().lower()
                        filtered = [
                            p for p in all_items 
                            if crop_clean in p.get("commodity", "").lower() 
                            or p.get("commodity", "").lower() in crop_clean
                        ]
                        return filtered

                    return all_items
                else:
                    logger.error(f"Market API returned HTTP {res.status_code}: {res.text}")
                    raise RuntimeError(f"Market service returned error HTTP {res.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch market prices from real source: {e}")
            raise RuntimeError(f"Real market price data unavailable: {str(e)}")

    @staticmethod
    def generate_market_alert(price_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a structured alert representation for a matched crop price update.
        """
        commodity = price_item.get("commodity", "Crop")
        variety = price_item.get("variety", "Standard")
        modal_price = price_item.get("modal_price", 0)
        min_price = price_item.get("min_price", 0)
        max_price = price_item.get("max_price", 0)
        unit = price_item.get("unit", "Quintal")
        market = price_item.get("market", "APMC Mandi")
        trend = price_item.get("trend", "stable")
        pct = price_item.get("percentage_change", 0.0)
        date_str = price_item.get("date", datetime.now().strftime("%Y-%m-%d"))

        # Convert quintal price to per-kg price if applicable (1 quintal = 100 kg)
        per_kg_modal = modal_price / 100.0 if unit == "Quintal" else modal_price
        per_kg_min = min_price / 100.0 if unit == "Quintal" else min_price
        per_kg_max = max_price / 100.0 if unit == "Quintal" else max_price

        event_id = f"MARKET_{commodity.upper().replace(' ', '_')}_{date_str.replace('-', '_')}"

        title = f"Daily Mandi Price for {commodity} ({date_str})"
        summary = (
            f"Today's modal price for {commodity} ({variety}) at {market} is "
            f"₹{modal_price:.0f} per {unit} (approx. ₹{per_kg_min:.1f} - ₹{per_kg_max:.1f}/kg). "
            f"Price trend is {trend}."
        )

        return {
            "event_id": event_id,
            "commodity": commodity,
            "variety": variety,
            "modal_price": modal_price,
            "min_price": min_price,
            "max_price": max_price,
            "per_kg_modal": per_kg_modal,
            "per_kg_min": per_kg_min,
            "per_kg_max": per_kg_max,
            "unit": unit,
            "market": market,
            "trend": trend,
            "percentage_change": pct,
            "title": title,
            "summary": summary,
            "severity": "NORMAL"
        }
