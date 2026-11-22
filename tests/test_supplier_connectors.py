from fastapi.testclient import TestClient

from api.connectors import build_connector_status
from api.main import app

client = TestClient(app)

EXPECTED_CONNECTORS = {
    "zambeel", "tejaraa", "ksa-drop", "wave-byte",
    "atsum-ksa", "hhc-dropshipping", "directstock", "souq-b2b",
}


def test_connector_status_lists_all_supplier_leads_without_claiming_live_connections():
    response = client.get("/api/v1/supplier-connectors")
    assert response.status_code == 200
    result = response.json()
    assert result["count"] == 8
    by_id = {item["id"]: item for item in result["connectors"]}
    assert set(by_id) == EXPECTED_CONNECTORS
    assert by_id["zambeel"]["countries"] == ["PK", "AE", "SA"]
    assert by_id["tejaraa"]["countries"] == ["AE", "SA"]
    assert by_id["ksa-drop"]["countries"] == ["SA", "AE"]
    assert by_id["wave-byte"]["countries"] == ["AE", "SA", "OM", "QA", "KW", "BH"]
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


def test_connectors_without_public_credentials_keep_manual_fallbacks():
    result = build_connector_status({})
    by_id = {item["id"]: item for item in result["connectors"]}
    for supplier_id in EXPECTED_CONNECTORS - {"zambeel", "tejaraa"}:
        assert by_id[supplier_id]["status"] == "manual_or_partner_setup_required"
        assert by_id[supplier_id]["manual_fallback"]
