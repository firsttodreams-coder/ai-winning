# Deploy the API to Cloudflare Workers

The API uses the official Cloudflare Python Workers integration for FastAPI.

## One-time dashboard setup

1. Open **Workers & Pages** in the Cloudflare dashboard.
2. Choose **Create application** and then **Import a repository**.
3. Connect GitHub and select `firsttodreams-coder/ai-winning`.
4. Use the repository root as the project root.
5. Set the build/deploy command to `uv run pywrangler deploy` if Cloudflare asks for a command. The repository's `wrangler.jsonc` identifies the Worker entry point.
6. Save and deploy. Keep the account on the Free plan; do not add a paid plan or payment method for this project.

Cloudflare should provide a `workers.dev` URL after a successful deployment.

## Verify

Open these endpoints, replacing `WORKER_URL` with the URL Cloudflare provides:

- `https://WORKER_URL/health`
- `https://WORKER_URL/api/v1/scoring-model`

The API also supports `POST /api/v1/score` and `POST /api/v1/product-economics`. Supplier and marketplace comparison endpoints accept user-entered or imported evidence only; no supplier or marketplace account is connected by default.

## Free-plan note

Cloudflare's Workers Free plan currently documents a daily request allowance and execution limits. Check the current limits before production use. A successful deployment does not mean that live marketplace data or AI-generated product research has been connected; those remain separate development tasks.

## Project files

- `src/main.py`: Cloudflare ASGI entry point
- `api/main.py`: shared FastAPI application
- `pyproject.toml`: Python Workers dependencies
- `wrangler.jsonc`: Worker name, entry point, and Python compatibility flag

Official references:
- https://developers.cloudflare.com/workers/languages/python/packages/fastapi/
- https://developers.cloudflare.com/workers/get-started/dashboard/
- https://developers.cloudflare.com/workers/platform/limits/
