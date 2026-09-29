import os
import httpx
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.config import settings

logger = logging.getLogger(__name__)

# Approved Deterministic Multilingual Templates (No unapproved hallucinated emergency instructions)
TEMPLATES = {
    "WEATHER_HEAVY_RAIN": {
        "ta-IN": "வணக்கம் {farmer_name}. உழவன் AI பேசுகிறது. உங்கள் பகுதியான {district} மாவட்டத்தில் {date} அன்று கனமழை பெய்யும் வாய்ப்பு உள்ளது. உங்கள் {crop} பயிரை பாதுகாக்க தேவையான வடிகால் மற்றும் முன்னெச்சரிக்கை நடவடிக்கைகளை மேற்கொள்ளுங்கள்.",
        "en-IN": "Hello {farmer_name}. This is Uzhavan AI. There is a high probability of heavy rainfall in your area {district} on {date}. Please ensure adequate drainage and precautionary measures for your {crop} crop.",
        "te-IN": "నమస్కారం {farmer_name}. ఉళవన్ AI మాట్లాడుతోంది. మీ ప్రాంతమైన {district} జిల్లాలో {date} తేదీన భారీ వర్షం కురిసే అవకాశం ఉంది. దయచేసి మీ {crop} పంటకు అవసరమైన ముందస్తు జాగ్రత్తలు తీసుకోండి.",
        "kn-IN": "ನಮಸ್ಕಾರ {farmer_name}. ಇದು ಉಳವನ್ AI. ನಿಮ್ಮ ಪ್ರದೇಶವಾದ {district} ಜಿಲ್ಲೆಯಲ್ಲಿ {date} ರಂದು ಭಾರೀ ಮಳೆಯಾಗುವ ಸಾಧ್ಯತೆಯಿದೆ. ದಯವಿಟ್ಟು ನಿಮ್ಮ {crop} ಬೆಳೆಗೆ ಅಗತ್ಯ ಮುನ್ನೆಚ್ಚರಿಕೆ ಕ್ರಮಗಳನ್ನು ಕೈಗೊಳ್ಳಿ.",
        "ml-IN": "നമസ്കാരം {farmer_name}. ഉഴവൻ AI സംസാരിക്കുന്നു. നിങ്ങളുടെ പ്രദേശമായ {district} ജില്ലയിൽ {date} ന് കനത്ത മഴയ്ക്ക് സാധ്യതയുണ്ട്. ദയവായി നിങ്ങളുടെ {crop} വിള സംരക്ഷിക്കാൻ ആവശ്യമായ മുൻകരുതലുകൾ എടുക്കുക.",
        "hi-IN": "नमस्ते {farmer_name}। उझवन AI बोल रहा है। आपके क्षेत्र {district} जिले में {date} को भारी बारिश की संभावना है। कृपया अपनी {crop} फसल के लिए आवश्यक जल निकासी और सावधानी बरतें।"
    },
    "WEATHER_CYCLONE_STORM": {
        "ta-IN": "அவசர எச்சரிக்கை {farmer_name}. உழவன் AI பேசுகிறது. {district} பகுதியில் கடுமையான புயல் மற்றும் பலத்த காற்று வீசக்கூடும். பாதுகாப்பான இடத்தில் இருங்கள் மற்றும் அறுவடை செய்த {crop} பயிர்களை பாதுகாப்பாக வையுங்கள்.",
        "en-IN": "Emergency alert {farmer_name}. This is Uzhavan AI. Severe storm and high winds are expected in {district}. Please stay in safe shelter and protect harvested {crop} produce.",
        "te-IN": "అత్యవసర హెచ్చరిక {farmer_name}. ఉళవన్ AI. {district} ప్రాంతంలో తీవ్ర తుఫాను వచ్చే అవకాశం ఉంది. దయచేసి సురక్షిత ప్రదేశంలో ఉండండి.",
        "kn-IN": "ತುರ್ತು ಎಚ್ಚರಿಕೆ {farmer_name}. ಉಳವನ್ AI. {district} ಪ್ರದೇಶದಲ್ಲಿ ತೀವ್ರ ಬಿರುಗಾಳಿ ನಿರೀಕ್ಷಿಸಲಾಗಿದೆ. ದಯವಿಟ್ಟು ಸುರಕ್ಷಿತವಾಗಿರಿ.",
        "ml-IN": "അടിയന്തര മുന്നറിയിപ്പ് {farmer_name}. ഉഴവൻ AI. {district} ൽ ശക്തമായ കാറ്റും കൊടുങ്കാറ്റും ഉണ്ടാകാൻ സാധ്യതയുണ്ട്. ജാഗ്രത പാലിക്കുക.",
        "hi-IN": "आपातकालीन चेतावनी {farmer_name}। उझवन AI। {district} क्षेत्र में भयंकर तूफान की संभावना है। कृपया सुरक्षित स्थान पर रहें और अपनी {crop} फसल को सुरक्षित करें।"
    },
    "WEATHER_EXTREME_HEAT": {
        "ta-IN": "வணக்கம் {farmer_name}. உழவன் AI பேசுகிறது. உங்கள் பகுதியான {district} மாவட்டத்தில் கடுமையான வெப்ப அலை நிலவுகிறது. உங்கள் {crop} பயிருக்கு தேவையான நீர் பாய்ச்சல் செய்யுங்கள்.",
        "en-IN": "Hello {farmer_name}. This is Uzhavan AI. Extreme heat wave conditions are prevailing in {district}. Please arrange timely irrigation for your {crop} crop.",
        "te-IN": "నమస్కారం {farmer_name}. మీ ప్రాంతమైన {district} లో తీవ్రమైన ఎండలు ఉన్నాయి. మీ {crop} పంటకు నీటిపారుదల ఏర్పాట్లు చేయండి.",
        "kn-IN": "ನಮಸ್ಕಾರ {farmer_name}. {district} ಜಿಲ್ಲೆಯಲ್ಲಿ ತೀವ್ರ ಬಿಸಿಲಿನ ವಾತಾವರಣವಿದೆ. ನಿಮ್ಮ {crop} ಬೆಳೆಗೆ ಸೂಕ್ತ ನೀರಾವರಿ ಒದಗಿಸಿ.",
        "ml-IN": "നമസ്കാരം {farmer_name}. {district} ജില്ലയിൽ കടുത്ത ചൂട് അനുഭവപ്പെടുന്നു. {crop} വിളകൾക്ക് ആവശ്യമായ നനവ് ഉറപ്പാക്കുക.",
        "hi-IN": "नमस्ते {farmer_name}। {district} जिले में अत्यधिक गर्मी और लू चल रही है। कृपया अपनी {crop} फसल के लिए तुरंत सिंचाई की व्यवस्था करें।"
    },
    "MARKET_PRICE": {
        "ta-IN": "வணக்கம் {farmer_name}. உழவன் AI சந்தை தகவல். இன்று உங்கள் பதிவு செய்த {crop} பயிரின் சந்தை விலை கிலோ ஒன்றுக்கு ரூபாய் {min_kg} முதல் ரூபாய் {max_kg} வரை உள்ளது. சராசரி விலை ரூபாய் {modal_kg} ஆக உள்ளது.",
        "en-IN": "Hello {farmer_name}. Uzhavan AI Market Update. Today the market price for your registered crop {crop} ranges from ₹{min_kg} to ₹{max_kg} per kilogram, with an average modal price of ₹{modal_kg}.",
        "te-IN": "నమస్కారం {farmer_name}. ఉళవన్ AI మార్కెట్ సమాచారం. ఈరోజు మీ {crop} పంట మార్కెట్ ధర కిలోకు ₹{min_kg} నుండి ₹{max_kg} వరకు ఉంది. సగటు ధర ₹{modal_kg}.",
        "kn-IN": "ನಮಸ್ಕಾರ {farmer_name}. ಉಳವನ್ AI ಮಾರುಕಟ್ಟೆ ಮಾಹಿತಿ. ಇಂದು ನಿಮ್ಮ {crop} ಬೆಳೆಯ ಮಾರುಕಟ್ಟೆ ಬೆಲೆ ಕೆಜಿಗೆ ₹{min_kg} ರಿಂದ ₹{max_kg} ವರೆಗೆ ಇದೆ.",
        "ml-IN": "നമസ്കാരം {farmer_name}. ഉഴവൻ AI മാർക്കറ്റ് അപ്ഡേറ്റ്. ഇന്ന് നിങ്ങളുടെ {crop} വിളയുടെ വിപണി വില കിലോഗ്രാമിന് ₹{min_kg} മുതൽ ₹{max_kg} വരെയാണ്.",
        "hi-IN": "नमस्ते {farmer_name}। उझवन AI मंडी भाव। आज आपकी पंजीकृत {crop} फसल का मंडी भाव ₹{min_kg} से ₹{max_kg} प्रति किलो है। औसत भाव ₹{modal_kg} है।"
    },
    "GOVERNMENT_SCHEME": {
        "ta-IN": "வணக்கம் {farmer_name}. அரசு நலத்திட்ட அறிவிப்பு. உங்கள் {crop} பயிருக்கும் உங்கள் விவசாய வகைக்கும் ஏற்ற புதிய அரசு திட்டம் {scheme_name} வெளியிடப்பட்டுள்ளது. விவரங்களை அறிய அருகிலுள்ள வேளாண் அலுவலகத்தை தொடர்பு கொள்ளவும்.",
        "en-IN": "Hello {farmer_name}. Government Scheme Announcement. A new verified scheme '{scheme_name}' has been announced for {crop} farmers. Please check your nearest agriculture office for benefits.",
        "te-IN": "నమస్కారం {farmer_name}. ప్రభుత్వ పథకం సమాచారం. {crop} రైతుల కోసం '{scheme_name}' పథకం అందుబాటులోకి వచ్చింది. ప్రయోజనాల కోసం సమీప వ్యవసాయ కార్యాలయాన్ని సంప్రదించండి.",
        "kn-IN": "ನಮಸ್ಕಾರ {farmer_name}. ಸರ್ಕಾರಿ ಯೋಜನೆ ಮಾಹಿತಿ. {crop} ಬೆಳೆಗಾರರಿಗೆ '{scheme_name}' ಯೋಜನೆ ಪ್ರಕಟಿಸಲಾಗಿದೆ. ಹೆಚ್ಚಿನ ವಿವರಗಳಿಗಾಗಿ ಕೃಷಿ ಇಲಾಖೆಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        "ml-IN": "നമസ്കാരം {farmer_name}. സർക്കാർ പദ്ധതി അറിയിപ്പ്. {crop} കർഷകർക്കായി പുതിയ '{scheme_name}' പദ്ധതി പ്രഖ്യാപിച്ചിരിക്കുന്നു. വിശദാംശങ്ങൾക്കായി കൃഷി ഭവനുമായി ബന്ധപ്പെടുക.",
        "hi-IN": "नमस्ते {farmer_name}। सरकारी योजना सूचना। {crop} किसानों के लिए नई सरकारी योजना '{scheme_name}' शुरू की गई है। लाभ प्राप्त करने के लिए कृषि कार्यालय से संपर्क करें।"
    },
    "AGRICULTURAL_NEWS": {
        "ta-IN": "வணக்கம் {farmer_name}. முக்கிய வேளாண் செய்தி. {news_title}. கூடுதல் தகவலுக்கு உழவன் AI தளத்தை பார்வையிடவும்.",
        "en-IN": "Hello {farmer_name}. Important Agricultural Update: {news_title}. Please stay tuned to Uzhavan AI for further alerts.",
        "te-IN": "నమస్కారం {farmer_name}. ముఖ్యమైన వ్యవసాయ వార్త: {news_title}.",
        "kn-IN": "ನಮಸ್ಕಾರ {farmer_name}. ಪ್ರಮುಖ ಕೃಷಿ ಸುದ್ದಿ: {news_title}.",
        "ml-IN": "നമസ്കാരം {farmer_name}. പ്രധാന കാർഷിക വാർത്ത: {news_title}.",
        "hi-IN": "नमस्ते {farmer_name}। महत्वपूर्ण कृषि समाचार: {news_title}।"
    },
    "IVR_MENU": {
        "ta-IN": " இந்த செய்தியை மீண்டும் கேட்க 1 ஐ அழுத்தவும். கூடுதல் தகவலுக்கு 2 ஐ அழுத்தவும். அழைப்பை முடிக்க 9 ஐ அழுத்தவும். குரல் அழைப்புகளை நிறுத்த 0 ஐ அழுத்தவும்.",
        "en-IN": " Press 1 to repeat this message. Press 2 for more information. Press 9 to end call. Press 0 to opt out of voice alerts.",
        "te-IN": " ఈ సందేశాన్ని మళ్లీ వినడానికి 1 నొక్కండి. మరింత సమాచారం కోసం 2 నొక్కండి. కాల్ ముగించడానికి 9 నొక్కండి. కాల్స్ నిలిపివేయడానికి 0 నొక్కండి.",
        "kn-IN": " ಈ ಸಂದೇಶವನ್ನು ಪುನರಾವರ್ತಿಸಲು 1 ಒತ್ತಿರಿ. ಹೆಚ್ಚಿನ ಮಾಹಿತಿಗಾಗಿ 2 ಒತ್ತಿರಿ. ಕರೆ ಮುಕ್ತಾಯಗೊಳಿಸಲು 9 ಒತ್ತಿರಿ. ಸೇವೆ ರದ್ದುಗೊಳಿಸಲು 0 ಒತ್ತಿರಿ.",
        "ml-IN": " ഈ സന്ദേശം വീണ്ടും കേൾക്കാൻ 1 അമർത്തുക. കൂടുതൽ വിവരങ്ങൾക്ക് 2 അമർത്തുക. കോൾ അവസാനിപ്പിക്കാൻ 9 അമർത്തുക. സേവനം നിർത്താൻ 0 അമർത്തുക.",
        "hi-IN": " इस संदेश को दोबारा सुनने के लिए 1 दबाएं। अधिक जानकारी के लिए 2 दबाएं। कॉल समाप्त करने के लिए 9 दबाएं। अलर्ट बंद करने के लिए 0 दबाएं।"
    }
}

