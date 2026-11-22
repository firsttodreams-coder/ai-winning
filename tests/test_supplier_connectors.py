from fastapi.testclient import TestClient

from api.connectors import build_connector_status
from api.main import app

client = TestClient(app)


def test_connector_status_does_not_claim_unverified_connections():
    response = client.get("/api/v1/supplier-connectors")
    assert response.status_code == 200
    result = response.json()
    assert result["count"] == 3
    by_id = {item["id"]: item for item in result["connectors"]}
    assert set(by_id) == {"zambeel", "tejaraa", "wave-byte"}
    assert by_id["zambeel"]["status"] in {"credentials_missing", "configured_not_verified"}
    assert by_id["tejaraa"]["status"] in {"credentials_missing", "configured_not_verified"}
    assert all(item["connection_verified"] is False for item in by_id.values())
    assert all(item["live_catalog_fetch_enabled"] is False for item in by_id.values())


def test_connector_status_reports_missing_environment_names_without_secret_values():
    result = build_connector_status({
        "ZAMBEEL_API_BASE_URL": "https://api.example.test",
        "ZAMBEEL_API_TOKEN": "",
        "TEJARAA_API_BASE_URL": "https://sandbox.example.test",
        "TEJARAA_API_KEY": "do-not-return-this-secret",
    })
    by_id = {item["id"]: item for item in result["connectors"]}
    assert by_id["zambeel"]["status"] == "credentials_missing"
    assert by_id["zambeel"]["missing_environment"] == ["ZAMBEEL_API_TOKEN"]
    assert by_id["tejaraa"]["status"] == "configured_not_verified"
    serialized = str(result)
    assert "do-not-return-this-secret" not in serialized
    assert "secret_values_exposed" in serialized


def test_connector_status_keeps_manual_fallback_for_unconfigured_provider():
    result = build_connector_status({})
    wave_byte = next(item for item in result["connectors"] if item["id"] == "wave-byte")
    assert wave_byte["status"] == "manual_or_partner_setup_required"
    assert wave_byte["manual_fallback"]
