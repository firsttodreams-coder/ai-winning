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


def test_product_economics_calculates_profit_and_margin():
    response = client.post(
        "/api/v1/product-economics",
        json={
            "currency": "PKR",
            "selling_price": 2000,
            "product_cost": 900,
            "shipping_cost": 150,
            "platform_fee_percent": 5,
            "marketing_cost": 100,
            "returns_allowance": 50,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["platform_fee"] == 100
    assert result["total_cost"] == 1300
    assert result["profit_per_unit"] == 700
    assert result["profit_margin_percent"] == 35


def test_product_economics_rejects_invalid_currency_and_price():
    response = client.post(
        "/api/v1/product-economics",
        json={"currency": "US", "selling_price": 0, "product_cost": 10, "shipping_cost": 1},
    )
    assert response.status_code == 422
