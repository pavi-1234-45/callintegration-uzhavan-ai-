import asyncio
import json
from app.database import init_db, AsyncSessionLocal
from app.models.farmer import Farmer
from app.models.scheme import GovernmentScheme
from app.services.market_service import MarketService
from app.services.scheme_service import SchemeService
from app.services.decision_engine import DecisionEngine
from sqlalchemy import select

async def test_market_and_schemes():
    print("\n" + "="*70)
    print("📈 TESTING REAL MARKET PRICES & GOVERNMENT SCHEMES MATCHING")
    print("="*70)

    await init_db()

    # 1. Fetch Real Agmarknet Market Prices
    print("\n[Step 1] Fetching Real Market Prices from Live Agmarknet API...")
    prices = await MarketService.fetch_market_prices(state="Tamil Nadu", crop="Tomato")
    assert len(prices) > 0, "No market prices returned for Tomato!"
    tomato_price = prices[0]
    print(f"✅ Real Tomato price received:")
    print(f"   Commodity: {tomato_price['commodity']} | Variety: {tomato_price['variety']}")
    print(f"   Market: {tomato_price['market']} | Modal Price: ₹{tomato_price['modal_price']} / {tomato_price['unit']}")
    print(f"   Trend: {tomato_price['trend']} ({tomato_price['percentage_change']}%)")

    # 2. Verify Crop Isolation
    print("\n[Step 2] Testing Crop Isolation (Tomato vs Onion)...")
    # Register 1 Onion farmer
    async with AsyncSessionLocal() as db:
        # Check if farmer exists
        f_onion = (await db.execute(select(Farmer).where(Farmer.phone == "+919111222333"))).scalars().first()
        if not f_onion:
            f_onion = Farmer(
                farmer_id="UZH-FARM-ONION-01",
                name="Muthu K.",
                phone="+919111222333",
                preferred_language="ta-IN",
                farmer_category="Small",
                state="Tamil Nadu",
                district="Madurai",
                latitude=9.9252,
                longitude=78.1198,
                main_crop="Onion",
                consent_given=True,
                voice_alerts_enabled=True
            )
            db.add(f_onion)
            await db.commit()

        # Match farmers for Tomato price alert
        alert_info = MarketService.generate_market_alert(tomato_price)
        matched_tomato = await DecisionEngine.match_farmers_for_alert(
            db=db,
            alert_type="MARKET",
            event_id=alert_info["event_id"],
            crop="Tomato",
            district="Madurai"
        )
        tomato_farmer_names = [f.name for f in matched_tomato]
        print(f"   Matched farmers for Tomato: {tomato_farmer_names}")
        assert "Muthu K." not in tomato_farmer_names, "CRITICAL ERROR: Onion farmer was matched for Tomato market alert!"
        print("✅ Crop Isolation Verified: Onion farmers do NOT receive Tomato market alerts.")

    # 3. Government Scheme Verification Flow
    print("\n[Step 3] Testing Government Scheme Verification & Eligibility Flow...")
    async with AsyncSessionLocal() as db:
        # Create unverified scheme
        test_scheme = GovernmentScheme(
            scheme_name="Test Drip Irrigation Subsidy 2026",
            description="100% drip subsidy for small horticultural farmers",
            state="Tamil Nadu",
            district="Madurai",
            eligible_crop="Tomato",
            farmer_category="Small",
            eligibility_criteria="Patta holder with borewell",
            benefit="100% subsidy on drip setup",
            official_url="https://agri.tn.gov.in",
            verification_status="PENDING_VERIFICATION"
        )
        db.add(test_scheme)
        await db.commit()
        await db.refresh(test_scheme)

        # Unverified check: should NOT be eligible or trigger calls
        kumar = (await db.execute(select(Farmer).where(Farmer.name == "Kumar S."))).scalars().first()
        if kumar:
            eligible_unverified = SchemeService.is_farmer_eligible(kumar, test_scheme)
            assert not eligible_unverified, "Unverified scheme must NOT trigger calls!"
            print("✅ Verification Check Verified: Unverified scheme does NOT trigger calls.")

            # Admin publishes scheme
            test_scheme.verification_status = "PUBLISHED"
            await db.commit()
            eligible_published = SchemeService.is_farmer_eligible(kumar, test_scheme)
            assert eligible_published, "Kumar should be eligible for published Tomato scheme in Madurai!"
            print(f"✅ Published Scheme Matched: Kumar S. is eligible for '{test_scheme.scheme_name}'!")

    print("\n" + "="*70)
    print("🎉 MARKET PRICES & GOVERNMENT SCHEMES MATCHING VERIFIED!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_market_and_schemes())
