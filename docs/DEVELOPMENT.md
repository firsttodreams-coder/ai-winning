# Development Notes

## Languages
The browser interface supports English (LTR) and Urdu (RTL). The language switch is available in the header and stores the selected language in the browser. Product names, filter labels, notices, and explanatory copy should be added to both translation dictionaries whenever new interface text is introduced.

## Backend API
The FastAPI service is in `api/main.py`. It is also deployed as a Cloudflare Python Worker through `src/main.py`.

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn api.main:app --reload
```

OpenAPI documentation is available at `/docs` while the API is running.

## Scoring contract
POST `/api/v1/score` accepts five integer signals from 1 to 10:
- Demand evidence: 30%
- Competition advantage: 20%
- Profit margin potential: 25%
- Shipping ease: 10%
- Trend strength: 15%

The API returns a 0–100 estimate and the weights used. It scores only the submitted values; it does not fetch marketplace data or claim to be AI-generated.

## Public trends source
GET `/api/v1/trends?country=PK` reads Google's public Trending Now RSS feed. Supported country codes: PK, US, GB, AE, SA, IN, CA, AU and DE. The response includes trend title, Google's approximate traffic bucket, start time, related news headlines and source links.

Important limitations:
- The feed returns a small set of broad trending searches, not product-specific search volume.
- Traffic values are approximate buckets, not exact counts.
- Trends may reflect news, sports or entertainment rather than shopping demand.
- A missing trend does not mean a product has no demand.
- Google may rate-limit or change the feed; the API returns a temporary-unavailable response rather than inventing results.
- Do not convert this signal directly into a winning-product score without product relevance checks and additional evidence.

## Product economics
POST `/api/v1/product-economics` estimates per-unit profit, margin, ROI and break-even price using the costs and price supplied by the user.

## Next engineering milestones
1. Show country-level Google Trends signals in the bilingual frontend, with source timestamps and clear caveats.
2. Add permitted marketplace evidence adapters where access is available; never scrape behind logins or bypass access controls.
3. Store product records and source evidence with timestamps.
4. Add country-aware currency, shipping and marketplace filters, including verified supplier pricing and MOQ where source access permits.
5. Add optional AI-assisted summaries with source citations and a no-key/local mode where feasible.
6. Add integration tests and a security review before accepting API credentials.
