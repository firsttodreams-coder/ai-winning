# AI Winning Product Finder

A free, open-source-friendly, responsive starter for researching product ideas across selectable markets.

## Current status

This repository currently contains a first browser-based prototype in `index.html`.

Included:
- Responsive mobile and desktop layout
- Country and city selectors
- Category and estimated-budget filters
- Clearly labelled sample product ideas and demo scores
- Installable Progressive Web App (PWA) manifest and app icon
- English and Urdu interface with an in-app language switch, translated product names, and RTL Urdu layout
- Right-to-left Urdu and left-to-right English layouts
- Country-specific city lists for the supported markets
- Transparent manual opportunity scoring using demand, competition, margin, shipping, and trend ratings
- Personal product research workspace: evaluate and save product candidates with your own evidence URL, market, cost inputs, weighted score, and estimated per-unit profit
- Research records saved locally in the current browser, with CSV export and delete controls
- Country-aware free research shortcuts for Google Trends, Daraz, Amazon regional stores, eBay sold listings, and web search; links open external sites and do not claim to import live metrics
- Market research workspace that builds category/country search links and product-specific supplier searches for Alibaba, AliExpress, CJdropshipping, 1688, Daraz, Amazon and eBay
- Curated local wholesale and dropshipping supplier directory focused on Pakistan, UAE and Saudi Arabia, with supplier website links, service-model labels, and English/Urdu notes; listings are clearly presented as research leads, not endorsements or verified live offers
- Zambeel catalog links for Pakistan, UAE and Saudi Arabia, plus a product-level supplier-versus-market price calculator for landed cost, competitor low/average prices, planned selling price, platform fees, advertising cost, margin, break-even, and entered/observed sales count
- Product-specific demand and competition research shortcuts, with explicit disclosure that city-level sales, live competition counts, supplier prices, and sales volumes are not yet automatically verified
- Basic offline cache for the app shell through a service worker
- MIT license
- FastAPI backend with health, scoring-model, country-level Google Trends RSS, product-scoring, and product-economics endpoints
- Cloudflare Python Workers entry point and deployment configuration
- Automated API tests and documented local setup

## Important data note

The current product list and sample scores are static demonstration data. The local supplier directory is a curated set of public supplier/marketplace links for Pakistan, UAE and Saudi Arabia, including Zambeel country catalog access. It does not certify a supplier or guarantee every product is dropship-eligible. The price comparison calculator uses prices and sold counts entered from the linked marketplace pages; it does not yet scrape live prices or sales counts automatically. Verify stock, currency, delivery, fees, and returns on the source listing. The market research workspace generates direct search links to third-party sites; it does not scrape those sites, fetch sales volumes, verify supplier offers, or calculate live competition. City is a search hint only; most public trend and marketplace sources are country-level. The personal research workspace evaluates values and evidence entered by the user; saved records remain in that browser's local storage and can be exported as CSV. It does not synchronize across devices. They are not live marketplace statistics, validated sales figures, or AI-generated recommendations. The opportunity calculator is a transparent weighted estimate based only on ratings entered by the user.

## Run

Open `index.html` in a modern browser, or publish the repository with GitHub Pages. Use the language button in the top-right area to switch between English and Urdu; the selection is saved in the browser. For installation, open the deployed HTTPS site in a supported mobile browser and use its browser menu's install/add-to-home-screen option. The service worker requires HTTPS or localhost.


## GitHub Pages setup

The GitHub Pages deployment workflow publishes the frontend automatically when changes are pushed to `main`.

Supplier connector requirements and public evidence are tracked in [docs/SUPPLIER_CONNECTOR_READINESS.md](docs/SUPPLIER_CONNECTOR_READINESS.md).

## Backend API

A first FastAPI scoring service is available in `api/main.py`.

- `GET /health` — service health check
- `GET /api/v1/scoring-model` — transparent scoring weights
- `POST /api/v1/score` — score five user-provided signals from 1 to 10
- `POST /api/v1/product-economics` — estimate per-unit profit, margin, ROI, and break-even price
- `GET /api/v1/suppliers?country=SA` — country-filtered supplier directory with honest API/catalog access status for Pakistan and GCC markets
- `POST /api/v1/supplier-offers/compare` — rank user-entered/imported supplier quotes by landed cost and estimated profit, preserving source URL and capture time
- `POST /api/v1/marketplace-prices/compare` — compare observed Daraz/Amazon/Noon/eBay listing prices (including entered shipping) against supplier cost and planned profit; preserves source links and unknown sales counts

Run it locally with `pip install -r requirements.txt` followed by `uvicorn api.main:app --reload`. See `docs/DEVELOPMENT.md` for details. The API now reads Google's public country-level Trending Now RSS feed for 13 supported markets (PK, US, GB, AE, SA, IN, CA, AU, DE, OM, QA, KW, BH). This is broad search-trend evidence only; it is not product-specific demand, marketplace sales, competitor counts, or verified buying intent. The API does not yet fetch live marketplace prices or generate AI recommendations. Cloudflare deployment instructions are in `docs/CLOUDFLARE_DEPLOY.md`.

## Next development milestones

Completed:
- Multi-supplier directory API for Pakistan and GCC markets; includes Zambeel plus Tejaraa, KSA Drop, Wave Byte, ATSUM KSA and wholesale sources, with service coverage and integration-readiness metadata.
- Supplier offer comparison API that ranks submitted quotes by landed cost and estimated profit, retaining source and capture-time provenance.
- Supplier quote CSV template and bilingual frontend importer for up to three offers, with supplier/country validation and optional stock, delivery and source URL fields.
- Marketplace listing CSV template and bilingual frontend importer for up to three observed listings, validating prices, shipping, source URLs and optional visible sold counts before populating the existing comparison form.
- Supplier and marketplace comparison responses now include source-domain and evidence-freshness metadata (`fresh`, `aging`, `stale`, `unknown`, or timestamp warnings) when a capture timestamp is supplied. This describes evidence age only; it does not independently verify the source or fetch live prices.
- Added automated unit tests for missing, fresh, stale, invalid, future-dated and non-HTTP evidence metadata.
- Bilingual marketplace price comparison form and API: compares up to three user-observed marketplace listings (including shipping) against supplier landed cost, planned selling price, fees, ads and returns allowance; preserves source URLs and unknown sold counts.
- Bilingual frontend supplier directory connected to the API, with a local directory fallback if the API is unavailable.
- Frontend profit calculator connected to the Cloudflare API.
- Bilingual country-level Google Trends panel connected with source timestamps and evidence limitations.
- Product research scoring connected to the transparent scoring API.
- Supplier-versus-market price comparison calculator, saved research, comparison and CSV export.
- Cloudflare Worker API kept in sync with the tested FastAPI application, with a regression test.

Remaining before production-grade product discovery:
1. Connect approved supplier catalog/API accounts (starting with Zambeel, Tejaraa, KSA Drop and Wave Byte) for verified product prices, MOQ, shipping, stock and destination coverage where public or authorized access permits.
2. Add permitted marketplace evidence adapters for current listing prices and seller/listing data; show source links and retrieval timestamps. The manual/import evidence comparison endpoint is now available as a first step.
3. Build product-specific demand evidence rather than treating broad country trends as proof of product sales.
4. Add optional AI-assisted analysis that cites its evidence and clearly separates estimates from verified facts.
5. Add end-to-end deployment checks, data freshness handling and user testing on mobile and desktop.

No marketplace sales, competitor counts, supplier stock or AI-generated winning-product claims should be displayed as verified unless a source actually provides that evidence.

## License

This project is licensed under the MIT License; see `LICENSE`.
