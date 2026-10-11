"""Aggregate all route modules under one APIRouter (mounted at /api)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    elevation,
    health,
    jobs,
    layers,
    minerals,
    observations,
    provenance,
    results,
    tiles,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(layers.router, tags=["map"])
api_router.include_router(observations.router, tags=["catalog"])
api_router.include_router(minerals.router, tags=["catalog"])
api_router.include_router(jobs.router, tags=["analysis"])
api_router.include_router(results.router, tags=["analysis"])
api_router.include_router(tiles.router, tags=["analysis", "map"])
api_router.include_router(provenance.router, tags=["analysis"])
api_router.include_router(elevation.router, tags=["map"])
