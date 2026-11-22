"""Free product-opportunity scoring and public market-signal API.

Scores and economics use user-provided inputs. Google Trends RSS is a broad
country-level discovery signal, not product-specific demand or sales data.
"""
from datetime import datetime, timezone
import csv
import io
from email.utils import parsedate_to_datetime
from statistics import median
from difflib import SequenceMatcher
import re
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from api.connectors import router as supplier_connectors_router

app = FastAPI(
    title="AI Winning Product Finder API",
    description="Open API for transparent product scoring and public market signals.",
    version="0.2.0",
)

app.include_router(supplier_connectors_router)

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


def _validate_public_http_url(value: str | None) -> str | None:
    """Accept only absolute public HTTP(S) URLs for evidence provenance."""
    if value is None:
        return None
    candidate = value.strip()
    try:
        parsed = urlsplit(candidate)
        valid = (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("URL must be an absolute HTTP or HTTPS address without embedded credentials.")
    return candidate


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


class OpportunityEvidence(BaseModel):
    evidence_type: str = Field(min_length=2, max_length=40)
    source_name: str = Field(min_length=2, max_length=100)
    source_url: str = Field(min_length=8, max_length=2048)
    captured_at: str | None = Field(default=None, max_length=64)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value):
        return _validate_public_http_url(value)


