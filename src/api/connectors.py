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
        "public_catalog": "https://products.myzambeel.com/",
        "official_access_info": "Public product catalogue is browseable; no public partner API specification was located during the 22 November 2026 review. Request approved API/feed access from Zambeel before building an adapter.",
        "documentation_url": "https://products.myzambeel.com/collections/products-for-pakistan",
        "manual_fallback": "Product URL review or supplier CSV import",
        "access_note": "Public country catalogues are visible, but this project has not verified an approved API/feed specification or credentials.",
    },
    {
        "id": "tejaraa",
        "name": "Tejaraa",
        "countries": ["AE", "SA"],
        "integration_type": "partner_api_or_catalog_export",
        "required_environment": ["TEJARAA_API_BASE_URL", "TEJARAA_API_KEY"],
        "public_catalog": "https://tejaraa.com/",
        "official_access_info": "Tejaraa documents live and sandbox Partner API keys under My Stores > Custom API. API access is membership-dependent; product spreadsheet exports are plan-limited. Obtain the authenticated endpoint schema and approved account access before implementing requests.",
        "documentation_url": "https://tejaraa.com/help/partner-api",
        "manual_fallback": "Seller-portal product-list spreadsheet export",
        "access_note": "Partner API live/sandbox keys and plan-limited catalog exports are advertised; endpoint schema and credentials must be obtained before requests are implemented.",
    },
    {
        "id": "ksa-drop",
        "name": "KSA Drop",
        "countries": ["SA", "AE"],
        "integration_type": "approved_partner_feed",
        "required_environment": [],
        "public_catalog": "https://ksadrop.com/",
        "manual_fallback": "Seller portal export or supplier quote CSV",
        "access_note": "Seller onboarding is advertised; no public API specification or project credentials have been verified.",
    },
    {
        "id": "wave-byte",
        "name": "Wave Byte",
        "countries": ["AE", "SA", "OM", "QA", "KW", "BH"],
        "integration_type": "official_shopify_app_or_approved_feed",
        "required_environment": [],
        "public_catalog": "https://wavebyte.ae/",
        "official_access_info": "Official Shopify app advertises a 7-day free trial followed by USD 5/month through Shopify billing. Public materials describe catalog and inventory sync through the app, not a general-purpose public API. Dropshipping is advertised in UAE, Saudi Arabia and Oman; other GCC markets are described for 3PL/fulfilment.",
        "documentation_url": "https://apps.shopify.com/wavebyte",
        "manual_fallback": "Supplier quote CSV import",
        "access_note": "Official Shopify app is optional and may require a paid plan; no general-purpose API credentials are configured.",
    },
    {
        "id": "atsum-ksa",
        "name": "ATSUM KSA",
        "countries": ["SA"],
        "integration_type": "approved_partner_api",
        "required_environment": [],
        "public_catalog": "https://www.myatsum.com/en",
        "manual_fallback": "Supplier quote CSV import",
        "access_note": "Custom API and commerce-platform integrations are advertised; partner specification and credentials must be requested.",
    },
    {
        "id": "hhc-dropshipping",
        "name": "HHC Dropshipping",
        "countries": ["PK"],
        "integration_type": "approved_catalog_export",
        "required_environment": [],
        "public_catalog": "https://hhcdropshipping.com/",
        "manual_fallback": "Supplier quote CSV import",
        "access_note": "Pakistan supplier lead; dropshipping terms and an authorized catalog export route require confirmation.",
    },
    {
        "id": "directstock",
        "name": "DirectStock",
        "countries": ["PK"],
        "integration_type": "approved_catalog_export",
        "required_environment": [],
        "public_catalog": "https://directstock.com.pk/products",
        "manual_fallback": "Product URL review or supplier quote CSV",
        "access_note": "Public wholesale listings are available; item-level dropshipping eligibility and API access are not verified.",
    },
    {
        "id": "souq-b2b",
        "name": "SouqB2B UAE",
        "countries": ["AE"],
        "integration_type": "approved_catalog_export",
        "required_environment": [],
        "public_catalog": "https://souqb2b.ae/en",
        "manual_fallback": "Supplier quote CSV import",
        "access_note": "Public wholesale/RFQ storefront; single-order dropshipping and API access require supplier confirmation.",
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
