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
- Basic offline cache for the app shell through a service worker
- MIT license
- Initial FastAPI backend with health, scoring-model, product-scoring, and product-economics endpoints
- Cloudflare Python Workers entry point and deployment configuration
- Automated API tests and documented local setup

## Important data note

The current product list and sample scores are static demonstration data. They are not live marketplace statistics, validated sales figures, or AI-generated recommendations. The opportunity calculator is a transparent weighted estimate based only on ratings entered by the user.

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
2. Add a real data-source layer using permitted public/free sources and source timestamps.
3. Add evidence-backed product metrics and country-aware currency/shipping filters.
4. Add optional AI-assisted analysis with citations and a no-key/local mode where feasible.
5. Add saved searches, comparison, export, and further integration tests.

## License

This project is licensed under the MIT License; see `LICENSE`.
