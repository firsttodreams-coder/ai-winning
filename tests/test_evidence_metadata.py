from datetime import datetime, timedelta, timezone

from api.main import _evidence_metadata


def test_missing_timestamp_is_unknown():
    result = _evidence_metadata("https://www.example.com/item", None)
    assert result["source_domain"] == "www.example.com"
    assert result["freshness_status"] == "unknown"
    assert result["evidence_age_hours"] is None


def test_recent_timestamp_is_fresh():
    captured = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    result = _evidence_metadata("https://Noon.com/product/1", captured)
    assert result["source_domain"] == "noon.com"
    assert result["freshness_status"] == "fresh"
    assert 1.9 <= result["evidence_age_hours"] <= 2.1


def test_old_timestamp_is_stale():
    captured = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    result = _evidence_metadata("http://supplier.example/quote", captured)
    assert result["freshness_status"] == "stale"


def test_invalid_timestamp_is_flagged():
    result = _evidence_metadata("https://example.com", "not-a-date")
    assert result["freshness_status"] == "invalid_timestamp"
    assert result["evidence_age_hours"] is None


def test_future_timestamp_is_flagged():
    captured = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    result = _evidence_metadata("https://example.com", captured)
    assert result["freshness_status"] == "future_timestamp"


def test_non_http_source_does_not_get_a_domain():
    result = _evidence_metadata("javascript:alert(1)", None)
    assert result["source_domain"] is None
