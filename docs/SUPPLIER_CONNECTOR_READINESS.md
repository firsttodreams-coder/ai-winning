# Supplier connector readiness (verified 13 November 2026)

This document separates publicly verifiable supplier capabilities from credentials or APIs that still require seller-account access. The app must not label a supplier as connected until an authenticated catalog request succeeds.

## Current supplier evidence

| Supplier | Markets / service evidence | Public integration evidence | Next integration requirement |
|---|---|---|---|
| My Zambeel | Pakistan, UAE and Saudi Arabia catalogs; country-specific product availability and dispatch filters | Public catalog pages; Shopify, YouCan and EasyOrders store connection and manual order upload are described | Obtain seller-account/API documentation and permission for product, price, stock, dispatch and destination fields |
| Tejaraa | Local supplier stock and dropshipping in KSA and UAE; no minimum order is advertised | Official seller pages describe an API and store/channel connections; automatic order syncing depends on plan | Request API docs, sandbox/partner credentials, catalog export format, commission and shipping fields |
| KSA Drop | Saudi dropshipping; seller portal access follows registration and first-order onboarding | Official onboarding page describes store integration and portal access; no public API specification verified | Complete seller onboarding and request product-feed/API documentation and permitted rate limits |
| Wave Byte | Dropshipping in UAE, Saudi Arabia and Oman; fulfillment/3PL in Qatar, Kuwait and Bahrain | Official site advertises Shopify catalog import and live inventory sync; Shopify app is available | Use the official Shopify app for a connected Shopify store, or request partner API/feed access for this platform; confirm per-country costs |
| ATSUM KSA | Saudi fulfillment/dropshipping operations | Official site advertises custom API integration and Shopify, Salla, YouCan, Zid and WooCommerce connections | Request API specification, partner credentials, catalog scope and stock/price update events |
| HHC Dropshipping | Pakistan supplier lead | Public supplier site; no public API specification verified | Confirm dropshipping terms, current catalog export and authorized integration route |
| DirectStock | Pakistan wholesale product listings | Public product listings; no dropshipping/API commitment verified | Confirm item-level dropship eligibility and request a permitted catalog export |
| SouqB2B UAE | UAE wholesale/RFQ lead | Public supplier/RFQ storefront; no public API specification verified | Confirm single-order dropshipping and request a product/quote export |

## Integration order

1. **Zambeel first:** request the official seller API/catalog export and field definitions for Pakistan, UAE and Saudi Arabia.
2. **Tejaraa and Wave Byte next:** both have explicit public integration signals; request authorized API/feed access and confirm plan requirements.
3. **ATSUM and KSA Drop:** obtain seller/partner credentials and specifications before building adapters.
4. Keep HHC, DirectStock and SouqB2B as manual/import suppliers until they confirm a supported integration route.

## Minimum normalized product record

Every adapter or CSV import should map to the same fields:

- `supplier_id`, `supplier_product_id`, `product_title`, `product_url`
- `country`, `currency`, `product_cost`, `commission`
- `shipping_cost`, `handling_cost`, `delivery_days`
- `stock_quantity`, `moq`, `dispatch_location`
- `captured_at`, `source_url`, `evidence_status`

Do not merge offers across countries or currencies without an explicit FX conversion and timestamp. A missing stock value stays unknown; it must not be interpreted as zero or available.

## Security and data-quality rules

- Never request or store supplier passwords in the frontend or repository.
- Store API credentials only as deployment secrets after the provider approves access.
- Respect supplier terms, authentication, rate limits and catalog permissions; do not bypass login or access controls.
- Record source URL and retrieval timestamp for each offer.
- Mark imported/manual data as `user_supplied_or_imported_not_live_verified`.
- Mark an adapter as live only after an authenticated request succeeds and its response has been validated.
- Keep failed or stale feeds visible as unavailable/stale; never silently replace them with demo values.

## Official references

- My Zambeel catalog: https://products.myzambeel.com/
- My Zambeel UAE/KSA seller workflow: https://www.myzambeel.com/pages/dropshipping-uae-and-ksa
- Tejaraa Saudi dropshipping: https://tejaraa.com/saudi-dropshipping
- Tejaraa seller API and workflow information: https://selling.tejaraa.com/selling/dropshipping
- KSA Drop onboarding: https://ksadrop.com/pages/how-it-works
- Wave Byte platform and market coverage: https://wavebyte.ae/
- Wave Byte Shopify app: https://shopify.wavebyte.ae/
- ATSUM KSA integrations: https://www.myatsum.com/en

Last checked: 2026-11-13. Public marketing pages establish advertised capabilities only; they do not prove that this project has account access, API credentials or a functioning connector.
