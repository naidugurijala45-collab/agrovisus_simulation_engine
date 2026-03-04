"""
AgroVisus FastAPI Backend — Main Entry Point
"""
import json
import logging
import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add simulation engine to path
ENGINE_ROOT = Path(__file__).parent.parent / "engine"
sys.path.insert(0, str(ENGINE_ROOT))

from backend.routers import simulation, disease, crops

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AgroVisus API",
    description="AI-powered crop simulation and diagnosis platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(disease.router, prefix="/api/disease", tags=["Disease"])
app.include_router(crops.router, prefix="/api/crops", tags=["Crops"])


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "AgroVisus API"}
