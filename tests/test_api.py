from fastapi.testclient import TestClient

import api.main as api_module
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



def test_trends_endpoint_returns_country_feed_and_source_metadata(monkeypatch):
    xml = """<?xml version="1.0"?>
    <rss xmlns:ht="https://trends.google.com/trending/rss">
      <channel><item>
        <title>portable blender</title>
        <pubDate>Mon, 10 Nov 2026 08:00:00 +0000</pubDate>
        <ht:approx_traffic>2000+</ht:approx_traffic>
      </item></channel>
    </rss>"""

    class FakeResponse:
        text = xml

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            assert url == "https://trends.google.com/trending/rss?geo=PK"
            return FakeResponse()

    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeClient)
    response = client.get("/api/v1/trends?country=PK")

    assert response.status_code == 200
    result = response.json()
    assert result["country"] == "PK"
    assert result["country_name"] == "Pakistan"
    assert result["count"] == 1
    assert result["trends"][0]["title"] == "portable blender"
    assert result["trends"][0]["approx_traffic"] == "2000+"
    assert result["fetched_at"]
    assert "not product-specific" in result["data_note"]


def test_trends_endpoint_reports_temporary_upstream_failure(monkeypatch):
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            import httpx
            raise httpx.ConnectError("upstream unavailable")

    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeClient)
    response = client.get("/api/v1/trends?country=PK")

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


def test_supplier_directory_keeps_multiple_gcc_suppliers_and_exposes_connection_status():
    response = client.get("/api/v1/suppliers?country=SA")
    assert response.status_code == 200
    result = response.json()
    ids = {supplier["id"] for supplier in result["suppliers"]}
    assert {"zambeel", "tejaraa", "ksa-drop", "wave-byte", "atsum-ksa"} <= ids
    assert all(supplier["directory_status"] == "listed_not_connected" for supplier in result["suppliers"])
    assert "no supplier account is connected" in result["data_note"].lower()


def test_supplier_directory_supports_gcc_fulfillment_markets():
    response = client.get("/api/v1/suppliers?country=BH")
    assert response.status_code == 200
    assert response.json()["country_name"] == "Bahrain"
    wave_byte = next(item for item in response.json()["suppliers"] if item["id"] == "wave-byte")
    assert "fulfillment" in wave_byte["modes"]
    assert "dropshipping" not in wave_byte["modes"]


def test_supplier_offer_comparison_sorts_by_estimated_profit_and_keeps_provenance():
    response = client.post("/api/v1/supplier-offers/compare", json={
        "country": "SA",
        "currency": "SAR",
        "selling_price": 200,
        "platform_fee_percent": 5,
        "marketing_cost": 10,
        "offers": [
            {"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 90, "shipping_cost": 20, "source_url": "https://example.com/quote", "captured_at": "2026-11-13T10:00:00Z"},
            {"supplier_id": "tejaraa", "supplier_name": "Tejaraa", "product_cost": 80, "shipping_cost": 15, "handling_cost": 2, "delivery_days": 4, "stock_quantity": 8, "moq": 1}
        ]
    })
    assert response.status_code == 200
    result = response.json()
    assert result["offers"][0]["supplier_id"] == "tejaraa"
    assert result["offers"][0]["landed_cost"] == 97
    assert result["offers"][0]["estimated_profit"] == 83
    assert result["offers"][1]["price_evidence"] == "user_supplied_or_imported_not_live_verified"


def test_supplier_offer_comparison_rejects_empty_offers_and_invalid_market():
    empty = client.post("/api/v1/supplier-offers/compare", json={
        "country": "SA", "currency": "SAR", "selling_price": 100, "offers": []
    })
    invalid = client.get("/api/v1/suppliers?country=XX")
    assert empty.status_code == 422
    assert invalid.status_code == 422


def test_trends_endpoint_accepts_additional_gcc_markets(monkeypatch):
    xml = """<?xml version="1.0"?><rss><channel><item><title>GCC trend</title></item></channel></rss>"""
    class FakeResponse:
        text = xml
        def raise_for_status(self):
            return None
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, url):
            assert url == "https://trends.google.com/trending/rss?geo=OM"
            return FakeResponse()
    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeClient)
    response = client.get("/api/v1/trends?country=OM")
    assert response.status_code == 200
    assert response.json()["country_name"] == "Oman"


def test_marketplace_price_comparison_calculates_delivered_market_prices_and_profit():
    response = client.post("/api/v1/marketplace-prices/compare", json={
        "product_name": "Portable blender",
        "country": "SA",
        "currency": "SAR",
        "planned_selling_price": 180,
        "supplier_cost": 65,
        "supplier_shipping": 15,
        "platform_fee_percent": 5,
        "marketing_cost": 12,
        "returns_allowance": 3,
        "listings": [
            {"marketplace": "Amazon.sa", "price": 149, "shipping_cost": 10, "listing_url": "https://example.com/a", "observed_sold_count": None},
            {"marketplace": "Noon", "price": 159, "shipping_cost": 0, "captured_at": "2026-11-13T10:00:00Z"},
            {"marketplace": "Other", "price": 139, "shipping_cost": 5, "observed_sold_count": 24}
        ]
    })
    assert response.status_code == 200
    result = response.json()
    assert result["marketplace_prices"]["lowest_delivered_price"] == 144
    assert result["marketplace_prices"]["average_delivered_price"] == 154.0
    assert result["marketplace_prices"]["median_delivered_price"] == 159
    assert result["supplier"]["landed_cost"] == 80
    assert result["estimated_profit_per_order"] == 76
    assert result["listings"][0]["observed_sold_count"] is None
    assert result["listings"][0]["evidence_status"] == "user_supplied_or_imported_not_live_verified"


def test_marketplace_price_comparison_rejects_empty_listings_and_invalid_country():
    empty = client.post("/api/v1/marketplace-prices/compare", json={
        "product_name": "Mini blender", "country": "SA", "currency": "SAR",
        "planned_selling_price": 100, "supplier_cost": 30, "listings": []
    })
    invalid = client.post("/api/v1/marketplace-prices/compare", json={
        "product_name": "Mini blender", "country": "XX", "currency": "SAR",
        "planned_selling_price": 100, "supplier_cost": 30,
        "listings": [{"marketplace": "Noon", "price": 90}]
    })
    assert empty.status_code == 422
    assert invalid.status_code == 422


def test_marketplace_price_comparison_keeps_missing_sold_count_unknown():
    response = client.post("/api/v1/marketplace-prices/compare", json={
        "product_name": "Phone stand", "country": "PK", "currency": "PKR",
        "planned_selling_price": 1000, "supplier_cost": 300,
        "listings": [{"marketplace": "Daraz", "price": 850}]
    })
    assert response.status_code == 200
    assert response.json()["listings"][0]["observed_sold_count"] is None


def test_marketplace_price_comparison_accepts_all_frontend_market_countries():
    response = client.post("/api/v1/marketplace-prices/compare", json={
        "product_name": "USB desk fan",
        "country": "US",
        "currency": "USD",
        "planned_selling_price": 25,
        "supplier_cost": 8,
        "listings": [{"marketplace": "Amazon", "price": 22}]
    })
    assert response.status_code == 200
    assert response.json()["country"] == "US"
