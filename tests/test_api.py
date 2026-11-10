from fastapi.testclient import TestClient

from api.main import app, parse_google_trends_rss

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


def test_frontend_origin_is_allowed_by_cors():
    response = client.options(
        "/api/v1/score",
        headers={
            "Origin": "https://firsttodreams-coder.github.io",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://firsttodreams-coder.github.io"


def test_google_trends_rss_parser_preserves_source_metrics_and_news():
    xml = """<?xml version="1.0"?>
    <rss xmlns:ht="https://trends.google.com/trending/rss">
      <channel><item>
        <title>portable blender</title>
        <pubDate>Mon, 10 Nov 2026 08:00:00 +0000</pubDate>
        <ht:approx_traffic>2000+</ht:approx_traffic>
        <ht:news_item>
          <ht:news_item_title>Example headline</ht:news_item_title>
          <ht:news_item_url>https://example.com/story</ht:news_item_url>
          <ht:news_item_source>Example News</ht:news_item_source>
        </ht:news_item>
      </item></channel>
    </rss>"""
    result = parse_google_trends_rss(xml)
    assert len(result) == 1
    assert result[0]["title"] == "portable blender"
    assert result[0]["approx_traffic"] == "2000+"
    assert result[0]["started"] == "2026-11-10T08:00:00+00:00"
    assert result[0]["news"][0]["source"] == "Example News"


def test_trends_endpoint_rejects_unsupported_country():
    response = client.get("/api/v1/trends?country=XX")
    assert response.status_code == 422
