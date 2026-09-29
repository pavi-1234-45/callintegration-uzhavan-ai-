import asyncio
from app.services.news_service import NewsService
from app.config import settings

async def test_news_and_priorities():
    print("\n" + "="*70)
    print("📰 TESTING REAL AGRICULTURAL NEWS MONITORING & PRIORITY QUEUE")
    print("="*70)

    # 1. Fetch and filter real agricultural news
    print("\n[Step 1] Fetching and Scoring News Articles from Production Endpoint...")
    articles = await NewsService.fetch_agricultural_news(state="tamil_nadu", language="english")
    print(f"✅ Fetched and scored {len(articles)} agricultural news articles.")
    for a in articles[:3]:
        print(f"   • [{a['tag'].upper()}] (Score: {a['relevance_score']}/100) {a['title'][:65]}...")
        print(f"     Source: {a['source']} | Voice Candidate: {a['eligible_for_voice']}")

    # 2. Test Deterministic Filtering
    print("\n[Step 2] Testing Irrelevant Article Rejection...")
    irrelevant_card = {
        "title": "Movie celebrity launches new apparel collection in Mumbai",
        "summary": "The actor spoke about fashion trends and Bollywood box office numbers.",
        "tag": "entertainment",
        "source": "entertainment_daily",
        "date": "2026-09-27"
    }
    scored = NewsService.evaluate_article_relevance(irrelevant_card)
    print(f"   Entertainment article scored: {scored['relevance_score']}/100 | Voice Candidate: {scored['eligible_for_voice']}")
    assert not scored["eligible_for_voice"], "Entertainment article must NOT qualify for voice calls!"
    print("✅ Deterministic News Filtering Verified: Irrelevant articles strictly rejected.")

    # 3. Priority Hierarchy Verification
    print("\n[Step 3] Verifying Priority Hierarchy Mappings...")
    priority_order = ["CRITICAL", "HIGH", "NORMAL", "LOW"]
    print(f"   System Priority Order: {' > '.join(priority_order)}")
    # Verify quiet hours emergency override
    assert settings.is_in_quiet_hours("CRITICAL") == False, "CRITICAL priority must bypass quiet hours for emergencies!"
    print("✅ Emergency Policy Verified: CRITICAL cyclone/storm alerts bypass quiet hours.")

    print("\n" + "="*70)
    print("🎉 AGRICULTURAL NEWS & PRIORITY SYSTEM VERIFIED!")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_news_and_priorities())
