# Uzhavan AI – Autonomous Multilingual Voice Communication System & Farmer Survey Portal

«Uzhavan AI's autonomous voice communication system enables farmers without smartphones to receive personalized weather alerts, crop-specific daily market prices, verified government scheme information, and important agricultural news directly on their normal phones in their preferred local language without requiring an internet connection or app installation.»

---

## Architecture Overview

```
Registered Farmers (Survey Portal)
        ↓
Autonomous Monitoring Engine (Weather / Market / Schemes / News)
        ↓
Decision Engine (Relevance, Crop Match, Location Match, Deduplication, Quiet Hours)
        ↓
Prioritized Queue (CRITICAL > HIGH > NORMAL > LOW)
        ↓
Multilingual TTS Engine (Tamil, English, Telugu, Kannada, Malayalam, Hindi)
        ↓
Telephony Provider Abstraction (Exotel PSTN / Twilio / Simulation Bridge)
        ↓
Carrier Call Signaling & IVR DTMF Menu (1=Repeat, 2=More Info, 9=End, 0=Opt Out)
        ↓
StatusCallback Webhook Handler (RINGING, ANSWERED, BUSY, NO_ANSWER, COMPLETED)
        ↓
CallLog Tracking, Retry Scheduler & Live Portal Dashboard
```

---

## Quickstart & Local Run Instructions

### 1. Activate Environment & Install Dependencies
```bash
cd /Users/pavi/callintegration
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
Copy and adjust `.env`:
```bash
cp .env.example .env
```

### 3. Launch Development Server
```bash
python run.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## Running Verification Test Suites

```bash
# Run the First Vertical Slice End-to-End Test:
PYTHONPATH=. python tests/test_vertical_slice.py

# Run Full Automated Pytest Suite:
pytest -v
```
