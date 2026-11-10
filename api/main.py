"""Free product-opportunity scoring and public market-signal API.

Scores and economics use user-provided inputs. Google Trends RSS is a broad
country-level discovery signal, not product-specific demand or sales data.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
}
GOOGLE_TRENDS_NAMESPACE = "{https://trends.google.com/trending/rss}"


class OpportunitySignals(BaseModel):
    demand: int = Field(ge=1, le=10, description="Strength of demand evidence")
    competition: int = Field(ge=1, le=10, description="Competitive advantage; 10 means low competition")
    margin: int = Field(ge=1, le=10, description="Potential profit margin")
    shipping: int = Field(ge=1, le=10, description="Ease and affordability of shipping")
    trend: int = Field(ge=1, le=10, description="Strength of the observed trend")


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
async def country_trends(country: str = Query(..., pattern=r"^(PK|US|GB|AE|SA|IN|CA|AU|DE)$")):
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
