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
GET `/api/v1/trends?country=PK` reads Google's public Trending Now RSS feed. GET `/api/v1/trends/match?country=PK&product_name=portable%20blender` checks literal English token overlap between a supplied product name and current trend titles; results are discovery hints, not sales evidence. Supported country codes: PK, US, GB, AE, SA, IN, CA, AU, DE, OM, QA, KW and BH (13 markets). The response includes trend title, Google's approximate traffic bucket, start time, related news headlines and source links.

Important limitations:
- The feed returns a small set of broad trending searches, not product-specific search volume.
- Traffic values are approximate buckets, not exact counts.
- Trends may reflect news, sports or entertainment rather than shopping demand.
- A missing trend does not mean a product has no demand.
- Google may rate-limit or change the feed; the API returns a temporary-unavailable response rather than inventing results.
- Do not convert this signal directly into a winning-product score without product relevance checks and additional evidence.

## Product-specific trend matching

The product trend matcher compares Unicode product-name tokens (including Urdu/Arabic-script text and mixed Urdu-English names) with current Google Trends RSS titles for the selected country. It returns only matches covering at least half of the supplied product-name tokens, with matched terms and a simple overlap percentage. This is a lexical relevance filter, not a Google Trends product query, exact search-volume metric, sales signal or forecast. No match does not imply no demand.

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


## Supplier catalogue quote handoff (22 November 2026)

The supplier-catalog CSV template now accepts optional quote evidence columns in addition to product identity fields: `supplier_id`, `supplier_name`, `product_cost`, `shipping_cost`, `handling_cost`, `delivery_days`, `stock_quantity`, `moq`, `source_url`, and `captured_at`. Product identity attributes (`brand`, `model`, `size`, `color`, `pack_quantity`, `condition`) are also supported for conservative matching. After a catalogue match is selected, available quote fields for that supplier product are copied into the first supplier-offer form slot for review; the product title is copied into the combined profitability form and the interface scrolls to the quote inputs. Missing fields remain blank/default and must be completed or verified by the user. Catalogue rows remain user-imported evidence; this does not create a supplier API connection or verify quote freshness.

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


## Supplier connector readiness endpoint (22 November 2026)

GET `/api/v1/supplier-connectors` reports integration readiness for Zambeel, Tejaraa and Wave Byte. It returns provider markets, integration path, required environment-variable names, missing variable names, and manual fallback options. It never returns secret values and never claims a live connection merely because credentials are present.

Supplier access research checked against official provider pages on 22 November 2026:
- Tejaraa's official Help Center confirms live and sandbox Partner API keys can be created in My Stores > Custom API; API access depends on membership, and product spreadsheet exports are plan-limited. The exact authenticated endpoint schema still needs to be obtained from the seller portal before implementation: https://tejaraa.com/help/partner-api.
- My Zambeel exposes a public product catalogue, including a Pakistan catalogue, but no public partner API specification was located in this review. Do not reverse-engineer private endpoints; request approved API/feed access: https://products.myzambeel.com/collections/products-for-pakistan.
- Wave Byte's official Shopify listing advertises a 7-day trial followed by USD 5/month through Shopify billing. Its public product materials describe catalogue/inventory sync through the Shopify app, not a general-purpose public API. Dropshipping is advertised for UAE, Saudi Arabia and Oman; other GCC markets are described for 3PL/fulfilment. Keep it optional and do not make it a dependency of the free core: https://apps.shopify.com/wavebyte and https://wavebyteglobal.com/services.
- Tejaraa's order guide says its free plan has a 5-piece minimum per product, paid memberships remove the minimum, courier prices are shown live and include 15% VAT, and typical delivery is 3–5 days after handoff. The comparison workflow must account for quantity/MOQ and delivery cost rather than comparing catalogue item price alone: https://tejaraa.com/help/placing-an-order.
- Wave Byte market metadata separates dropshipping coverage (UAE, Saudi Arabia, Oman) from wider 3PL/fulfilment coverage (UAE, Saudi Arabia, Oman, Qatar, Kuwait, Bahrain); do not imply dropshipping is currently offered in all six markets: https://wavebyteglobal.com/services.

