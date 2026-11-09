from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_score_endpoint_returns_weighted_score():
    response = client.post(
        "/api/v1/score",
        json={"demand": 10, "competition": 10, "margin": 10, "shipping": 10, "trend": 10},
    )
    assert response.status_code == 200
    assert response.json()["score"] == 100
    assert response.json()["rating"] == "strong"


def test_score_rejects_values_outside_scale():
    response = client.post(
        "/api/v1/score",
        json={"demand": 11, "competition": 5, "margin": 5, "shipping": 5, "trend": 5},
    )
    assert response.status_code == 422
