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
GET `/api/v1/trends?country=PK` reads Google's public Trending Now RSS feed. Supported country codes: PK, US, GB, AE, SA, IN, CA, AU, DE, OM, QA, KW and BH (13 markets). The response includes trend title, Google's approximate traffic bucket, start time, related news headlines and source links.

Important limitations:
- The feed returns a small set of broad trending searches, not product-specific search volume.
- Traffic values are approximate buckets, not exact counts.
- Trends may reflect news, sports or entertainment rather than shopping demand.
- A missing trend does not mean a product has no demand.
- Google may rate-limit or change the feed; the API returns a temporary-unavailable response rather than inventing results.
- Do not convert this signal directly into a winning-product score without product relevance checks and additional evidence.

## Product economics
POST `/api/v1/product-economics` estimates per-unit profit, margin, ROI and break-even price using the costs and price supplied by the user.

## Supplier and marketplace CSV imports

The bilingual browser importer accepts up to 50 supplier quote rows and up to 50 marketplace listing rows per CSV file. It validates the complete file before changing the form, rejects files above the limit, and dynamically creates the matching comparison inputs so all imported rows can be reviewed and edited. Supplier rows are checked against the selected country's available supplier IDs; marketplace rows validate positive prices, non-negative shipping, optional sold counts, source URLs and capture timestamps. The CSV parser supports quoted commas, escaped quotes and multiline fields, rejects malformed quote placement, duplicate or empty headers and row-width mismatches, and displays the affected CSV record number for row validation errors.

Imported prices, stock and sold counts remain user-supplied observations. CSV import does not connect a supplier account, fetch a marketplace feed or independently verify the source. The backend comparison endpoints also cap each offers/listings array at 50 records.

The API and backend GitHub Actions workflows extract the inline JavaScript from `index.html` and run `node --check` so syntax errors in the mobile/desktop interface are caught alongside Python tests.

## Current integration status (20 November 2026)

Already implemented in the repository: bilingual country-level Trends display; the supplier directory API and frontend; supplier quote and marketplace listing comparison APIs; CSV import templates for manually observed evidence; source URLs and capture-time freshness metadata; currency/country validation; supplier-to-marketplace candidate matching; and API tests in GitHub Actions. These features do not imply that a supplier account is connected or that marketplace prices, stock, sales counts or competitor counts are being fetched automatically.

The 13 supported Trends markets are PK, US, GB, AE, SA, IN, CA, AU, DE, OM, QA, KW and BH. Trends remain broad country-level discovery signals and must not be represented as product-specific sales evidence.

## Next engineering milestones
1. Obtain authorized supplier credentials and API/feed specifications, beginning with Zambeel across Pakistan, UAE and Saudi Arabia; then Tejaraa and Wave Byte. Keep other GCC providers available as manual/import options until access is approved.
2. Implement one supplier adapter at a time against the normalized offer schema. Validate country, currency, product ID, price, stock, MOQ, delivery, source URL and retrieval timestamp before marking an adapter connected.
3. Add permitted marketplace evidence adapters only where official APIs, partner feeds or other authorized access are available; never bypass login, rate limits or terms.
4. Add product-specific demand evidence and relevance checks. Do not treat broad Google Trends, generic traffic buckets or category popularity as proof of product sales.
5. Add optional AI-assisted analysis that cites each input source and separates verified observations, user-entered values and estimates.
6. Complete end-to-end deployment checks, mobile/desktop user testing, secret-handling review and stale-feed/error-state tests before production claims.


## Supplier-to-marketplace catalogue matching

POST `/api/v1/catalog/match` accepts imported supplier and marketplace product records (up to 50 each). The matcher:
- prioritizes an exact SKU match when both records provide the same SKU, even if one title omits a model/size number;
- rejects conflicting supplied brand, model, size, colour, pack-quantity or condition attributes;
- rejects conflicting title-number fingerprints unless the records share an exact SKU or both provide the same structured model value;
- returns a heuristic similarity score, a coarse confidence label, exclusion counts and a match reason;
- enforces one-to-one assignment and returns unmatched product IDs.

This is a candidate-matching aid, not proof of identical products. Every result has `review_required: true`; verify images, model, dimensions, pack quantity, quality, authenticity, country, stock and supplier eligibility before using a price comparison or listing. SKU quality depends on the supplier and marketplace data provided.


## Unified supplier and marketplace profitability comparison

The `POST /api/v1/product-profitability/compare` endpoint combines user-entered supplier offers and marketplace listings for the same product and market. It reports delivered marketplace price range/average/median alongside each supplier's landed unit cost, profit per order at the planned selling price, estimated profit at the marketplace average, break-even price, delivery/stock details, and estimated MOQ investment when MOQ is supplied.

Request fields include `product_name`, `country`, matching `currency`, `planned_selling_price`, `product_identity_confirmed: true`, optional platform fee/marketing/returns costs, at least one `offers` entry, and at least one `listings` entry. The identity flag is a manual confirmation gate: it records that the user checked the same product and variant, not an automated identity verification. An optional `catalog_match_context` preserves the selected catalogue suggestion as unverified provenance. Supplier offers retain source URL and capture time; marketplace listings retain listing URL and capture time. Freshness metadata is descriptive only. Neither input is fetched or independently verified by this endpoint.

MOQ investment is calculated as landed unit cost multiplied by MOQ. Profit estimates exclude taxes, duties, COD, payment fees and unentered costs. The best-supplier field ranks suppliers by estimated profit at the planned selling price, not by verified sales or guaranteed outcomes.
