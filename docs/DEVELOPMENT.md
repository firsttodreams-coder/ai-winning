# Development Notes

## Languages
The browser interface supports English (LTR) and Urdu (RTL). The language switch is available in the header and stores the selected language in the browser. Product names, filter labels, notices, and explanatory copy should be added to both translation dictionaries whenever new interface text is introduced.

## Backend API
The initial FastAPI service is in `api/main.py`.

Run locally:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

## Next engineering milestones
1. Connect the browser calculator to this API when a backend host is selected.
2. Add a documented adapter for a permitted public/free product data source.
3. Store product records and source evidence with timestamps.
4. Add country-aware currency, shipping and marketplace filters.
5. Add optional AI-assisted summaries with clear source citations and a no-key local mode.
6. Add deployment, integration tests, and security review before accepting API credentials.
