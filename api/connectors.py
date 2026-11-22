"""Supplier connector readiness registry.

This module deliberately reports configuration only. It does not call supplier
APIs, scrape catalogues, or treat the presence of credentials as a verified
connection. Provider-specific adapters must be implemented only against
approved documentation and credentials.
"""
import os
from collections.abc import Mapping

from fastapi import APIRouter

router = APIRouter()

CONNECTOR_DEFINITIONS = (
    {
        "id": "zambeel",
        "name": "My Zambeel",
        "countries": ["PK", "AE", "SA"],
        "integration_type": "authorized_api_or_catalog_feed",
        "required_environment": ["ZAMBEEL_API_BASE_URL", "ZAMBEEL_API_TOKEN"],
        "public_catalog": "https://products.myzameel.com/",
        "manual_fallback": "Product URL review or supplier CSV import",
        "access_note": (
            "Public country catalogues are visible, but this project has not "
            "verified an approved API/feed specification or credentials."
        ),
    },
    {
        "id": "tejaraa",
        "name": "Tejaraa",
        "countries": ["AE", "SA"],
        "integration_type": "partner_api_or_catalog_export",
        "required_environment": ["TEJARAA_API_BASE_URL", "TEJARAA_API_KEY"],
        "public_catalog": "https://tejaraa.com/",
        "manual_fallback": "Seller-portal product-list spreadsheet export",
        "access_note": (
            "Tejaraa documents Partner API live/sandbox keys and plan-limited "
            "catalog exports; endpoint schema and credentials must be obtained "
            "from the seller portal before requests are implemented."
        ),
    },
    {
        "id": "wave-byte",
        "name": "Wave Byte",
        "countries": ["AE", "SA", "OM", "QA", "KW", "BH"],
        "integration_type": "official_shopify_app_or_approved_feed",
        "required_environment": [],
        "public_catalog": "https://wavebyte.ae/",
        "manual_fallback": "Supplier quote CSV import",
        "access_note": (
            "Official Shopify app is optional and may require a paid plan; "
            "no general-purpose API credentials are configured here."
        ),
    },
)


def build_connector_status(env: Mapping[str, str] | None = None) -> dict:
    """Return safe readiness metadata without exposing secret values."""
    values = os.environ if env is None else env
    connectors = []
    for definition in CONNECTOR_DEFINITIONS:
        required = definition["required_environment"]
        missing = [name for name in required if not values.get(name, "").strip()]
        if not required:
            status = "manual_or_partner_setup_required"
        elif missing:
            status = "credentials_missing"
        else:
            status = "configured_not_verified"

        connectors.append({
            **definition,
            "required_environment": list(required),
            "missing_environment": missing,
            "status": status,
            "connection_verified": False,
            "live_catalog_fetch_enabled": False,
            "secret_values_exposed": False,
        })

    return {
        "count": len(connectors),
        "connectors": connectors,
        "data_note": (
            "Readiness only. No supplier API request was made. Configured "
            "credentials do not prove authentication or live catalogue access. "
            "Manual CSV/URL review remains available."
        ),
    }


@router.get("/api/v1/supplier-connectors")
def supplier_connector_status():
    """Expose connector readiness without revealing environment secret values."""
    return build_connector_status()
