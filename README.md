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
- Initial FastAPI backend with health, scoring-model, product-scoring, and product-economics endpoints
- Cloudflare Python Workers entry point and deployment configuration
- Automated API tests and documented local setup

## Important data note

The current product list and sample scores are static demonstration data. The local supplier directory is a curated set of public supplier/marketplace links for Pakistan, UAE and Saudi Arabia, including Zambeel country catalog access. It does not certify a supplier or guarantee every product is dropship-eligible. The price comparison calculator uses prices and sold counts entered from the linked marketplace pages; it does not yet scrape live prices or sales counts automatically. Verify stock, currency, delivery, fees, and returns on the source listing. The market research workspace generates direct search links to third-party sites; it does not scrape those sites, fetch sales volumes, verify supplier offers, or calculate live competition. City is a search hint only; most public trend and marketplace sources are country-level. The personal research workspace evaluates values and evidence entered by the user; saved records remain in that browser's local storage and can be exported as CSV. It does not synchronize across devices. They are not live marketplace statistics, validated sales figures, or AI-generated recommendations. The opportunity calculator is a transparent weighted estimate based only on ratings entered by the user.

## Run

Open `index.html` in a modern browser, or publish the repository with GitHub Pages. Use the language button in the top-right area to switch between English and Urdu; the selection is saved in the browser. For installation, open the deployed HTTPS site in a supported mobile browser and use its browser menu's install/add-to-home-screen option. The service worker requires HTTPS or localhost.


## GitHub Pages setup

The GitHub Pages deployment workflow publishes the frontend automatically when changes are pushed to `main`.

## Backend API

A first FastAPI scoring service is available in `api/main.py`.

- `GET /health` — service health check
- `GET /api/v1/scoring-model` — transparent scoring weights
- `POST /api/v1/score` — score five user-provided signals from 1 to 10
- `POST /api/v1/product-economics` — estimate per-unit profit, margin, ROI, and break-even price

Run it locally with `pip install -r requirements.txt` followed by `uvicorn api.main:app --reload`. See `docs/DEVELOPMENT.md` for details. The API does not yet fetch live marketplace data or generate AI recommendations. Cloudflare deployment instructions are in `docs/CLOUDFLARE_DEPLOY.md`.

## Planned development

1. Connect the frontend calculator to the API after selecting a backend host.
2. Add a real data-source layer using permitted public/free sources and source timestamps, beginning with reliable country-level trend feeds and explicit rate-limit handling.
3. Add evidence-backed product metrics and country-aware currency/shipping filters, including verified supplier pricing, MOQ, shipping and seller counts where source access permits.
4. Add optional AI-assisted analysis with citations and a no-key/local mode where feasible.
5. Add saved searches, comparison, export, and further integration tests.

## License

This project is licensed under the MIT License; see `LICENSE`.
