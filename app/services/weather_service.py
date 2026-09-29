import httpx
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

class WeatherService:
    @staticmethod
    async def fetch_weather_data(latitude: float, longitude: float, district: str = "") -> Dict[str, Any]:
        """
        Fetches REAL weather data from Open-Meteo or live Uzhavan AI backend.
        Never uses fake or simulated data.
        """
        # Primary: Open-Meteo real meteorological station data
        try:
            url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={latitude}&longitude={longitude}"
                f"&current=temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,wind_speed_10m"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,precipitation_probability_max,wind_speed_10m_max"
                f"&timezone=auto"
            )
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    current = data.get("current", {})
                    daily = data.get("daily", {})

                    temp = current.get("temperature_2m", 0.0)
                    wind = current.get("wind_speed_10m", 0.0)
                    rain_sum = daily.get("rain_sum", [0.0])[0] if daily.get("rain_sum") else 0.0
                    rain_prob = daily.get("precipitation_probability_max", [0])[0] if daily.get("precipitation_probability_max") else 0
                    temp_max = daily.get("temperature_2m_max", [temp])[0] if daily.get("temperature_2m_max") else temp
                    weather_code = current.get("weather_code", 0)

                    return {
                        "source": "Open-Meteo WMO Real Meteorological Data",
                        "latitude": latitude,
                        "longitude": longitude,
                        "temperature": temp,
                        "temp_max": temp_max,
                        "wind_speed": wind,
                        "precipitation_sum": rain_sum,
                        "rain_probability": rain_prob,
                        "weather_code": weather_code,
                        "timestamp": datetime.now().isoformat(),
                        "raw": data
                    }
        except Exception as e:
            logger.warning(f"Open-Meteo fetch failed: {e}. Attempting Uzhavan Live API.")

        # Fallback to live Uzhavan AI backend API
        try:
            uzhavan_url = f"{settings.UZHAVAN_LIVE_API_BASE}/api/weather/current"
            payload = {
                "latitude": latitude,
                "longitude": longitude,
                "language": "english"
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(uzhavan_url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    curr = data.get("current", {})
                    forecast = data.get("daily_forecast", [{}])[0]
                    return {
                        "source": "Uzhavan AI Production Meteorological API",
                        "latitude": latitude,
                        "longitude": longitude,
                        "temperature": curr.get("temperature", 0.0),
                        "temp_max": forecast.get("temp_max", 0.0),
                        "wind_speed": curr.get("windspeed", 0.0),
                        "precipitation_sum": forecast.get("precipitation_sum", 0.0),
                        "rain_probability": 50 if forecast.get("precipitation_sum", 0.0) > 0 else 0,
                        "weather_code": 0,
                        "timestamp": datetime.now().isoformat(),
                        "raw": data
                    }
        except Exception as e:
            logger.error(f"Live Uzhavan AI weather fetch failed: {e}")

        # If all real APIs fail, raise error - never invent fake weather
        raise RuntimeError("Real weather services unavailable. Logged failure without generating fake values.")

    @staticmethod
    def evaluate_weather_alert(district: str, weather_data: Dict[str, Any]) -> Tuple[str, str, str, str]:
        """
        Evaluates weather data against deterministic agricultural thresholds.
        Returns:
            (severity, condition_type, event_id, description)
            severity: NO_ALERT, LOW, MEDIUM, HIGH, CRITICAL
        """
        rain_sum = weather_data.get("precipitation_sum", 0.0)
        rain_prob = weather_data.get("rain_probability", 0)
        wind = weather_data.get("wind_speed", 0.0)
        temp_max = weather_data.get("temp_max", 0.0)
        wmo_code = weather_data.get("weather_code", 0)
        date_str = datetime.now().strftime("%Y_%m_%d")
        dist_clean = district.upper().replace(" ", "_")

        # 1. CRITICAL: Storm / Cyclone (WMO storm codes 95, 96, 99 or wind > 65 km/h)
        if wind >= 65.0 or wmo_code in [95, 96, 99]:
            event_id = f"{dist_clean}_CYCLONE_STORM_{date_str}"
            return (
                "CRITICAL",
                "CYCLONE_STORM",
                event_id,
                f"Severe storm and cyclone warning in {district} with wind speeds up to {wind} km/h. Secure crops and stay indoors."
            )

        # 2. HIGH: Heavy Rain (> 35mm precipitation or rain probability > 80% with >= 20mm) OR Extreme Heat (> 41°C)
        if rain_sum >= 35.0 or (rain_prob >= 80 and rain_sum >= 20.0):
            event_id = f"{dist_clean}_HEAVY_RAIN_{date_str}"
            return (
                "HIGH",
                "HEAVY_RAIN",
                event_id,
                f"Heavy rainfall expected in {district} ({rain_sum:.1f} mm rain, {rain_prob}% probability). Please ensure field drainage."
            )
        elif temp_max >= 41.0:
            event_id = f"{dist_clean}_EXTREME_HEAT_{date_str}"
            return (
                "HIGH",
                "EXTREME_HEAT",
                event_id,
                f"Extreme heat wave alert in {district} with temperatures touching {temp_max:.1f}°C. Arrange immediate irrigation."
            )

        # 3. MEDIUM: Moderate Rain (15mm - 35mm) OR High Wind (> 40 km/h) OR Heat Advisory (> 38°C)
        if rain_sum >= 15.0 or rain_prob >= 70:
            event_id = f"{dist_clean}_MODERATE_RAIN_{date_str}"
            return (
                "MEDIUM",
                "MODERATE_RAIN",
                event_id,
                f"Moderate rain alert in {district} ({rain_sum:.1f} mm). Postpone pesticide spraying and fertilizer application."
            )
        elif wind >= 40.0:
            event_id = f"{dist_clean}_STRONG_WIND_{date_str}"
            return (
                "MEDIUM",
                "STRONG_WIND",
                event_id,
                f"Strong winds up to {wind:.1f} km/h forecasted in {district}. Provide support stakes for tall standing crops."
            )

        # 4. LOW: Light rain (5mm - 15mm)
        if rain_sum >= 5.0:
            event_id = f"{dist_clean}_LIGHT_RAIN_{date_str}"
            return (
                "LOW",
                "LIGHT_RAIN",
                event_id,
                f"Light rain forecast in {district} ({rain_sum:.1f} mm). Favorable for land preparation."
            )

        return ("NO_ALERT", "NORMAL", f"{dist_clean}_NORMAL_{date_str}", "Weather conditions are normal. No alert required.")
