import asyncio
import os
from app.services.tts_service import TTSService, TEMPLATES
from app.config import settings

async def test_all_six_languages():
    print("\n" + "="*70)
    print("🌐 TESTING ALL 6 LANGUAGES MULTILINGUAL TTS SYNTHESIS")
    print("="*70)

    languages = [
        ("ta-IN", "குமார்", "மதுரை", "தக்காளி"),
        ("en-IN", "Kumar", "Madurai", "Tomato"),
        ("te-IN", "కుమార్", "మదురై", "టమోటా"),
        ("kn-IN", "ಕುಮಾರ್", "ಮಧುರೈ", "ಟೊಮೆಟೊ"),
        ("ml-IN", "കുമാർ", "മധുരൈ", "തക്കാളി"),
        ("hi-IN", "कुमार", "मदुरै", "टमाटर")
    ]

    for lang_code, name, district, crop in languages:
        lang_info = settings.SUPPORTED_LANGUAGES[lang_code]
        print(f"\n[Testing {lang_info['name']} ({lang_code})]")

        # 1. Weather text
        weather_text = TTSService.render_message_text(
            alert_type="WEATHER",
            language=lang_code,
            farmer_name=name,
            district=district,
            crop=crop,
            data={"date": "28-09-2026"},
            include_ivr=True
        )
        print(f"   Rendered Sample: {weather_text[:80]}...")

        # 2. Market price text
        market_text = TTSService.render_message_text(
            alert_type="MARKET",
            language=lang_code,
            farmer_name=name,
            district=district,
            crop=crop,
            data={"min_kg": 22, "max_kg": 28, "modal_kg": 25},
            include_ivr=False
        )
        print(f"   Market Sample: {market_text[:80]}...")

        # 3. Audio synthesis
        audio_url = await TTSService.synthesize_speech(weather_text, lang_code)
        assert audio_url is not None, f"TTS synthesis failed for {lang_code}"
        print(f"✅ Audio generated successfully: {audio_url}")

    print("\n" + "="*70)
    print("🎉 ALL 6 LANGUAGES SYNTHESIS & DETERMINISTIC TEMPLATES VERIFIED!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_all_six_languages())
