"""Free, transparent product-opportunity scoring API.

This service scores user-provided research signals. It does not claim to fetch
live marketplace data or make autonomous AI predictions.
"""
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="AI Winning Product Finder API",
    description="Open API for transparent product opportunity scoring.",
    version="0.1.0",
)

WEIGHTS = {
    "demand": 0.30,
    "competition": 0.20,
    "margin": 0.25,
    "shipping": 0.10,
    "trend": 0.15,
}


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


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-winning-product-finder-api"}


@app.get("/api/v1/scoring-model")
def scoring_model():
    return {
        "version": "0.1.0",
        "scale": {"minimum": 1, "maximum": 10},
        "weights": WEIGHTS,
        "note": "Scores are estimates based only on supplied inputs, not live market evidence.",
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
