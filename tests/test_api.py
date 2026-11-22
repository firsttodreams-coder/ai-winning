from fastapi.testclient import TestClient

import api.main as api_module
from api.main import app, parse_google_trends_rss

client = TestClient(app)






def test_unified_profitability_requires_product_identity_confirmation():
    payload = {
        "product_name": "USB Blender", "country": "PK", "currency": "PKR",
        "planned_selling_price": 5000,
        "offers": [{"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 1800}],
        "listings": [{"marketplace": "Daraz", "price": 4500}],
    }
    rejected = client.post("/api/v1/product-profitability/compare", json=payload)
    assert rejected.status_code == 422
    payload["product_identity_confirmed"] = True
    accepted = client.post("/api/v1/product-profitability/compare", json=payload)
    assert accepted.status_code == 200
    identity = accepted.json()["product_identity_review"]
    assert identity["status"] == "user_confirmed"
    assert identity["verification_method"] == "manual_checkbox"
    assert identity["automated_catalog_match_performed"] is False
    assert identity["review_required"] is True

def test_unified_profitability_ranks_stock_shortfalls_below_fulfillable_suppliers():
    response = client.post("/api/v1/product-profitability/compare", json={
        "product_name": "USB Blender",
        "country": "PK",
        "currency": "PKR",
        "planned_selling_price": 5000,
        "product_identity_confirmed": True,
        "offers": [
            {
                "supplier_id": "supplier-low-stock",
                "supplier_name": "Low stock supplier",
                "product_cost": 1000,
                "moq": 10,
                "stock_quantity": 4,
            },
            {
                "supplier_id": "supplier-ready",
                "supplier_name": "Ready supplier",
                "product_cost": 1500,
                "moq": 5,
                "stock_quantity": 20,
            },
            {
                "supplier_id": "supplier-unknown",
                "supplier_name": "Unknown stock supplier",
                "product_cost": 900,
            },
        ],
        "listings": [{"marketplace": "Daraz", "price": 4500}],
    })
    assert response.status_code == 200
    result = response.json()
    ranked = result["supplier_comparisons"]
    assert ranked[0]["supplier_id"] == "supplier-ready"
    assert ranked[0]["stock_status"] == "available"
    assert ranked[1]["supplier_id"] == "supplier-unknown"
    assert ranked[0]["moq_fulfillable"] is True
    assert ranked[0]["supplier_rank"] == 1
    low_stock = next(row for row in ranked if row["supplier_id"] == "supplier-low-stock")
    assert low_stock["stock_status"] == "insufficient_for_moq"
    assert low_stock["moq_fulfillable"] is False
    assert low_stock["supplier_rank"] == 3
    unknown = next(row for row in ranked if row["supplier_id"] == "supplier-unknown")
    assert unknown["stock_status"] == "unknown"
    assert unknown["moq_fulfillable"] is None
    assert result["best_supplier_by_planned_profit"] == "supplier-ready"
    assert "Unknown stock is not treated as verified availability" in result["supplier_ranking_note"]


def test_catalog_match_suggests_similar_titles_and_marks_review_required():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [
            {"product_id": "s1", "title": "Portable USB Rechargeable Blender"},
            {"product_id": "s2", "title": "LED Motion Sensor Night Light"}
        ],
        "marketplace_products": [
            {"product_id": "m1", "title": "USB Portable Rechargeable Blender"},
            {"product_id": "m2", "title": "Ceramic Coffee Mug"}
        ],
        "minimum_similarity": 0.4
    })
    assert response.status_code == 200
    result = response.json()
    assert result["match_count"] == 1
    assert result["matches"][0]["supplier_product"]["product_id"] == "s1"
    assert result["matches"][0]["marketplace_product"]["product_id"] == "m1"
    assert result["matches"][0]["review_required"] is True
    assert "s2" in result["unmatched_supplier_product_ids"]
    assert "m2" in result["unmatched_marketplace_product_ids"]


