"""Free product-opportunity scoring and public market-signal API.

Scores and economics use user-provided inputs. Google Trends RSS is a broad
country-level discovery signal, not product-specific demand or sales data.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from statistics import median
from difflib import SequenceMatcher
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

app = FastAPI(
    title="AI Winning Product Finder API",
    description="Open API for transparent product scoring and public market signals.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://firsttodreams-coder.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

WEIGHTS = {
    "demand": 0.30,
    "competition": 0.20,
    "margin": 0.25,
    "shipping": 0.10,
    "trend": 0.15,
}

TREND_COUNTRIES = {
    "PK": "Pakistan",
    "US": "United States",
    "GB": "United Kingdom",
    "AE": "United Arab Emirates",
    "SA": "Saudi Arabia",
    "IN": "India",
    "CA": "Canada",
    "AU": "Australia",
    "DE": "Germany",
    "OM": "Oman",
    "QA": "Qatar",
    "KW": "Kuwait",
    "BH": "Bahrain",
}
GOOGLE_TRENDS_NAMESPACE = "{https://trends.google.com/trending/rss}"


# Supplier directory metadata is curated from public provider information.
# "api_access" describes public integration evidence, not an active connection.
SUPPLIERS = [
    {"id": "zambeel", "name": "Zambeel", "countries": ["PK", "AE", "SA"], "modes": ["dropshipping", "wholesale"], "website": "https://myzambeel.com/", "api_access": "account_or_partner_access_required", "catalog_access": "destination-specific catalogue; verify stock and price in account"},
    {"id": "tejaraa", "name": "Tejaraa", "countries": ["AE", "SA"], "modes": ["dropshipping", "wholesale"], "website": "https://tejaraa.com/", "api_access": "api_advertised_contact_for_credentials", "catalog_access": "public storefront; supplier cost and commission shown separately"},
    {"id": "ksa-drop", "name": "KSA Drop", "countries": ["SA", "AE"], "modes": ["dropshipping", "fulfillment"], "website": "https://ksadrop.com/", "api_access": "not_publicly_confirmed", "catalog_access": "seller account or onboarding required"},
    {"id": "wave-byte", "name": "Wave Byte", "countries": ["AE", "SA", "OM", "QA", "KW", "BH"], "modes": ["dropshipping", "fulfillment"], "service_by_country": {"AE": ["dropshipping", "fulfillment"], "SA": ["dropshipping", "fulfillment"], "OM": ["dropshipping", "fulfillment"], "QA": ["fulfillment"], "KW": ["fulfillment"], "BH": ["fulfillment"]}, "website": "https://wavebyte.ae/", "api_access": "store_connector_public_api_not_confirmed", "catalog_access": "Seller account required; dropshipping in UAE, KSA and Oman; fulfillment only in Qatar, Kuwait and Bahrain."},
    {"id": "hhc-dropshipping", "name": "HHC Dropshipping", "countries": ["PK"], "modes": ["dropshipping", "fulfillment"], "website": "https://hhcdropshipping.com/", "api_access": "not_publicly_confirmed", "catalog_access": "supplier account and current terms require confirmation"},
    {"id": "directstock", "name": "DirectStock", "countries": ["PK"], "modes": ["wholesale"], "website": "https://directstock.com.pk/products", "api_access": "not_publicly_confirmed", "catalog_access": "public product listings; dropshipping terms require seller confirmation"},
    {"id": "souq-b2b", "name": "SouqB2B UAE", "countries": ["AE"], "modes": ["wholesale"], "website": "https://souqb2b.ae/en", "api_access": "not_publicly_confirmed", "catalog_access": "supplier/RFQ workflow; single-order dropshipping requires confirmation"},
    {"id": "atsum-ksa", "name": "ATSUM KSA", "countries": ["SA"], "modes": ["dropshipping", "fulfillment", "wholesale"], "website": "https://www.myatsum.com/en", "api_access": "not_publicly_confirmed", "catalog_access": "catalogue availability and item-level dropship eligibility require confirmation"},
]

COUNTRY_NAMES = {"PK": "Pakistan", "AE": "United Arab Emirates", "SA": "Saudi Arabia", "OM": "Oman", "QA": "Qatar", "KW": "Kuwait", "BH": "Bahrain"}
COUNTRY_CURRENCIES = {
    "PK": "PKR", "US": "USD", "GB": "GBP", "AE": "AED", "SA": "SAR",
    "IN": "INR", "CA": "CAD", "AU": "AUD", "DE": "EUR", "OM": "OMR",
    "QA": "QAR", "KW": "KWD", "BH": "BHD",
}


def _validate_market_currency(country: str, currency: str) -> None:
    expected = COUNTRY_CURRENCIES[country]
    if currency != expected:
        raise ValueError(
            f"Currency for {country} must be {expected}; convert the entered prices before comparing."
        )


class OpportunitySignals(BaseModel):
    demand: int = Field(ge=1, le=10, description="Strength of demand evidence")
    competition: int = Field(ge=1, le=10, description="Competitive advantage; 10 means low competition")
    margin: int = Field(ge=1, le=10, description="Potential profit margin")
    shipping: int = Field(ge=1, le=10, description="Ease and affordability of shipping")
    trend: int = Field(ge=1, le=10, description="Strength of the observed trend")



def _evidence_metadata(source_url: str | None, captured_at: str | None) -> dict:
    """Describe provenance and timestamp freshness without claiming verification."""
    source_domain = None
    if source_url:
        try:
            parsed_url = urlsplit(source_url.strip())
            if parsed_url.scheme.lower() in {"http", "https"} and parsed_url.hostname:
                source_domain = parsed_url.hostname.lower()
        except ValueError:
            source_domain = None

    metadata = {
        "source_domain": source_domain,
        "captured_at": captured_at,
        "evidence_age_hours": None,
        "freshness_status": "unknown",
    }
    if not captured_at:
        return metadata

    try:
        parsed_time = datetime.fromisoformat(captured_at.strip().replace("Z", "+00:00"))
        if parsed_time.tzinfo is None:
            parsed_time = parsed_time.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - parsed_time.astimezone(timezone.utc)).total_seconds() / 3600
    except (TypeError, ValueError, OverflowError):
        metadata["freshness_status"] = "invalid_timestamp"
        return metadata

    metadata["evidence_age_hours"] = round(age_hours, 2)
    if age_hours < -0.05:
        metadata["freshness_status"] = "future_timestamp"
    elif age_hours <= 24:
        metadata["freshness_status"] = "fresh"
    elif age_hours <= 168:
        metadata["freshness_status"] = "aging"
    else:
        metadata["freshness_status"] = "stale"
    return metadata


class SupplierOffer(BaseModel):
    supplier_id: str = Field(min_length=2, max_length=60)
    supplier_name: str = Field(min_length=2, max_length=120)
    product_cost: float = Field(ge=0, le=100000000)
    shipping_cost: float = Field(default=0, ge=0, le=100000000)
    handling_cost: float = Field(default=0, ge=0, le=100000000)
    delivery_days: int | None = Field(default=None, ge=0, le=365)
    stock_quantity: int | None = Field(default=None, ge=0)
    moq: int | None = Field(default=None, ge=1)
    source_url: str | None = Field(default=None, max_length=2048)
    captured_at: str | None = Field(default=None, max_length=64)


class SupplierOfferComparison(BaseModel):
    country: str = Field(pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$")
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    selling_price: float = Field(gt=0, le=100000000)
    platform_fee_percent: float = Field(default=0, ge=0, le=100)
    marketing_cost: float = Field(default=0, ge=0, le=100000000)
    returns_allowance: float = Field(default=0, ge=0, le=100000000)
    offers: list[SupplierOffer] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_market_and_currency(self):
        _validate_market_currency(self.country, self.currency)
        known_suppliers = {supplier["id"]: supplier for supplier in SUPPLIERS}
        for offer in self.offers:
            supplier = known_suppliers.get(offer.supplier_id)
            if supplier and self.country not in supplier["countries"]:
                raise ValueError(
                    f"Supplier {offer.supplier_id} is not listed for market {self.country}."
                )
        return self


class MarketplaceListing(BaseModel):
    marketplace: str = Field(min_length=2, max_length=80)
    listing_title: str | None = Field(default=None, max_length=200)
    price: float = Field(gt=0, le=100000000)
    shipping_cost: float = Field(default=0, ge=0, le=100000000)
    listing_url: str | None = Field(default=None, max_length=2048)
    observed_sold_count: int | None = Field(default=None, ge=0)
    captured_at: str | None = Field(default=None, max_length=64)


class MarketplacePriceComparison(BaseModel):
    product_name: str = Field(min_length=2, max_length=160)
    country: str = Field(pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$")
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    planned_selling_price: float = Field(gt=0, le=100000000)
    supplier_cost: float = Field(ge=0, le=100000000)
    supplier_shipping: float = Field(default=0, ge=0, le=100000000)
    platform_fee_percent: float = Field(default=0, ge=0, le=100)
    marketing_cost: float = Field(default=0, ge=0, le=100000000)
    returns_allowance: float = Field(default=0, ge=0, le=100000000)
    listings: list[MarketplaceListing] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def currency_matches_country(self):
        _validate_market_currency(self.country, self.currency)
        return self


class CatalogProduct(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=100)


class ProductMatchRequest(BaseModel):
    supplier_products: list[CatalogProduct] = Field(min_length=1, max_length=50)
    marketplace_products: list[CatalogProduct] = Field(min_length=1, max_length=50)
    minimum_similarity: float = Field(default=0.45, ge=0, le=1)


class ProductEconomics(BaseModel):
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    selling_price: float = Field(gt=0, le=100000000)
    product_cost: float = Field(ge=0, le=100000000)
    shipping_cost: float = Field(ge=0, le=100000000)
    platform_fee_percent: float = Field(default=0, ge=0, le=100)
    marketing_cost: float = Field(default=0, ge=0, le=100000000)
    returns_allowance: float = Field(default=0, ge=0, le=100000000)


def parse_google_trends_rss(xml_text: str) -> list[dict]:
    """Parse Google's public Trending Now RSS feed without inventing metrics."""
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("RSS channel is missing")

    items = []
    for item in channel.findall("item"):
        title = item.findtext("title")
        if not title:
            continue
        published = item.findtext("pubDate")
        try:
            started = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat() if published else None
        except (TypeError, ValueError, OverflowError):
            started = None
        news = []
        for entry in item.findall(f"{GOOGLE_TRENDS_NAMESPACE}news_item"):
            news_title = entry.findtext(f"{GOOGLE_TRENDS_NAMESPACE}news_item_title")
            news_url = entry.findtext(f"{GOOGLE_TRENDS_NAMESPACE}news_item_url")
            news_source = entry.findtext(f"{GOOGLE_TRENDS_NAMESPACE}news_item_source")
            if news_title:
                news.append({"title": news_title, "url": news_url, "source": news_source})
        items.append({
            "title": title,
            "approx_traffic": item.findtext(f"{GOOGLE_TRENDS_NAMESPACE}approx_traffic"),
            "started": started,
            "news": news,
        })
    return items


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-winning-product-finder-api"}


