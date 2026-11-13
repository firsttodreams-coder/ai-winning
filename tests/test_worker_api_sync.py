from pathlib import Path


def test_cloudflare_worker_uses_the_same_api_as_the_tested_application():
    root = Path(__file__).resolve().parents[1]
    application_api = (root / "api" / "main.py").read_text(encoding="utf-8")
    worker_api = (root / "src" / "api" / "main.py").read_text(encoding="utf-8")

    assert worker_api == application_api
    assert '@app.get("/api/v1/trends")' in worker_api
    assert '@app.get("/api/v1/suppliers")' in worker_api
    assert '@app.post("/api/v1/supplier-offers/compare")' in worker_api