def test_catalog_match_preserves_supplier_and_marketplace_comparison_fields():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{
            "product_id": "s-price", "title": "USB desk fan",
            "supplier_id": "supplier-a", "supplier_name": "Supplier A",
            "product_cost": 900, "shipping_cost": 100, "handling_cost": 20,
            "delivery_days": 3, "stock_quantity": 30, "moq": 2,
            "source_url": "https://example.com/supplier",
        }],
        "marketplace_products": [{
            "product_id": "m-price", "title": "USB desk fan",
            "marketplace_price": 2200, "marketplace_shipping_cost": 150,
            "marketplace_listing_url": "https://example.com/listing",
            "marketplace_captured_at": "2026-11-22T08:00:00Z",
        }],
        "minimum_similarity": 0.5,
    })
    assert response.status_code == 200
    match = response.json()["matches"][0]
    assert match["supplier_product"]["product_cost"] == 900
    assert match["supplier_product"]["stock_quantity"] == 30
    assert match["supplier_product"]["moq"] == 2
    assert match["marketplace_product"]["marketplace_price"] == 2200
    assert match["marketplace_product"]["marketplace_shipping_cost"] == 150
    assert match["marketplace_product"]["marketplace_listing_url"] == "https://example.com/listing"


def test_catalog_match_rejects_empty_catalog_and_invalid_threshold():
    empty = client.post("/api/v1/catalog/match", json={
        "supplier_products": [],
        "marketplace_products": [{"product_id": "m1", "title": "Coffee Mug"}]
    })
    invalid = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "Coffee Mug"}],
        "marketplace_products": [{"product_id": "m1", "title": "Coffee Mug"}],
        "minimum_similarity": 1.5
    })
    assert empty.status_code == 422
    assert invalid.status_code == 422


def test_catalog_match_uses_one_to_one_assignment():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "USB desk fan"}],
        "marketplace_products": [
            {"product_id": "m1", "title": "USB desk fan"},
            {"product_id": "m2", "title": "USB desk fan"}
        ],
        "minimum_similarity": 0.5
    })
    assert response.status_code == 200
    assert response.json()["match_count"] == 1

def test_catalog_match_rejects_different_skus_even_when_titles_match():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "USB Rechargeable Blender 500ml", "sku": "SUP-500"}],
        "marketplace_products": [{"product_id": "m1", "title": "USB Rechargeable Blender 500ml", "sku": "MKT-500"}],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    result = response.json()
    assert result["match_count"] == 0
    assert result["excluded_sku_conflict_pairs"] == 1


def test_catalog_match_rejects_missing_numeric_variant_detail():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "iPhone 15 protective case"}],
        "marketplace_products": [{"product_id": "m1", "title": "iPhone protective case"}],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    result = response.json()
    assert result["match_count"] == 0
    assert result["excluded_variant_ambiguity_pairs"] == 1


def test_catalog_match_allows_matching_numeric_variant_when_fingerprints_agree():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "iPhone 15 protective case"}],
        "marketplace_products": [{"product_id": "m1", "title": "Protective case for iPhone 15"}],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    assert response.json()["match_count"] == 1


def test_catalog_match_rejects_conflicting_structured_attributes():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "Wireless earbuds", "brand": "Acme", "model": "X2", "color": "Black", "pack_quantity": 1, "condition": "new"}],
        "marketplace_products": [{"product_id": "m1", "title": "Wireless earbuds", "brand": "Other", "model": "X2", "color": "White", "pack_quantity": 2, "condition": "new"}],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    assert response.json()["match_count"] == 0
    assert response.json()["excluded_attribute_conflict_pairs"] == 1


def test_catalog_match_accepts_matching_structured_attributes():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "Wireless earbuds", "brand": "Acme", "model": "X2", "size": "Regular", "color": "Black", "pack_quantity": 1, "condition": "New"}],
        "marketplace_products": [{"product_id": "m1", "title": "Acme X2 wireless earbuds", "brand": "ACME", "model": "x2", "size": "regular", "color": "black", "pack_quantity": 1, "condition": "new"}],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    assert response.json()["match_count"] == 1


def test_catalog_match_allows_missing_attributes_but_requires_review():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "Wireless earbuds", "brand": "Acme"}],
        "marketplace_products": [{"product_id": "m1", "title": "Wireless earbuds"}],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    assert response.json()["match_count"] == 1
    assert response.json()["matches"][0]["review_required"] is True


def test_catalog_match_rejects_invalid_pack_quantity():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "Coffee filters", "pack_quantity": 0}],
        "marketplace_products": [{"product_id": "m1", "title": "Coffee filters"}]
    })
    assert response.status_code == 422


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



