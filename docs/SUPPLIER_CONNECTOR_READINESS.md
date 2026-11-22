# Supplier connector readiness (verified 22 November 2026)

This document separates publicly visible catalog evidence from authenticated integration access. A supplier is not "connected" until an authorized request succeeds and the response is validated.

## Current supplier evidence

| Supplier | Markets / service evidence | Public integration evidence | Next integration requirement |
|---|---|---|---|
| My Zambeel | Public country catalogs for Pakistan, UAE, KSA and other GCC markets. Product pages can show country-specific SKU, supplier price, delivery cost, landed cost, suggested selling-price range, dispatch estimate, stock and dispatch origin. | Public product catalog is visible without proving an API entitlement. No public API specification or credentials were verified in this review. | Ask Zambeel support for an approved product-feed/API export and permission to read country-specific price, SKU, stock, dispatch and delivery fields. Until approved, keep manual product URL/CSV import. |
| Tejaraa | Local supplier stock and dropshipping in KSA and UAE; product prices and commissions are shown separately. | Official Help Center describes a Partner API with live and sandbox keys, plus downloadable product-list export subject to plan limits. Store/channel syncing depends on plan and connected channel. | Create/verify seller account, request Partner API access and docs, check plan/export limits, and obtain sandbox credentials before adapter work. |
| KSA Drop | Saudi Arabia and UAE dropshipping; seller portal follows onboarding. | Official onboarding describes seller account and store integration; no public API specification verified. | Complete seller onboarding and request product-feed/API documentation and permitted rate limits. |
| Wave Byte | Dropshipping in UAE, Saudi Arabia and Oman; fulfillment in Qatar, Kuwait and Bahrain. | Official Shopify app advertises catalog import, product/variant/image/stock sync and automatic order forwarding. Public Shopify app page states a 7-day trial then US$5/month. No separate public API spec verified. | Keep as optional integration. Confirm seller account, app plan and whether an authorized partner feed/API is available. Do not make the core product-finder depend on the paid Shopify app. |
| ATSUM KSA | Saudi fulfillment/dropshipping operations. | Official site advertises custom API integration and Shopify, Salla, YouCan, Zid and WooCommerce connections. | Request API specification, partner credentials, catalog scope and stock/price update events. |
| HHC Dropshipping | Pakistan supplier lead. | Public supplier site; no public API specification verified. | Confirm dropshipping terms, current catalog export and authorized integration route. |
| DirectStock | Pakistan wholesale product listings. | Public product listings; no dropshipping/API commitment verified. | Confirm item-level dropship eligibility and request a permitted catalog export. |
| SouqB2B UAE | UAE wholesale/RFQ lead. | Public supplier/RFQ storefront; no public API specification verified. | Confirm single-order dropshipping and request a product/quote export. |

## Integration order

1. **Zambeel first:** request approved seller API/product-feed access for Pakistan, UAE and Saudi Arabia. Its public catalog already exposes useful country-level product evidence, but this does not authorize automated extraction.
2. **Tejaraa second:** obtain Partner API sandbox/live keys and understand product export limits and membership conditions.
3. **Wave Byte third / optional:** use the official Shopify app only where a seller account and paid plan are acceptable; separately request authorized feed/API access for this platform.
4. **ATSUM and KSA Drop:** obtain seller/partner credentials and specifications before building adapters.
5. Keep HHC, DirectStock and SouqB2B as manual/import suppliers until they confirm a supported integration route.

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
- Keep the core AI Product Finder free and open-source; any third-party supplier subscription must be disclosed as an optional external cost, not hidden as a platform requirement.

## Official references

- My Zambeel country catalog: https://products.myzambeel.com/
- My Zambeel Pakistan catalog: https://products.myzambeel.com/collections/products-for-pakistan
- My Zambeel product-level cost/stock/dispatch example: https://products.myzambeel.com/products/5-in-1-wireless-power-bank
- Tejaraa Help Center / Partner API and product export guides: https://tejaraa.com/help
- Tejaraa Partner API seller workflow: https://selling.tejaraa.com/selling/dropshipping
- KSA Drop onboarding: https://ksadrop.com/pages/how-it-works
- Wave Byte Shopify app and pricing: https://shopify.wavebyte.ae/
- Wave Byte platform and market coverage: https://wavebyte.ae/
- ATSUM KSA integrations: https://www.myatsum.com/en

Last checked: 2026-11-22. Public marketing/help pages establish advertised capabilities only; they do not prove that this project has account access, API credentials or a functioning connector.