class ProductOpportunityCandidate(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=80)
    product_name: str = Field(min_length=2, max_length=160)
    country: str = Field(pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$")
    city: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    signals: OpportunitySignals
    evidence: list[OpportunityEvidence] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_market_currency(self):
        _validate_market_currency(self.country, self.currency)
        return self


class ProductDiscoveryRequest(BaseModel):
    candidates: list[ProductOpportunityCandidate] = Field(min_length=1, max_length=50)


class ProductTrendCheckRequest(BaseModel):
    country: str = Field(pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$")
    product_names: list[str] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_product_names(self):
        cleaned = [name.strip() for name in self.product_names]
        if any(len(name) < 2 or len(name) > 120 for name in cleaned):
            raise ValueError("Each product name must contain 2 to 120 characters.")
        if len({name.casefold() for name in cleaned}) != len(cleaned):
            raise ValueError("Product names must be unique.")
        self.product_names = cleaned
        return self


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

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value):
        return _validate_public_http_url(value)


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

    @field_validator("listing_url")
    @classmethod
    def validate_listing_url(cls, value):
        return _validate_public_http_url(value)


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


class CatalogMatchContext(BaseModel):
    supplier_product_id: str = Field(min_length=1, max_length=80)
    supplier_title: str = Field(min_length=2, max_length=200)
    marketplace_product_id: str = Field(min_length=1, max_length=80)
    marketplace_title: str = Field(min_length=2, max_length=200)
    similarity: float = Field(ge=0, le=1)


class UnifiedProfitabilityComparison(BaseModel):
    product_name: str = Field(min_length=2, max_length=160)
    country: str = Field(pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$")
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    planned_selling_price: float = Field(gt=0, le=100000000)
    platform_fee_percent: float = Field(default=0, ge=0, le=100)
    marketing_cost: float = Field(default=0, ge=0, le=100000000)
    returns_allowance: float = Field(default=0, ge=0, le=100000000)
    offers: list[SupplierOffer] = Field(min_length=1, max_length=50)
    listings: list[MarketplaceListing] = Field(min_length=1, max_length=50)
    product_identity_confirmed: bool = False
    catalog_match_context: CatalogMatchContext | None = None

    @model_validator(mode="after")
    def validate_market_and_currency(self):
        _validate_market_currency(self.country, self.currency)
        if not self.product_identity_confirmed:
            raise ValueError("Confirm supplier offers and marketplace listings are the same product and variant before comparing profitability.")
        known_suppliers = {supplier["id"]: supplier for supplier in SUPPLIERS}
        for offer in self.offers:
            supplier = known_suppliers.get(offer.supplier_id)
            if supplier and self.country not in supplier["countries"]:
                raise ValueError(
                    f"Supplier {offer.supplier_id} is not listed for market {self.country}."
                )
        return self


class CatalogProduct(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=200)
    sku: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    size: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=60)
    pack_quantity: int | None = Field(default=None, ge=1, le=10000)
    condition: str | None = Field(default=None, max_length=40)
    supplier_id: str | None = Field(default=None, max_length=60)
    supplier_name: str | None = Field(default=None, max_length=120)
    product_cost: float | None = Field(default=None, ge=0, le=100000000)
    shipping_cost: float | None = Field(default=None, ge=0, le=100000000)
    handling_cost: float | None = Field(default=None, ge=0, le=100000000)
    delivery_days: int | None = Field(default=None, ge=0, le=365)
    stock_quantity: int | None = Field(default=None, ge=0)
    moq: int | None = Field(default=None, ge=1)
    source_url: str | None = Field(default=None, max_length=2048)
    captured_at: str | None = Field(default=None, max_length=64)
    marketplace_price: float | None = Field(default=None, gt=0, le=100000000)
    marketplace_shipping_cost: float | None = Field(default=None, ge=0, le=100000000)
    marketplace_listing_url: str | None = Field(default=None, max_length=2048)
    marketplace_captured_at: str | None = Field(default=None, max_length=64)

    @field_validator("source_url", "marketplace_listing_url")
    @classmethod
    def validate_catalog_urls(cls, value):
        return _validate_public_http_url(value)


class ProductMatchRequest(BaseModel):
    supplier_products: list[CatalogProduct] = Field(min_length=1, max_length=50)
    marketplace_products: list[CatalogProduct] = Field(min_length=1, max_length=50)
    minimum_similarity: float = Field(default=0.45, ge=0, le=1)


class SupplierCatalogImportRequest(BaseModel):
    supplier_id: str = Field(min_length=2, max_length=60)
    country: str = Field(pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$")
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    csv_content: str = Field(min_length=10, max_length=2_000_000)

    @model_validator(mode="after")
    def validate_supplier_market(self):
        _validate_market_currency(self.country, self.currency)
        supplier = next((item for item in SUPPLIERS if item["id"] == self.supplier_id), None)
        if supplier is None:
            raise ValueError("Supplier ID is not in the supported supplier directory.")
        if self.country not in supplier["countries"]:
            raise ValueError(f"Supplier {self.supplier_id} is not listed for market {self.country}.")
        return self


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



def _trend_tokens(value: str) -> set[str]:
    """Tokenize Unicode letters and numbers, including Urdu and Arabic-script text."""
    return set(re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE))


def _trend_freshness(started: str | None, now: datetime | None = None) -> dict:
    """Classify trend timestamp age; this is not a demand-strength score."""
    if not started:
        return {"trend_age_hours": None, "trend_freshness": "unknown"}
    try:
        observed = datetime.fromisoformat(started.strip().replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        age_hours = (reference.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds() / 3600
    except (AttributeError, TypeError, ValueError, OverflowError):
        return {"trend_age_hours": None, "trend_freshness": "invalid_timestamp"}
    if age_hours < -0.05:
        status = "future_timestamp"
    elif age_hours <= 24:
        status = "fresh"
    elif age_hours <= 168:
        status = "aging"
    else:
        status = "stale"
    return {"trend_age_hours": round(age_hours, 2), "trend_freshness": status}


def match_product_to_trends(product_name: str, trends: list[dict], now: datetime | None = None) -> list[dict]:
    """Find literal Unicode token overlap; never infer sales demand."""
    product_terms = _trend_tokens(product_name)
    if not product_terms:
        return []
    matches = []
    for trend in trends:
        title_terms = _trend_tokens(trend.get("title", ""))
        matched_terms = sorted(product_terms & title_terms)
        coverage = len(matched_terms) / len(product_terms)
        if coverage >= 0.5:
            matches.append({
                **trend,
                **_trend_freshness(trend.get("started"), now),
                "match_score": round(coverage * 100, 1),
                "matched_terms": matched_terms,
                "relevance": "strong" if coverage == 1 else "partial",
            })
    freshness_priority = {"fresh": 3, "aging": 2, "unknown": 1, "stale": 0}
    return sorted(
        matches,
        key=lambda item: (
            freshness_priority.get(item["trend_freshness"], -1),
            item["match_score"],
            item.get("started") or "",
        ),
        reverse=True,
    )


@app.get("/api/v1/trends/match")
async def product_trend_matches(
    country: str = Query(..., pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE|OM|QA|KW|BH)$"),
    product_name: str = Query(..., min_length=2, max_length=120),
):
    """Match a product name against literal terms in Google's current country trend titles."""
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
    matches = match_product_to_trends(product_name, trends)
    return {
        "country": country,
        "product_name": product_name,
        "source": feed_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "match_count": len(matches),
        "matches": matches,
        "matching_method": "Literal Unicode token overlap against current trend titles; at least 50% of product-name tokens must match.",
        "freshness_method": "Trend timestamps are labelled fresh (up to 24h), aging (24h–7d), stale (over 7d), unknown, or invalid/future; freshness is not demand strength.",
        "data_note": "A name match is only a discovery hint. It does not prove product-specific search volume, purchase intent, marketplace sales or future demand. No match does not mean no demand.",
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



@app.post("/api/v1/product-discovery/trend-check")
async def batch_product_trend_check(data: ProductTrendCheckRequest):
    """Check multiple product names against one fresh country-level Trends feed."""
    feed_url = f"https://trends.google.com/trending/rss?geo={data.country}"
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

    results = []
    for product_name in data.product_names:
        matches = match_product_to_trends(product_name, trends)
        results.append({
            "product_name": product_name,
            "match_count": len(matches),
            "matches": matches,
            "interpretation": "literal_trend_title_overlap_only",
            "verified_product_demand": False,
        })
    return {
        "country": data.country,
        "country_name": TREND_COUNTRIES[data.country],
        "source": feed_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "results": results,
        "freshness_method": "Matched trend timestamps are labelled fresh (up to 24h), aging (24h–7d), stale (over 7d), unknown, or invalid/future; freshness is not demand strength.",
        "data_note": "One country-level Google Trends feed was checked for all submitted products. Matches are lexical discovery hints only; broad trends do not prove product-specific demand, marketplace sales, or a sales forecast. No match does not mean no demand.",
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


@app.post("/api/v1/supplier-catalog/import")
def import_supplier_catalog(data: SupplierCatalogImportRequest):
    """Validate and normalize a supplier CSV without claiming a live connection."""
    try:
        reader = csv.DictReader(io.StringIO(data.csv_content.lstrip("\ufeff")))
        if not reader.fieldnames:
            raise ValueError("CSV header row is missing.")
        aliases = {
            "product_id": ("product_id", "supplier_product_id", "id", "sku"),
            "title": ("title", "product_title", "product_name", "name"),
            "sku": ("sku", "seller_sku", "product_sku"),
            "brand": ("brand", "manufacturer"),
            "model": ("model", "model_number"),
            "size": ("size", "product_size"),
            "color": ("color", "colour"),
            "product_cost": ("product_cost", "supplier_price", "cost", "price"),
            "shipping_cost": ("shipping_cost", "delivery_cost", "shipping", "delivery"),
            "handling_cost": ("handling_cost", "handling"),
            "delivery_days": ("delivery_days", "dispatch_days", "lead_time_days"),
            "stock_quantity": ("stock_quantity", "stock", "inventory", "quantity"),
            "moq": ("moq", "minimum_order_quantity"),
            "source_url": ("source_url", "product_url", "url", "link"),
            "captured_at": ("captured_at", "updated_at", "snapshot_at"),
        }
        normalized_headers = {
            re.sub(r"[\s-]+", "_", str(name).strip().lower()): name
            for name in reader.fieldnames if name
        }
        selected = {
            target: next((normalized_headers[name] for name in names if name in normalized_headers), None)
            for target, names in aliases.items()
        }
        if selected["title"] is None or selected["product_cost"] is None:
            raise ValueError("CSV must include product title/name and product cost/price columns.")

        def cell(row, field):
            column = selected[field]
            value = row.get(column) if column else None
            return str(value).strip() if value is not None and str(value).strip() else None

        def number(row, field, integer=False, required=False):
            value = cell(row, field)
            if value is None:
                if required:
                    raise ValueError(f"Missing required value: {field}.")
                return None
            cleaned = value.replace(",", "").replace(data.currency, "").strip()
            try:
                parsed = float(cleaned)
            except ValueError as exc:
                raise ValueError(f"Invalid numeric value for {field}: {value}.") from exc
            if integer:
                if not parsed.is_integer():
                    raise ValueError(f"{field} must be a whole number.")
                return int(parsed)
            return parsed

        supplier = next(item for item in SUPPLIERS if item["id"] == data.supplier_id)
        products = []
        errors = []
        for row_number, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue
            if len(products) + len(errors) >= 500:
                raise ValueError("CSV import is limited to 500 non-empty rows.")
            try:
                title = cell(row, "title")
                if not title:
                    raise ValueError("Product title is empty.")
                product_id = cell(row, "product_id") or f"{data.supplier_id}-{row_number}"
                source_url = cell(row, "source_url")
                if source_url:
                    source_url = _validate_public_http_url(source_url)
                products.append({
                    "product_id": product_id,
                    "title": title,
                    "sku": cell(row, "sku"),
                    "brand": cell(row, "brand"),
                    "model": cell(row, "model"),
                    "size": cell(row, "size"),
                    "color": cell(row, "color"),
                    "supplier_id": data.supplier_id,
                    "supplier_name": supplier["name"],
                    "country": data.country,
                    "currency": data.currency,
                    "product_cost": number(row, "product_cost", required=True),
                    "shipping_cost": number(row, "shipping_cost") or 0,
                    "handling_cost": number(row, "handling_cost") or 0,
                    "delivery_days": number(row, "delivery_days", integer=True),
                    "stock_quantity": number(row, "stock_quantity", integer=True),
                    "moq": number(row, "moq", integer=True),
                    "source_url": source_url,
                    "captured_at": cell(row, "captured_at"),
                    "evidence_status": "user_supplied_or_imported_not_live_verified",
                })
            except (ValueError, TypeError) as exc:
                errors.append({"row": row_number, "error": str(exc)})
        if not products and errors:
            raise ValueError(f"No valid product rows found. First row error: {errors[0]['error']}")
        return {
            "supplier_id": data.supplier_id,
            "supplier_name": supplier["name"],
            "country": data.country,
            "currency": data.currency,
            "imported_count": len(products),
            "rejected_count": len(errors),
            "products": products,
            "row_errors": errors,
            "connection_verified": False,
            "live_catalog_fetch_enabled": False,
            "data_note": "CSV rows were supplied by the user. This endpoint validates and previews the import; it does not fetch a supplier feed, verify stock, or persist catalog records.",
        }
    except csv.Error as exc:
        raise HTTPException(status_code=422, detail=f"Invalid CSV: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


def _marketplace_group_summaries(listings):
    """Summarize submitted listing observations by marketplace without inferring sales."""
    groups = {}
    for listing in listings:
        groups.setdefault(listing["marketplace"], []).append(listing)
    summaries = []
    for name, rows in sorted(groups.items(), key=lambda item: item[0].casefold()):
        prices = [row["observed_total_price"] for row in rows]
        sold_counts = [row["observed_sold_count"] for row in rows if row["observed_sold_count"] is not None]
        summaries.append({
            "marketplace": name,
            "listing_count": len(rows),
            "lowest_delivered_price": round(min(prices), 2),
            "average_delivered_price": round(sum(prices) / len(prices), 2),
            "median_delivered_price": round(median(prices), 2),
            "highest_delivered_price": round(max(prices), 2),
            "observed_sold_count_samples": len(sold_counts),
        })
    return summaries

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
    price_gap_percent = ((data.planned_selling_price - average) / average) * 100
    price_position = (
        "near_average" if abs(price_gap_percent) <= 1
        else "below_average" if price_gap_percent < 0
        else "above_average"
    )
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
            "by_marketplace": _marketplace_group_summaries(normalized),
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
        "planned_price_vs_market_average_percent": round(price_gap_percent, 2),
        "planned_price_position": price_position,
        "estimated_profit_per_order": round(profit, 2),
        "estimated_profit_margin_percent": round(profit / data.planned_selling_price * 100, 2),
        "break_even_selling_price": round(break_even, 2) if break_even is not None else None,
        "market_average_minus_supplier_landed_cost": round(average - supplier_landed, 2),
        "listings": normalized,
        "data_note": "Marketplace listings and supplier costs were entered or imported by the user. No live marketplace price, sales count, or supplier quote was fetched or independently verified. Delivered listing price includes the entered listing shipping cost; taxes, coupons, COD, returns and fees may differ.",
    }


@app.post("/api/v1/product-profitability/compare")
def compare_product_profitability(data: UnifiedProfitabilityComparison):
    """Join entered supplier offers with observed marketplace prices for one product."""
    listing_rows = []
    for listing in data.listings:
        delivered = listing.price + listing.shipping_cost
        listing_rows.append({
            "marketplace": listing.marketplace,
            "listing_title": listing.listing_title,
            "item_price": round(listing.price, 2),
            "shipping_cost": round(listing.shipping_cost, 2),
            "observed_total_price": round(delivered, 2),
            "listing_url": listing.listing_url,
            "observed_sold_count": listing.observed_sold_count,
            "captured_at": listing.captured_at,
            "evidence_status": "user_supplied_or_imported_not_live_verified",
            "evidence_metadata": _evidence_metadata(listing.listing_url, listing.captured_at),
        })

    market_prices = [row["observed_total_price"] for row in listing_rows]
    market_average = sum(market_prices) / len(market_prices)
    market_median = median(market_prices)
    market_low = min(market_prices)
    market_high = max(market_prices)
    fee_rate = data.platform_fee_percent / 100
    marketplace_groups = _marketplace_group_summaries(listing_rows)
    comparisons = []

    for offer in data.offers:
        landed = offer.product_cost + offer.shipping_cost + offer.handling_cost
        planned_fee = data.planned_selling_price * fee_rate
        planned_profit = (
            data.planned_selling_price - landed - planned_fee
            - data.marketing_cost - data.returns_allowance
        )
        market_fee = market_average * fee_rate
        market_profit = (
            market_average - landed - market_fee
            - data.marketing_cost - data.returns_allowance
        )
        break_even = (
            (landed + data.marketing_cost + data.returns_allowance) / (1 - fee_rate)
            if fee_rate < 1 else None
        )
        moq_investment = landed * offer.moq if offer.moq is not None else None
        comparisons.append({
            "supplier_id": offer.supplier_id,
            "supplier_name": offer.supplier_name,
            "product_cost": round(offer.product_cost, 2),
            "shipping_cost": round(offer.shipping_cost, 2),
            "handling_cost": round(offer.handling_cost, 2),
            "landed_cost_per_unit": round(landed, 2),
            "planned_selling_price": round(data.planned_selling_price, 2),
            "planned_profit_per_order": round(planned_profit, 2),
            "planned_profit_margin_percent": round(planned_profit / data.planned_selling_price * 100, 2),
            "planned_roi_percent": round(planned_profit / landed * 100, 2) if landed > 0 else None,
            "market_average_profit_per_order": round(market_profit, 2),
            "market_average_profit_margin_percent": round(market_profit / market_average * 100, 2),
            "marketplace_profitability": [{
                "marketplace": group["marketplace"],
                "listing_count": group["listing_count"],
                "average_delivered_price": group["average_delivered_price"],
                "lowest_delivered_price": group["lowest_delivered_price"],
                "estimated_profit_at_average_price": round(group["average_delivered_price"] * (1 - fee_rate) - landed - data.marketing_cost - data.returns_allowance, 2),
                "estimated_profit_at_lowest_price": round(group["lowest_delivered_price"] * (1 - fee_rate) - landed - data.marketing_cost - data.returns_allowance, 2),
                "estimated_margin_at_average_price_percent": round(((group["average_delivered_price"] * (1 - fee_rate) - landed - data.marketing_cost - data.returns_allowance) / group["average_delivered_price"] * 100), 2),
            } for group in marketplace_groups],
            "break_even_selling_price": round(break_even, 2) if break_even is not None else None,
            "moq": offer.moq,
            "estimated_moq_investment": round(moq_investment, 2) if moq_investment is not None else None,
            "delivery_days": offer.delivery_days,
            "stock_quantity": offer.stock_quantity,
            "stock_status": (
                "unknown" if offer.stock_quantity is None
                else "insufficient_for_moq" if offer.moq is not None and offer.stock_quantity < offer.moq
                else "available"
            ),
            "moq_fulfillable": (
                None if offer.stock_quantity is None or offer.moq is None
                else offer.stock_quantity >= offer.moq
            ),
            "source_url": offer.source_url,
            "captured_at": offer.captured_at,
            "evidence_status": "user_supplied_or_imported_not_live_verified",
            "evidence_metadata": _evidence_metadata(offer.source_url, offer.captured_at),
        })

    # A supplier with a known stock shortfall must not outrank one able to meet MOQ.
    stock_priority = {
        "available": 2,
        "unknown": 1,
        "insufficient_for_moq": 0,
    }
    comparisons.sort(
        key=lambda row: (
            stock_priority[row["stock_status"]],
            row["planned_profit_per_order"],
        ),
        reverse=True,
    )
    for rank, comparison in enumerate(comparisons, start=1):
        comparison["supplier_rank"] = rank
    eligible_comparisons = [
        row for row in comparisons if row["stock_status"] != "insufficient_for_moq"
    ]
    return {
        "product_name": data.product_name,
        "country": data.country,
        "currency": data.currency,
        "marketplace": {
            "listing_count": len(listing_rows),
            "by_marketplace": marketplace_groups,
            "lowest_delivered_price": round(market_low, 2),
            "average_delivered_price": round(market_average, 2),
            "median_delivered_price": round(market_median, 2),
            "highest_delivered_price": round(market_high, 2),
            "price_spread": round(market_high - market_low, 2),
            "listings": listing_rows,
        },
        "supplier_comparisons": comparisons,
        "best_supplier_by_planned_profit": (
            eligible_comparisons[0]["supplier_id"]
            if eligible_comparisons and eligible_comparisons[0]["planned_profit_per_order"] > 0
            else None
        ),
        "recommendation_status": (
            "positive_estimated_profit_available"
            if eligible_comparisons and eligible_comparisons[0]["planned_profit_per_order"] > 0
            else "no_positive_estimated_profit"
        ),
        "supplier_ranking_note": (
            "Known stock shortages below MOQ are ranked after suppliers without a known shortfall. Unknown stock is not treated as verified availability; confirm stock and MOQ directly."
        ),
        "catalog_match_context": ({
            **data.catalog_match_context.model_dump(),
            "status": "catalog_suggestion_selected",
            "review_required": True,
            "automated_identity_verified": False,
        } if data.catalog_match_context else None),
        "product_identity_review": {
            "status": "user_confirmed",
            "verification_method": "manual_checkbox",
            "automated_catalog_match_performed": False,
            "review_required": True,
            "review_note": "User confirmed product identity manually. This is not an automated SKU, brand, model or variant match; inspect supplier and listing specifications before purchase.",
        },
        "data_note": (
            "Supplier quotes and marketplace listings were entered or imported by the user; "
            "they are not live-verified. Profit estimates use the entered planned price or "
            "observed marketplace average and the entered fee, marketing and returns costs. "
            "MOQ investment is landed unit cost multiplied by MOQ; taxes, duties, COD, "
            "payment fees and unexpected returns are excluded unless entered."
        ),
    }


@app.post("/api/v1/catalog/match")
def match_catalog_products(data: ProductMatchRequest):
    """Suggest conservative catalogue matches; conflicting variants are never auto-matched."""
    def normalize(value: str) -> str:
        return " ".join(re.findall(r"[\w]+", value.casefold()))

    def numeric_fingerprints(value: str) -> set[str]:
        # Numbers often encode model, size, capacity or pack-count variants.
        return set(re.findall(r"\d+(?:\.\d+)?", normalize(value)))

    def matching_model(left: CatalogProduct, right: CatalogProduct) -> bool:
        return bool(
            left.model and right.model
            and normalize(left.model) == normalize(right.model)
        )

    attribute_fields = ("brand", "model", "size", "color", "pack_quantity", "condition")

    def attribute_conflicts(left: CatalogProduct, right: CatalogProduct) -> list[str]:
        conflicts = []
        for field in attribute_fields:
            lv, rv = getattr(left, field), getattr(right, field)
            if lv is None or rv is None:
                continue
            equal = lv == rv if field == "pack_quantity" else normalize(str(lv)) == normalize(str(rv))
            if not equal:
                conflicts.append(field)
        return conflicts

    def similarity(left: CatalogProduct, right: CatalogProduct) -> tuple[float, str | None]:
        left_title, right_title = normalize(left.title), normalize(right.title)
        if not left_title or not right_title:
            return 0.0, None

        # When both sources expose SKUs, a disagreement is stronger evidence
        # than a similar title: never fall back to fuzzy matching across SKUs.
        if left.sku and right.sku:
            if left.sku.strip().casefold() == right.sku.strip().casefold():
                return 1.0, "exact_sku"
            return 0.0, None

        left_numbers, right_numbers = numeric_fingerprints(left.title), numeric_fingerprints(right.title)
        # A supplied, matching model attribute can resolve a title that omits
        # the model number. Without that structured confirmation, stay strict.
        if (
            left_numbers != right_numbers
            and (left_numbers or right_numbers)
            and not matching_model(left, right)
        ):
            return 0.0, None

        left_tokens, right_tokens = set(left_title.split()), set(right_title.split())
        overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        sequence = SequenceMatcher(None, left_title, right_title).ratio()
        score = round((0.55 * sequence) + (0.45 * overlap), 4)
        return score, "title_and_variant_compatible" if left_numbers or right_numbers else "title_similarity"

    candidates = []
    excluded_sku_conflicts = 0
    excluded_variant_ambiguities = 0
    excluded_attribute_conflict_pairs = 0
    for supplier in data.supplier_products:
        for market in data.marketplace_products:
            # Count conservative exclusions for diagnostics without returning
            # potentially sensitive or overly verbose pair-level details.
            if supplier.sku and market.sku and supplier.sku.strip().casefold() != market.sku.strip().casefold():
                excluded_sku_conflicts += 1
                continue
            if attribute_conflicts(supplier, market):
                excluded_attribute_conflict_pairs += 1
                continue
            exact_sku = bool(
                supplier.sku and market.sku
                and supplier.sku.strip().casefold() == market.sku.strip().casefold()
            )
            supplier_numbers = numeric_fingerprints(supplier.title)
            market_numbers = numeric_fingerprints(market.title)
            if (
                supplier_numbers != market_numbers
                and (supplier_numbers or market_numbers)
                and not exact_sku
                and not matching_model(supplier, market)
            ):
                excluded_variant_ambiguities += 1
                continue
            score, reason = similarity(supplier, market)
            if reason and score >= data.minimum_similarity:
                candidates.append({
                    "supplier_product": supplier.model_dump(),
                    "marketplace_product": market.model_dump(),
                    "similarity": score,
                    "confidence": "high" if score >= 0.85 else "medium" if score >= 0.65 else "low",
                    "match_reason": reason,
                    "match_status": "suggested_name_match",
                    "review_required": True,
                })
    candidates.sort(key=lambda item: (item["similarity"], item["match_reason"] == "exact_sku"), reverse=True)

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
        "match_method": "sku_first_variant_aware_title_similarity",
        "minimum_similarity": data.minimum_similarity,
        "match_count": len(matches),
        "excluded_sku_conflict_pairs": excluded_sku_conflicts,
        "excluded_variant_ambiguity_pairs": excluded_variant_ambiguities,
        "excluded_attribute_conflict_pairs": excluded_attribute_conflict_pairs,
        "matches": matches,
        "unmatched_supplier_product_ids": [
            item.product_id for item in data.supplier_products if item.product_id not in used_supplier
        ],
        "unmatched_marketplace_product_ids": [
            item.product_id for item in data.marketplace_products if item.product_id not in used_market
        ],
        "data_note": "SKU, supplied attribute and title-based suggestions only. Conflicting known brand, model, size, colour, pack quantity or condition values are excluded. Missing attributes are not inferred; review quality, authenticity, stock, delivery and supplier eligibility before pricing or listing.",
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


@app.post("/api/v1/product-discovery/rank")
def rank_product_opportunities(data: ProductDiscoveryRequest):
    """Rank submitted product candidates without inventing demand or sales metrics."""
    ranked = []
    seen_ids = set()
    for candidate in data.candidates:
        if candidate.candidate_id in seen_ids:
            raise HTTPException(status_code=422, detail="candidate_id values must be unique.")
        seen_ids.add(candidate.candidate_id)
        signal_values = candidate.signals.model_dump()
        score = round(sum(signal_values[key] * weight for key, weight in WEIGHTS.items()) * 10)
        evidence_rows = []
        fresh_count = 0
        usable_source_count = 0
        for evidence in candidate.evidence:
            metadata = _evidence_metadata(evidence.source_url, evidence.captured_at)
            if metadata["source_domain"]:
                usable_source_count += 1
            if metadata["freshness_status"] == "fresh":
                fresh_count += 1
            evidence_rows.append({
                **evidence.model_dump(),
                "evidence_metadata": metadata,
                "verification_status": "submitted_source_not_independently_verified",
            })

        # Confidence describes evidence coverage/freshness, never likelihood of sales.
        if usable_source_count >= 3 and fresh_count >= 2:
            confidence = "higher_evidence_coverage"
        elif usable_source_count >= 1:
            confidence = "some_evidence"
        else:
            confidence = "insufficient_evidence"
        ranked.append({
            "candidate_id": candidate.candidate_id,
            "product_name": candidate.product_name,
            "country": candidate.country,
            "city": candidate.city,
            "category": candidate.category,
            "currency": candidate.currency,
            "opportunity_score": score,
            "score_rating": "strong" if score >= 75 else "moderate" if score >= 50 else "needs-validation",
            "signals": signal_values,
            "weights": WEIGHTS,
            "evidence_count": len(evidence_rows),
            "usable_source_count": usable_source_count,
            "fresh_evidence_count": fresh_count,
            "evidence_confidence": confidence,
            "evidence": evidence_rows,
            "sales_forecast": None,
            "verified_sales_data": False,
            "explanation": "Score is a weighted estimate from submitted ratings. Evidence confidence reflects source-link coverage and timestamp freshness only; it does not verify demand, sales, or product identity.",
        })
    ranked.sort(key=lambda item: (item["opportunity_score"], item["usable_source_count"], item["fresh_evidence_count"]), reverse=True)
    return {
        "count": len(ranked),
        "ranking_method": "transparent_weighted_user_signals_with_evidence_coverage",
        "ranked_candidates": ranked,
        "data_note": "This endpoint ranks only candidates and evidence supplied in the request. It does not fetch product sales, marketplace prices, competitor counts, or supplier stock. Scores are estimates, not guaranteed winning-product predictions; source URLs and timestamps are not independently verified.",
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