def test_trend_freshness_labels_timestamp_age_without_claiming_demand():
    fixed_now = api_module.datetime(2026, 11, 22, 12, 0, tzinfo=api_module.timezone.utc)
    fresh = api_module._trend_freshness("2026-11-22T00:00:00+00:00", fixed_now)
    aging = api_module._trend_freshness("2026-11-19T00:00:00+00:00", fixed_now)
    stale = api_module._trend_freshness("2026-11-10T00:00:00+00:00", fixed_now)
    unknown = api_module._trend_freshness(None, fixed_now)
    future = api_module._trend_freshness("2026-11-23T00:00:00+00:00", fixed_now)
    assert fresh["trend_freshness"] == "fresh"
    assert aging["trend_freshness"] == "aging"
    assert stale["trend_freshness"] == "stale"
    assert unknown["trend_freshness"] == "unknown"
    assert future["trend_freshness"] == "future_timestamp"


def test_product_trend_match_includes_freshness_and_prefers_fresher_matches():
    trends = [
        {"title": "portable blender deals", "started": "2026-11-10T08:00:00+00:00"},
        {"title": "portable blender offers", "started": "2026-11-22T08:00:00+00:00"},
    ]
    result = api_module.match_product_to_trends("Portable Blender", trends, now=api_module.datetime(2026, 11, 22, 12, 0, tzinfo=api_module.timezone.utc))
    assert result[0]["trend_freshness"] == "fresh"
    assert result[1]["trend_freshness"] == "stale"
    assert result[0]["trend_age_hours"] is not None


def test_product_trend_match_uses_literal_token_overlap_and_excludes_weak_matches():
    trends = [
        {"title": "portable blender deals", "approx_traffic": "2000+", "started": "2026-11-10T08:00:00+00:00", "news": []},
        {"title": "electronics news", "approx_traffic": "1000+", "started": None, "news": []},
        {"title": "football final", "approx_traffic": "5000+", "started": None, "news": []},
    ]
    result = api_module.match_product_to_trends("Portable Blender", trends)
    assert len(result) == 1
    assert result[0]["title"] == "portable blender deals"
    assert result[0]["match_score"] == 100
    assert result[0]["matched_terms"] == ["blender", "portable"]
    assert result[0]["relevance"] == "strong"


def test_product_trend_match_supports_urdu_and_mixed_script_titles():
    trends = [
        {"title": "پورٹیبل بلینڈر کی قیمت", "approx_traffic": "500+", "started": None, "news": []},
        {"title": "portable blender deals", "approx_traffic": "2000+", "started": None, "news": []},
        {"title": "فٹبال میچ", "approx_traffic": "1000+", "started": None, "news": []},
    ]
    result = api_module.match_product_to_trends("پورٹیبل بلینڈر", trends)
    assert len(result) == 1
    assert result[0]["title"] == "پورٹیبل بلینڈر کی قیمت"
    assert result[0]["match_score"] == 100
    assert result[0]["matched_terms"] == ["بلینڈر", "پورٹیبل"]


def test_product_trend_match_handles_mixed_urdu_and_english_tokens():
    result = api_module.match_product_to_trends(
        "portable بلینڈر",
        [{"title": "portable بلینڈر قیمت", "approx_traffic": "100+", "started": None, "news": []}],
    )
    assert len(result) == 1
    assert result[0]["match_score"] == 100


def test_product_trend_match_returns_partial_for_half_the_product_terms():
    result = api_module.match_product_to_trends(
        "wireless portable",
        [{"title": "portable home goods", "approx_traffic": "200+", "started": None, "news": []}],
    )
    assert len(result) == 1
    assert result[0]["match_score"] == 50
    assert result[0]["relevance"] == "partial"


def test_product_trend_match_endpoint_returns_country_source_and_limitations(monkeypatch):
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
    response = client.get("/api/v1/trends/match?country=PK&product_name=portable%20blender")
    assert response.status_code == 200
    payload = response.json()
    assert payload["match_count"] == 1
    assert payload["matches"][0]["match_score"] == 100
    assert "does not prove" in payload["data_note"]


