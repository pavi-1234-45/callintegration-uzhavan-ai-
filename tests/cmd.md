http://localhost:8000



Portal Dashboard (Frontend)	http://localhost:8000/	Live statistics, alert feeds, and call queues
Farmer Registration	http://localhost:8000/register	Field staff survey form with phone & consent
Farmer Directory	http://localhost:8000/farmers	Filter registered farmers by district/crop
Weather Alerts	http://localhost:8000/weather-alerts	Open-Meteo & Uzhavan AI autonomous weather monitor
Market Updates	http://localhost:8000/market-updates	Real Agmarknet 2.0 live commodity pricing
Government Schemes	http://localhost:8000/schemes	Central & TN schemes with eligibility matching
Agricultural News	http://localhost:8000/news	PIB, The Hindu & TOI scored alerts
Voice Calls Dispatcher	http://localhost:8000/voice-calls	Manual trigger, priority queue status
Call History & Audio	http://localhost:8000/call-history	Call logs, DTMF responses, and audio playback
System Settings	http://localhost:8000/settings	Telephony provider config & Firebase sync status
Interactive API Docs (Backend)	http://localhost:8000/docs	Swagger UI for all REST endpoints and Webhooks
Firebase Status API	http://localhost:8000/api/firebase/status	Live connection info for uzhavan-ai-686d6
Firebase Sync Trigger	POST http://localhost:8000/api/firebase/sync	Sync app-registered farmers to DB & queue
Mobile App Auth Webhook	POST http://localhost:8000/api/v2/auth/register	Direct zero-modification ingestion endpoint
