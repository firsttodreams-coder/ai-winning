# Deploy the API for free

The frontend is hosted on GitHub Pages. The FastAPI backend can be deployed separately using the included `render.yaml` Blueprint.

## Render setup

1. Sign in to Render and connect the GitHub account that owns this repository.
2. Open the Render dashboard and choose **New → Blueprint**.
3. Select `firsttodreams-coder/ai-winning` and approve the Blueprint.
4. Confirm the service plan is **Free**, then create the service.
5. After deployment, open the service URL and check `/health`. It should return a JSON status of `ok`.

The API URL will be assigned by Render and is not known until the service is created. Do not put private keys or passwords in this repository.

## Free-tier limitations

Render's free web services sleep after 15 minutes without traffic and may take about a minute to wake up. Free instances have an ephemeral filesystem and are intended for testing and hobby projects, not production guarantees. See [Render's free instance documentation](https://render.com/docs/free).

## API endpoints

- `GET /health`
- `GET /api/v1/scoring-model`
- `POST /api/v1/score`
- `POST /api/v1/product-economics`

All calculations currently use user-provided inputs. Live marketplace research and external AI inference are not yet connected.