def test_product_trend_match_endpoint_validates_product_name():
    response = client.get("/api/v1/trends/match?country=PK&product_name=x")
    assert response.status_code == 422


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
        "returns_allowance": 5,
        "offers": [
            {"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 90, "shipping_cost": 20, "source_url": "https://example.com/quote", "captured_at": "2026-11-13T10:00:00Z"},
            {"supplier_id": "tejaraa", "supplier_name": "Tejaraa", "product_cost": 80, "shipping_cost": 15, "handling_cost": 2, "delivery_days": 4, "stock_quantity": 8, "moq": 1}
        ]
    })
    assert response.status_code == 200
    result = response.json()
    assert result["offers"][0]["supplier_id"] == "tejaraa"
    assert result["offers"][0]["landed_cost"] == 97
    assert result["offers"][0]["estimated_profit"] == 78
    assert result["offers"][0]["returns_allowance"] == 5
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
    assert result["planned_price_vs_market_average_percent"] == 16.88
    assert result["planned_price_position"] == "above_average"
    assert result["listings"][0]["observed_sold_count"] is None
    assert result["listings"][0]["evidence_status"] == "user_supplied_or_imported_not_live_verified"
    grouped = result["marketplace_prices"]["by_marketplace"]
    assert [row["marketplace"] for row in grouped] == ["Amazon.sa", "Noon", "Other"]
    assert grouped[0]["listing_count"] == 1
    assert grouped[0]["average_delivered_price"] == 159
    assert grouped[2]["observed_sold_count_samples"] == 1


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


