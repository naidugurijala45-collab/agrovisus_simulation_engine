"""
Disease Router — image upload → diagnosis (stub for MVP, ready for CNN).
"""
import random
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()


class DiseaseCandidate(BaseModel):
    disease: str
    confidence: float
    recommendation: str


class DiagnosisResult(BaseModel):
    top_prediction: str
    confidence: float
    candidates: List[DiseaseCandidate]
    severity: str
    action_required: bool
    recommendation: str


# Stub disease catalog — replace with CNN inference when model is ready
STUB_DISEASES = [
    {
        "disease": "Northern Corn Leaf Blight",
        "confidence": 0.87,
        "recommendation": "Apply fungicide (Headline or Quilt Xcel) within 48 hours. Monitor surrounding plants.",
        "severity": "Moderate",
        "action_required": True,
    },
    {
        "disease": "Gray Leaf Spot",
        "confidence": 0.76,
        "recommendation": "Scout field for spread. If >5% leaf area affected, consider foliar fungicide application.",
        "severity": "Mild",
        "action_required": False,
    },
    {
        "disease": "Common Rust",
        "confidence": 0.91,
        "recommendation": "Immediate fungicide application recommended. Restrict field access to prevent spread.",
        "severity": "Severe",
        "action_required": True,
    },
    {
        "disease": "Healthy",
        "confidence": 0.95,
        "recommendation": "No disease detected. Continue standard monitoring schedule.",
        "severity": "None",
        "action_required": False,
    },
]


@router.post("/predict", response_model=DiagnosisResult)
async def predict_disease(file: UploadFile = File(...)):
    """
    Accept a leaf image and return a disease diagnosis.
    Currently returns a realistic stub — CNN model integration pending.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (jpg, png, webp)")

    # Read and validate file isn't empty
    contents = await file.read()
    if len(contents) < 100:
        raise HTTPException(status_code=400, detail="Image file appears to be empty or corrupt")

    # Stub: pick a random result (will be replaced by real CNN inference)
    primary = random.choice(STUB_DISEASES)
    others = [d for d in STUB_DISEASES if d["disease"] != primary["disease"]][:2]

    candidates = [
        DiseaseCandidate(
            disease=primary["disease"],
            confidence=primary["confidence"],
            recommendation=primary["recommendation"],
        )
    ] + [
        DiseaseCandidate(
            disease=o["disease"],
            confidence=round(random.uniform(0.03, 0.15), 2),
            recommendation=o["recommendation"],
        )
        for o in others
    ]

    return DiagnosisResult(
        top_prediction=primary["disease"],
        confidence=primary["confidence"],
        candidates=candidates,
        severity=primary["severity"],
        action_required=primary["action_required"],
        recommendation=primary["recommendation"],
    )