Current readiness rules:
- Zambeel: expects deployment secrets `ZAMBEEL_API_BASE_URL` and `ZAMBEEL_API_TOKEN`; approved API/feed access and its schema still need to be obtained from the provider.
- Tejaraa: expects `TEJARAA_API_BASE_URL` and `TEJARAA_API_KEY`; the provider documents live/sandbox Partner API keys and plan-limited catalog exports, but this repository does not yet implement a provider-specific request until the official endpoint/auth schema and credentials are confirmed.
- Wave Byte: remains an optional official Shopify-app/approved-feed route; do not require its paid app for the free core product finder.

A status of `configured_not_verified` means only that required environment variables exist. `connection_verified` and `live_catalog_fetch_enabled` remain false until an authenticated provider request and response validation are implemented. Manual product URL review and CSV import remain the fallback. Never paste supplier secrets into GitHub source files, frontend code, or chat; add approved credentials only as deployment secrets.

Tests in `tests/test_supplier_connectors.py` cover missing/configured readiness, no secret disclosure, and manual fallback behavior.



## Batch product trend check API (22 November 2026)

POST `/api/v1/product-discovery/trend-check` accepts one supported country code and 1–50 unique product names. It fetches the public Google Trends RSS feed once, then checks each product name against the same country feed using Unicode token overlap (including Urdu and mixed Urdu-English names). Each product receives its own match list and an explicit `verified_product_demand: false` marker. This reduces repeated upstream requests when screening a shortlist, but does not create product-specific search volume, sales evidence or forecasts. No match does not mean no demand.

## Product discovery ranking API (22 November 2026)

POST `/api/v1/product-discovery/rank` ranks 1–50 candidate products for a supported country using the existing transparent signal weights (demand 30%, competition advantage 20%, margin 25%, shipping 10%, trend 15%). Each candidate includes a unique ID, product name, country, matching currency, optional city/category, five 1–10 signal ratings, and optional evidence entries with type, source name, URL and capture timestamp.

The response sorts candidates by weighted score and then reports evidence-link coverage and timestamp freshness. Evidence confidence labels describe coverage only; they do not mean demand or sales have been verified. All source entries remain marked as submitted and not independently verified. The API deliberately returns no sales forecast and does not create sales counts, supplier prices, stock, or competitor numbers. City is recorded as context only; this endpoint does not provide city-level market data.

Example request:

```json
{
  "candidates": [{
    "candidate_id": "lamp-1",
    "product_name": "Rechargeable LED Lamp",
    "country": "PK",
    "city": "Lahore",
    "category": "Home",
    "currency": "PKR",
    "signals": {"demand": 7, "competition": 6, "margin": 8, "shipping": 8, "trend": 6},
    "evidence": [{
      "evidence_type": "marketplace_listing",
      "source_name": "Daraz",
      "source_url": "https://www.daraz.pk/",
      "captured_at": "2026-11-22T08:00:00Z"
    }]
  }]
}
```


## Shortlist to profitability workflow (22 November 2026)

Each product returned by the bilingual batch country trend check now has a "Compare suppliers & profit" action. Selecting it copies only that product name into the shared product-name field, carries over the planned selling price only if the supplier comparison field is still blank, and scrolls to the supplier quote workflow. The user must still enter current supplier costs, shipping and handling, then enter observed marketplace listings (or import verified CSV observations) before building the combined report. This handoff does not fetch supplier prices or marketplace listings and does not change the batch trend result into verified demand.

## Product discovery ranking frontend (22 November 2026)

The bilingual browser UI now includes a Product Opportunity Ranking panel connected to the Cloudflare API at `POST /api/v1/product-discovery/rank`. The user selects a country/city in the existing market filters, enters a product name, rates five signals from 1–10, and may attach one source URL and source name. The UI displays the weighted score, evidence-coverage label and evidence count.

The panel does not invent products, sales counts, forecasts or marketplace data. A submitted URL is user-provided and not independently verified. The score is an estimate based on the ratings entered by the user. The browser code is included in the existing JavaScript syntax-check workflow; the worker API synchronization test explicitly checks the discovery route.