def test_supplier_offer_comparison_rejects_currency_that_does_not_match_country():
    response = client.post("/api/v1/supplier-offers/compare", json={
        "country": "SA", "currency": "AED", "selling_price": 100,
        "offers": [{"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 30}]
    })
    assert response.status_code == 422
    assert "Currency for SA must be SAR" in response.text


def test_supplier_offer_comparison_rejects_known_supplier_outside_its_market():
    response = client.post("/api/v1/supplier-offers/compare", json={
        "country": "SA", "currency": "SAR", "selling_price": 100,
        "offers": [{"supplier_id": "directstock", "supplier_name": "DirectStock", "product_cost": 30}]
    })
    assert response.status_code == 422
    assert "Supplier directstock is not listed for market SA" in response.text


def test_supplier_offer_comparison_allows_custom_supplier_id():
    response = client.post("/api/v1/supplier-offers/compare", json={
        "country": "SA", "currency": "SAR", "selling_price": 100,
        "offers": [{"supplier_id": "my-local-supplier", "supplier_name": "My Local Supplier", "product_cost": 30}]
    })
    assert response.status_code == 200
    assert response.json()["offers"][0]["supplier_id"] == "my-local-supplier"


def test_marketplace_price_comparison_rejects_currency_that_does_not_match_country():
    response = client.post("/api/v1/marketplace-prices/compare", json={
        "product_name": "Phone stand", "country": "PK", "currency": "SAR",
        "planned_selling_price": 1000, "supplier_cost": 300,
        "listings": [{"marketplace": "Daraz", "price": 850}]
    })
    assert response.status_code == 422
    assert "Currency for PK must be PKR" in response.text



def test_catalog_match_rejects_conflicting_numeric_variants():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [{"product_id": "s1", "title": "iPhone 13 protective case"}],
        "marketplace_products": [{"product_id": "m1", "title": "iPhone 14 protective case"}],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    result = response.json()
    assert result["match_count"] == 0
    assert result["unmatched_supplier_product_ids"] == ["s1"]
    assert result["unmatched_marketplace_product_ids"] == ["m1"]


def test_catalog_match_prioritizes_exact_sku_and_explains_confidence():
    response = client.post("/api/v1/catalog/match", json={
        "supplier_products": [
            {"product_id": "s1", "title": "Portable Blender 500ml", "sku": "BLEND-500"},
            {"product_id": "s2", "title": "Portable Blender 600ml", "sku": "BLEND-600"}
        ],
        "marketplace_products": [
            {"product_id": "m1", "title": "Mini blender", "sku": "blend-500"}
        ],
        "minimum_similarity": 0.1
    })
    assert response.status_code == 200
    result = response.json()
    assert result["matches"][0]["supplier_product"]["product_id"] == "s1"
    assert result["matches"][0]["similarity"] == 1.0
    assert result["matches"][0]["confidence"] == "high"
    assert result["matches"][0]["match_reason"] == "exact_sku"
    assert result["matches"][0]["review_required"] is True



def test_unified_profitability_comparison_joins_market_and_supplier_costs():
    response = client.post("/api/v1/product-profitability/compare", json={
        "product_name": "Portable blender", "country": "PK", "currency": "PKR",
        "planned_selling_price": 1500, "product_identity_confirmed": True, "platform_fee_percent": 10,
        "marketing_cost": 50, "returns_allowance": 25,
        "offers": [
            {"supplier_id": "zambeel", "supplier_name": "Zambeel",
             "product_cost": 500, "shipping_cost": 100, "handling_cost": 20,
             "moq": 3, "delivery_days": 4, "stock_quantity": 20},
            {"supplier_id": "custom", "supplier_name": "Custom supplier",
             "product_cost": 700, "shipping_cost": 50, "moq": 1}
        ],
        "listings": [
            {"marketplace": "Daraz", "price": 1400, "shipping_cost": 100},
            {"marketplace": "Marketplace B", "price": 1600}
        ]
    })
    assert response.status_code == 200
    result = response.json()
    assert result["marketplace"]["average_delivered_price"] == 1550
    marketplace_profit = {
        item["marketplace"]: item
        for item in result["supplier_comparisons"][0]["marketplace_profitability"]
    }
    assert marketplace_profit["Daraz"]["listing_count"] == 1
    assert marketplace_profit["Daraz"]["average_delivered_price"] == 1500
    assert marketplace_profit["Daraz"]["estimated_profit_at_average_price"] == 655
    assert marketplace_profit["Daraz"]["estimated_margin_at_average_price_percent"] == 43.67
    assert marketplace_profit["Marketplace B"]["average_delivered_price"] == 1600
    assert marketplace_profit["Marketplace B"]["estimated_profit_at_average_price"] == 745
    first = result["supplier_comparisons"][0]
    assert first["supplier_id"] == "zambeel"
    assert first["landed_cost_per_unit"] == 620
    assert first["planned_profit_per_order"] == 655
    assert first["planned_roi_percent"] == 105.65
    assert first["estimated_moq_investment"] == 1860
    assert first["market_average_profit_per_order"] == 700
    assert result["best_supplier_by_planned_profit"] == "zambeel"
    assert result["marketplace"]["listings"][0]["evidence_status"] == "user_supplied_or_imported_not_live_verified"
    assert result["recommendation_status"] == "positive_estimated_profit_available"


def test_unified_profitability_does_not_recommend_a_supplier_when_all_estimated_profits_are_non_positive():
    response = client.post("/api/v1/product-profitability/compare", json={
        "product_name": "Portable blender", "country": "PK", "currency": "PKR",
        "planned_selling_price": 500, "product_identity_confirmed": True,
        "offers": [
            {"supplier_id": "zambeel", "supplier_name": "Zambeel",
             "product_cost": 500, "shipping_cost": 100, "handling_cost": 20},
            {"supplier_id": "custom", "supplier_name": "Custom supplier",
             "product_cost": 700, "shipping_cost": 50}
        ],
        "listings": [
            {"marketplace": "Daraz", "price": 1400, "shipping_cost": 100},
            {"marketplace": "Marketplace B", "price": 1600}
        ]
    })
    assert response.status_code == 200
    result = response.json()
    assert all(item["planned_profit_per_order"] <= 0 for item in result["supplier_comparisons"])
    assert result["best_supplier_by_planned_profit"] is None
    assert result["recommendation_status"] == "no_positive_estimated_profit"


def test_unified_profitability_comparison_rejects_wrong_currency_and_supplier_market():
    wrong_currency = client.post("/api/v1/product-profitability/compare", json={
        "product_name": "Phone stand", "country": "SA", "currency": "AED",
        "planned_selling_price": 100, "offers": [
            {"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 20}
        ],
        "listings": [{"marketplace": "Noon", "price": 90}]
    })
    wrong_supplier = client.post("/api/v1/product-profitability/compare", json={
        "product_name": "Phone stand", "country": "SA", "currency": "SAR",
        "planned_selling_price": 100, "offers": [
            {"supplier_id": "directstock", "supplier_name": "DirectStock", "product_cost": 20}
        ],
        "listings": [{"marketplace": "Noon", "price": 90}]
    })
    assert wrong_currency.status_code == 422
    assert wrong_supplier.status_code == 422


def test_unified_profitability_comparison_requires_supplier_and_market_data():
    response = client.post("/api/v1/product-profitability/compare", json={
        "product_name": "Desk fan", "country": "PK", "currency": "PKR",
        "planned_selling_price": 1000,
        "offers": [{"supplier_id": "custom", "supplier_name": "Custom supplier", "product_cost": 300}],
        "listings": []
    })
    assert response.status_code == 422


def test_unified_profitability_preserves_catalog_match_as_unverified_context():
    payload = {
        "product_name": "Portable USB Blender", "country": "PK", "currency": "PKR",
        "planned_selling_price": 5000, "product_identity_confirmed": True,
        "offers": [{"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 1800}],
        "listings": [{"marketplace": "Daraz", "price": 4500}],
        "catalog_match_context": {
            "supplier_product_id": "s-10", "supplier_title": "Portable USB Blender",
            "marketplace_product_id": "m-20", "marketplace_title": "USB Blender Portable",
            "similarity": 0.87
        }
    }
    response = client.post("/api/v1/product-profitability/compare", json=payload)
    assert response.status_code == 200
    context = response.json()["catalog_match_context"]
    assert context["status"] == "catalog_suggestion_selected"
    assert context["review_required"] is True
    assert context["automated_identity_verified"] is False
    assert context["similarity"] == 0.87


def test_unified_profitability_rejects_malformed_catalog_match_context_with_422():
    payload = {
        "product_name": "USB Blender", "country": "PK", "currency": "PKR",
        "planned_selling_price": 5000, "product_identity_confirmed": True,
        "offers": [{"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 1800}],
        "listings": [{"marketplace": "Daraz", "price": 4500}],
        "catalog_match_context": {
            "supplier_product_id": "s-1", "supplier_title": "USB Blender",
            "marketplace_product_id": "m-1", "marketplace_title": "USB Blender",
            "similarity": "not-a-number"
        }
    }
    malformed_similarity = client.post("/api/v1/product-profitability/compare", json=payload)
    assert malformed_similarity.status_code == 422

    del payload["catalog_match_context"]["marketplace_title"]
    incomplete_context = client.post("/api/v1/product-profitability/compare", json=payload)
    assert incomplete_context.status_code == 422


def test_unified_profitability_rejects_invalid_catalog_match_similarity():
    payload = {
        "product_name": "USB Blender", "country": "PK", "currency": "PKR",
        "planned_selling_price": 5000, "product_identity_confirmed": True,
        "offers": [{"supplier_id": "zambeel", "supplier_name": "Zambeel", "product_cost": 1800}],
        "listings": [{"marketplace": "Daraz", "price": 4500}],
        "catalog_match_context": {
            "supplier_product_id": "s-1", "supplier_title": "USB Blender",
            "marketplace_product_id": "m-1", "marketplace_title": "USB Blender",
            "similarity": 1.2
        }
    }
    response = client.post("/api/v1/product-profitability/compare", json=payload)
    assert response.status_code == 422



def test_product_discovery_ranks_candidates_and_reports_evidence_coverage():
    response = client.post("/api/v1/product-discovery/rank", json={
        "candidates": [
            {
                "candidate_id": "lamp-1",
                "product_name": "Rechargeable LED Lamp",
                "country": "PK",
                "city": "Lahore",
                "currency": "PKR",
                "signals": {"demand": 8, "competition": 6, "margin": 7, "shipping": 8, "trend": 7},
                "evidence": [
                    {"evidence_type": "marketplace_listing", "source_name": "Daraz", "source_url": "https://www.daraz.pk/item/1", "captured_at": "2026-11-22T03:00:00Z"},
                    {"evidence_type": "supplier_quote", "source_name": "Supplier", "source_url": "https://supplier.example/item/1", "captured_at": "2026-11-22T03:30:00Z"},
                    {"evidence_type": "search_interest", "source_name": "Trends", "source_url": "https://trends.google.com/trends/explore"}
                ]
            },
            {
                "candidate_id": "mug-1",
                "product_name": "Ceramic Mug",
                "country": "PK",
                "currency": "PKR",
                "signals": {"demand": 3, "competition": 4, "margin": 5, "shipping": 6, "trend": 2}
            }
        ]
    })
    assert response.status_code == 200
    result = response.json()
    assert result["count"] == 2
    assert result["ranked_candidates"][0]["candidate_id"] == "lamp-1"
    assert result["ranked_candidates"][0]["evidence_confidence"] == "higher_evidence_coverage"
    assert result["ranked_candidates"][0]["verified_sales_data"] is False
    assert result["ranked_candidates"][0]["sales_forecast"] is None
    assert result["ranked_candidates"][1]["evidence_confidence"] == "insufficient_evidence"


def test_product_discovery_rejects_currency_mismatch_and_duplicate_ids():
    mismatch = client.post("/api/v1/product-discovery/rank", json={
        "candidates": [{
            "candidate_id": "x", "product_name": "Test Product", "country": "PK", "currency": "AED",
            "signals": {"demand": 5, "competition": 5, "margin": 5, "shipping": 5, "trend": 5}
        }]
    })
    duplicate = client.post("/api/v1/product-discovery/rank", json={
        "candidates": [
            {"candidate_id": "x", "product_name": "Test Product A", "country": "PK", "currency": "PKR", "signals": {"demand": 5, "competition": 5, "margin": 5, "shipping": 5, "trend": 5}},
            {"candidate_id": "x", "product_name": "Test Product B", "country": "PK", "currency": "PKR", "signals": {"demand": 6, "competition": 5, "margin": 5, "shipping": 5, "trend": 5}}
        ]
    })
    assert mismatch.status_code == 422
    assert duplicate.status_code == 422



def test_batch_product_trend_check_fetches_one_country_feed_for_multiple_products(monkeypatch):
    xml = """<?xml version="1.0"?>
    <rss xmlns:ht="https://trends.google.com/trending/rss">
      <channel>
        <item><title>portable blender deals</title><ht:approx_traffic>2000+</ht:approx_traffic></item>
        <item><title>wireless headphones</title><ht:approx_traffic>1000+</ht:approx_traffic></item>
      </channel>
    </rss>"""

    class FakeResponse:
        text = xml
        def raise_for_status(self):
            return None

    class FakeClient:
        calls = 0
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, url):
            self.calls += 1
            assert url == "https://trends.google.com/trending/rss?geo=PK"
            return FakeResponse()

    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeClient)
    response = client.post("/api/v1/product-discovery/trend-check", json={
        "country": "PK",
        "product_names": ["portable blender", "wireless headphones", "ceramic mug"]
    })
    assert response.status_code == 200
    result = response.json()
    assert result["count"] == 3
    assert result["results"][0]["match_count"] == 1
    assert result["results"][1]["match_count"] == 1
    assert result["results"][2]["match_count"] == 0
    assert all(item["verified_product_demand"] is False for item in result["results"])
    assert "do not prove" in result["data_note"]


def test_batch_product_trend_check_supports_urdu_product_names(monkeypatch):
    xml = """<?xml version="1.0"?>
    <rss><channel><item><title>پورٹیبل بلینڈر کی قیمت</title></item></channel></rss>"""

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
            return FakeResponse()

    monkeypatch.setattr(api_module.httpx, "AsyncClient", FakeClient)
    response = client.post("/api/v1/product-discovery/trend-check", json={
        "country": "PK", "product_names": ["پورٹیبل بلینڈر"]
    })
    assert response.status_code == 200
    assert response.json()["results"][0]["match_count"] == 1


def test_batch_product_trend_check_validates_names_and_country():
    duplicate = client.post("/api/v1/product-discovery/trend-check", json={
        "country": "PK", "product_names": ["USB Blender", "usb blender"]
    })
    invalid_country = client.post("/api/v1/product-discovery/trend-check", json={
        "country": "XX", "product_names": ["USB Blender"]
    })
    assert duplicate.status_code == 422
    assert invalid_country.status_code == 422


def test_evidence_and_listing_urls_require_absolute_http_or_https():
    valid_evidence = api_module.OpportunityEvidence(
        evidence_type="listing",
        source_name="Marketplace",
        source_url=" https://example.com/product/1 ",
    )
    assert valid_evidence.source_url == "https://example.com/product/1"

    invalid_urls = [
        "javascript:alert(1)",
        "ftp://example.com/file",
        "https:///missing-host",
        "https://user:password@example.com/private",
        "not-a-url",
    ]
    for url in invalid_urls:
        try:
            api_module.OpportunityEvidence(
                evidence_type="listing",
                source_name="Marketplace",
                source_url=url,
            )
        except Exception:
            pass
        else:
            raise AssertionError(f"Unsafe evidence URL was accepted: {url}")

    for model, field in [
        (api_module.SupplierOffer, "source_url"),
        (api_module.MarketplaceListing, "listing_url"),
    ]:
        kwargs = (
            {"supplier_id": "test", "supplier_name": "Test", "product_cost": 10}
            if field == "source_url"
            else {"marketplace": "Test", "price": 10}
        )
        kwargs[field] = "javascript:alert(1)"
        try:
            model(**kwargs)
        except Exception:
            pass
        else:
            raise AssertionError(f"Unsafe {field} was accepted")


def test_supplier_connector_readiness_is_explicit_and_never_exposes_secrets():
    from api.connectors import build_connector_status

    fake_env = {
        "ZAMBEEL_API_BASE_URL": "https://api.example.test",
        "ZAMBEEL_API_TOKEN": "do-not-return-this-token",
        "TEJARAA_API_BASE_URL": "https://partner.example.test",
        "TEJARAA_API_KEY": "do-not-return-this-key",
    }
    status = build_connector_status(fake_env)
    assert status["count"] == len(status["connectors"])
    by_id = {item["id"]: item for item in status["connectors"]}

    assert by_id["zambeel"]["status"] == "configured_not_verified"
    assert by_id["zambeel"]["connection_verified"] is False
    assert by_id["zambeel"]["live_catalog_fetch_enabled"] is False
    assert by_id["tejaraa"]["status"] == "configured_not_verified"
    assert "PK" in by_id["zambeel"]["countries"]
    assert "SA" in by_id["tejaraa"]["countries"]
    assert "do-not-return-this-token" not in str(status)
    assert "do-not-return-this-key" not in str(status)


def test_supplier_connector_status_endpoint_lists_manual_and_partner_routes():
    response = client.get("/api/v1/supplier-connectors")
    assert response.status_code == 200
    result = response.json()
    by_id = {item["id"]: item for item in result["connectors"]}

    assert {"zambeel", "tejaraa", "ksa-drop", "wave-byte", "atsum-ksa"} <= set(by_id)
    assert by_id["zambeel"]["status"] == "credentials_missing"
    assert by_id["ksa-drop"]["status"] == "manual_or_partner_setup_required"
    assert by_id["wave-byte"]["live_catalog_fetch_enabled"] is False
    assert result["data_note"].startswith("Readiness only.")



def test_unified_profitability_calculates_each_marketplace_profit_for_each_supplier():
    response = client.post("/api/v1/product-profitability/compare", json={
        "product_name": "USB Blender",
        "country": "PK",
        "currency": "PKR",
        "planned_selling_price": 3200,
        "platform_fee_percent": 10,
        "marketing_cost": 100,
        "returns_allowance": 50,
        "product_identity_confirmed": True,
        "offers": [{
            "supplier_id": "supplier-a",
            "supplier_name": "Supplier A",
            "product_cost": 1000,
            "shipping_cost": 200,
            "handling_cost": 100,
        }],
        "listings": [
            {"marketplace": "Daraz", "price": 1800},
            {"marketplace": "Daraz", "price": 2200},
            {"marketplace": "Noon", "price": 3000},
        ],
    })
    assert response.status_code == 200
    result = response.json()
    supplier = result["supplier_comparisons"][0]
    by_market = {row["marketplace"]: row for row in supplier["marketplace_profitability"]}
    assert by_market["Daraz"]["listing_count"] == 2
    assert by_market["Daraz"]["average_delivered_price"] == 2000
    assert by_market["Daraz"]["lowest_delivered_price"] == 1800
    assert by_market["Daraz"]["estimated_profit_at_average_price"] == 350
    assert by_market["Daraz"]["estimated_profit_at_lowest_price"] == 170
    assert by_market["Noon"]["estimated_profit_at_average_price"] == 1250
    assert by_market["Noon"]["estimated_margin_at_average_price_percent"] == 41.67
