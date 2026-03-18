"""
Chat Router — AI field advisor powered by Claude.
"""
import json
import os
import logging
from typing import Any, Dict, List, Optional

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

SYSTEM_PROMPT = (
    "You are an expert agronomist for AgroVisus. You have the "
    "farmer's simulation results as context. Be specific, practical, "
    "under 120 words. Reference their actual crop, stage, and alerts."
)


# ── Request / Response models ──────────────────────────────────────────────

class AlertContext(BaseModel):
    rule_name: str
    severity: str
    yield_impact_percent: float
    days_active: int
    advisory: str


class ROIContext(BaseModel):
    recommendation_strength: str
    revenue_at_risk_per_acre: float
    roi_mid: float


class FieldContext(BaseModel):
    crop_type: str
    growth_stage: str
    state_code: str
    sim_days_run: int
    final_yield_kg_ha: float
    triggered_alerts: List[AlertContext] = []
    roi: Optional[ROIContext] = None


class ChatRequest(BaseModel):
    message: str
    field_context: FieldContext


class ChatResponse(BaseModel):
    reply: str


# ── Route ──────────────────────────────────────────────────────────────────

@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a question about a field and get an AI agronomist response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    user_message = (
        f"Field context: {json.dumps(req.field_context.model_dump())}\n\n"
        f"Question: {req.message}"
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        reply = message.content[0].text
        return ChatResponse(reply=reply)

    except anthropic.AuthenticationError:
        raise HTTPException(status_code=500, detail="Invalid ANTHROPIC_API_KEY")
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error: {e}")
        raise HTTPException(status_code=502, detail=f"AI service error: {e.message}")
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal error processing chat request")