class TTSService:
    @staticmethod
    def render_message_text(
        alert_type: str,
        language: str,
        farmer_name: str,
        district: str,
        crop: str,
        data: Dict[str, Any],
        include_ivr: bool = True
    ) -> str:
        """
        Renders deterministic text using approved multilingual templates.
        """
        lang = language if language in settings.SUPPORTED_LANGUAGES else "ta-IN"

        # Map alert type to template key
        template_key = "WEATHER_HEAVY_RAIN"
        if alert_type == "CYCLONE_STORM":
            template_key = "WEATHER_CYCLONE_STORM"
        elif alert_type == "EXTREME_HEAT":
            template_key = "WEATHER_EXTREME_HEAT"
        elif alert_type == "MARKET":
            template_key = "MARKET_PRICE"
        elif alert_type == "SCHEME":
            template_key = "GOVERNMENT_SCHEME"
        elif alert_type == "NEWS":
            template_key = "AGRICULTURAL_NEWS"

        template = TEMPLATES.get(template_key, {}).get(lang) or TEMPLATES.get(template_key, {}).get("en-IN")

        # Prepare formatting variables
        date_str = data.get("date", datetime.now().strftime("%d-%m-%Y"))
        min_kg = f"{data.get('per_kg_min', 0):.0f}"
        max_kg = f"{data.get('per_kg_max', 0):.0f}"
        modal_kg = f"{data.get('per_kg_modal', 0):.0f}"
        scheme_name = data.get("scheme_name", "Agricultural Welfare Scheme")
        news_title = data.get("news_title", "Agriculture Advisory")

        formatted_text = template.format(
            farmer_name=farmer_name,
            district=district,
            crop=crop,
            date=date_str,
            min_kg=min_kg,
            max_kg=max_kg,
            modal_kg=modal_kg,
            scheme_name=scheme_name,
            news_title=news_title
        )

        if include_ivr:
            ivr_text = TEMPLATES["IVR_MENU"].get(lang, TEMPLATES["IVR_MENU"]["en-IN"])
            formatted_text += ivr_text

        return formatted_text

    @staticmethod
    async def synthesize_speech(text: str, language: str) -> Optional[str]:
        """
        Synthesizes speech using the verified production Uzhavan TTS endpoint.
        Caches the audio file in static/audio/ and returns the relative audio URL.
        """
        lang_config = settings.SUPPORTED_LANGUAGES.get(language, settings.SUPPORTED_LANGUAGES["ta-IN"])
        tts_code = lang_config["tts_code"]

        # Cache key based on text and language
        cache_hash = hashlib.md5(f"{tts_code}_{text}".encode("utf-8")).hexdigest()
        filename = f"tts_{cache_hash}.mp3"
        filepath = os.path.join("app", "static", "audio", filename)

        if os.path.exists(filepath):
            return f"/static/audio/{filename}"

        url = f"{settings.UZHAVAN_LIVE_API_BASE}/api/tts/speak"
        params = {"text": text[:900], "lang": tts_code}

        try:
            async with httpx.AsyncClient(timeout=25.0, verify=False) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    with open(filepath, "wb") as f:
                        f.write(res.content)
                    return f"/static/audio/{filename}"
                else:
                    logger.error(f"TTS API failed HTTP {res.status_code}: {res.text}")
                    return None
        except Exception as e:
            logger.error(f"TTS synthesis exception: {e}")
            return None
