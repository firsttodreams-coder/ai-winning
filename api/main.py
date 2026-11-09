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