@app.get("/api/v1/scoring-model")
def scoring_model():
    return {
        "version": "0.2.0",
        "scale": {"minimum": 1, "maximum": 10},
        "weights": WEIGHTS,
        "note": "Scores are estimates based only on supplied inputs, not live market evidence.",
    }


@app.get("/api/v1/trends")
async def country_trends(country: str = Query(..., pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$")):
    """Return Google's public top 10 Trending Now RSS entries for a supported country."""
    feed_url = f"https://trends.google.com/trending/rss?geo={country}"
    try:
        async with httpx.AsyncClient(
            timeout=12.0,
            follow_redirects=True,
            headers={"User-Agent": "AI-Winning-Product-Finder/0.2 (+public-trends-reader)"},
        ) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
        trends = parse_google_trends_rss(response.text)
    except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Public Google Trends feed is temporarily unavailable. Please try again later.",
        ) from exc

    return {
        "country": country,
        "country_name": TREND_COUNTRIES[country],
        "source": feed_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(trends),
        "trends": trends,
        "data_note": (
            "These are broad Google Search trends, not product-specific search volume, "
            "marketplace sales, competitor counts, or verified buying demand. "
            "Traffic values are approximate buckets supplied by Google."
        ),
    }



@app.get("/api/v1/suppliers")
def supplier_directory(country: str = Query(..., pattern=r"^(PK|AE|SA|OM|QA|KW|BH)$")):
    """Return curated supplier options and honest integration-readiness metadata."""
    suppliers = []
    for supplier in SUPPLIERS:
        if country not in supplier["countries"]:
            continue
        item = dict(supplier)
        item["market_country"] = country
        item["market_country_name"] = COUNTRY_NAMES[country]
        item["modes"] = item.get("service_by_country", {}).get(country, item["modes"])
        item.pop("service_by_country", None)
        item["directory_status"] = "listed_not_connected"
        suppliers.append(item)
    return {
        "country": country,
        "country_name": COUNTRY_NAMES[country],
        "count": len(suppliers),
        "suppliers": suppliers,
        "data_note": "Directory information only. No supplier account is connected and no live price, stock, delivery promise, or order status is being fetched.",
    }


@app.post("/api/v1/supplier-offers/compare")
def compare_supplier_offers(data: SupplierOfferComparison):
    """Compare supplier offers entered/imported by the user; never invent live quotes."""
    results = []
    for offer in data.offers:
        landed_cost = offer.product_cost + offer.shipping_cost + offer.handling_cost
        platform_fee = data.selling_price * data.platform_fee_percent / 100
        total_cost = landed_cost + platform_fee + data.marketing_cost + data.returns_allowance
        profit = data.selling_price - total_cost
        results.append({
            "supplier_id": offer.supplier_id,
            "supplier_name": offer.supplier_name,
            "currency": data.currency,
            "product_cost": round(offer.product_cost, 2),
            "shipping_cost": round(offer.shipping_cost, 2),
            "handling_cost": round(offer.handling_cost, 2),
            "landed_cost": round(landed_cost, 2),
            "platform_fee": round(platform_fee, 2),
            "marketing_cost": round(data.marketing_cost, 2),
            "returns_allowance": round(data.returns_allowance, 2),
            "estimated_profit": round(profit, 2),
            "profit_margin_percent": round((profit / data.selling_price) * 100, 2),
            "delivery_days": offer.delivery_days,
            "stock_quantity": offer.stock_quantity,
            "moq": offer.moq,
            "source_url": offer.source_url,
            "captured_at": offer.captured_at,
            "price_evidence": "user_supplied_or_imported_not_live_verified",
            "evidence_metadata": _evidence_metadata(offer.source_url, offer.captured_at),
        })
    results.sort(key=lambda item: item["estimated_profit"], reverse=True)
    return {
        "country": data.country,
        "currency": data.currency,
        "selling_price": data.selling_price,
        "offers": results,
        "best_estimated_profit_supplier": results[0]["supplier_id"] if results else None,
        "data_note": "Comparison uses only submitted supplier prices and costs. Confirm current stock, quote validity, taxes, COD, returns and delivery terms with each supplier.",
    }


@app.post("/api/v1/marketplace-prices/compare")
def compare_marketplace_prices(data: MarketplacePriceComparison):
    """Compare user-observed marketplace listings against a supplier quote.

    This endpoint deliberately does not scrape marketplaces or infer missing
    sales counts. Listing prices and URLs are supplied by the user/import.
    """
    normalized = []
    for listing in data.listings:
        delivered_price = listing.price + listing.shipping_cost
        normalized.append({
            "marketplace": listing.marketplace,
            "listing_title": listing.listing_title,
            "item_price": round(listing.price, 2),
            "shipping_cost": round(listing.shipping_cost, 2),
            "observed_total_price": round(delivered_price, 2),
            "listing_url": listing.listing_url,
            "observed_sold_count": listing.observed_sold_count,
            "captured_at": listing.captured_at,
            "evidence_status": "user_supplied_or_imported_not_live_verified",
            "evidence_metadata": _evidence_metadata(listing.listing_url, listing.captured_at),
        })
    totals = [item["observed_total_price"] for item in normalized]
    average = sum(totals) / len(totals)
    lowest = min(totals)
    highest = max(totals)
    supplier_landed = data.supplier_cost + data.supplier_shipping
    fee = data.planned_selling_price * data.platform_fee_percent / 100
    total_cost = supplier_landed + fee + data.marketing_cost + data.returns_allowance
    profit = data.planned_selling_price - total_cost
    break_even = (
        (supplier_landed + data.marketing_cost + data.returns_allowance)
        / (1 - data.platform_fee_percent / 100)
        if data.platform_fee_percent < 100 else None
    )
    return {
        "product_name": data.product_name,
        "country": data.country,
        "currency": data.currency,
        "listing_count": len(normalized),
        "marketplace_prices": {
            "lowest_delivered_price": round(lowest, 2),
            "average_delivered_price": round(average, 2),
            "median_delivered_price": round(median(totals), 2),
            "highest_delivered_price": round(highest, 2),
            "price_spread": round(highest - lowest, 2),
        },
        "supplier": {
            "product_cost": round(data.supplier_cost, 2),
            "shipping_cost": round(data.supplier_shipping, 2),
            "landed_cost": round(supplier_landed, 2),
        },
        "planned_selling_price": round(data.planned_selling_price, 2),
        "estimated_profit_per_order": round(profit, 2),
        "estimated_profit_margin_percent": round(profit / data.planned_selling_price * 100, 2),
        "break_even_selling_price": round(break_even, 2) if break_even is not None else None,
        "market_average_minus_supplier_landed_cost": round(average - supplier_landed, 2),
        "listings": normalized,
        "data_note": "Marketplace listings and supplier costs were entered or imported by the user. No live marketplace price, sales count, or supplier quote was fetched or independently verified. Delivered listing price includes the entered listing shipping cost; taxes, coupons, COD, returns and fees may differ.",
    }


@app.post("/api/v1/catalog/match")
def match_catalog_products(data: ProductMatchRequest):
    """Match imported supplier and marketplace titles; scores are heuristic, not verified identity."""
    def normalize(title: str) -> str:
        return " ".join(re.findall(r"[\w]+", title.casefold()))

    def similarity(left: str, right: str) -> float:
        left_norm, right_norm = normalize(left), normalize(right)
        if not left_norm or not right_norm:
            return 0.0
        left_tokens, right_tokens = set(left_norm.split()), set(right_norm.split())
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
        return round((0.55 * sequence) + (0.45 * overlap), 4)

    candidates = []
    for supplier in data.supplier_products:
        for market in data.marketplace_products:
            score = similarity(supplier.title, market.title)
            if score >= data.minimum_similarity:
                candidates.append({
                    "supplier_product": supplier.model_dump(),
                    "marketplace_product": market.model_dump(),
                    "similarity": score,
                    "match_status": "suggested_name_match",
                    "review_required": True,
                })
    candidates.sort(key=lambda item: item["similarity"], reverse=True)

    # Greedy one-to-one assignment prevents one listing being counted as many products.
    matches, used_supplier, used_market = [], set(), set()
    for candidate in candidates:
        supplier_id = candidate["supplier_product"]["product_id"]
        market_id = candidate["marketplace_product"]["product_id"]
        if supplier_id in used_supplier or market_id in used_market:
            continue
        matches.append(candidate)
        used_supplier.add(supplier_id)
        used_market.add(market_id)

    return {
        "match_method": "normalized_title_similarity",
        "minimum_similarity": data.minimum_similarity,
        "match_count": len(matches),
        "matches": matches,
        "unmatched_supplier_product_ids": [
            item.product_id for item in data.supplier_products if item.product_id not in used_supplier
        ],
        "unmatched_marketplace_product_ids": [
            item.product_id for item in data.marketplace_products if item.product_id not in used_market
        ],
        "data_note": "Name-based suggestions only. Similar titles do not prove identical variants, quality, model, pack size, authenticity, stock or supplier eligibility. Review every match before pricing or listing.",
    }


@app.post("/api/v1/product-economics")
def product_economics(data: ProductEconomics):
    """Estimate per-unit profit from costs supplied by the user."""
    values = data.model_dump()
    fee = values["selling_price"] * values["platform_fee_percent"] / 100
    total_cost = (
        values["product_cost"]
        + values["shipping_cost"]
        + fee
        + values["marketing_cost"]
        + values["returns_allowance"]
    )
    profit = values["selling_price"] - total_cost
    margin = (profit / values["selling_price"]) * 100
    invested_cost = total_cost
    roi = (profit / invested_cost) * 100 if invested_cost else None
    fixed_costs = (
        values["product_cost"]
        + values["shipping_cost"]
        + values["marketing_cost"]
        + values["returns_allowance"]
    )
    fee_rate = values["platform_fee_percent"] / 100
    break_even = fixed_costs / (1 - fee_rate) if fee_rate < 1 else None
    return {
        "currency": values["currency"],
        "platform_fee": round(fee, 2),
        "total_cost": round(total_cost, 2),
        "profit_per_unit": round(profit, 2),
        "profit_margin_percent": round(margin, 2),
        "roi_percent": round(roi, 2) if roi is not None else None,
        "break_even_selling_price": round(break_even, 2) if break_even is not None else None,
        "note": "Estimate based only on costs and price supplied by the user; taxes and other costs may apply.",
    }


@app.post("/api/v1/score")
def score_opportunity(signals: OpportunitySignals):
    values = signals.model_dump()
    raw_score = sum(values[key] * weight for key, weight in WEIGHTS.items())
    score = round(raw_score * 10)
    return {
        "score": score,
        "rating": "strong" if score >= 75 else "moderate" if score >= 50 else "needs-validation",
        "signals": values,
        "weights": WEIGHTS,
        "explanation": "Transparent weighted estimate from user-provided ratings only.",
    }
