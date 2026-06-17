"""Model readiness endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from api.services.model_inference import normalize_horizon, model_status


router = APIRouter()


@router.get("/status")
def get_model_status(load_models: bool = Query(False, description="Attempt to load model artifacts")):
    """Get model artifact readiness and feature-schema status."""
    return model_status(load_models=load_models)


@router.get("/explain/{segment_id}")
def explain_model_prediction(
    segment_id: str,
    horizon: str = Query("15m", description="Forecast horizon (15m, 60m, or 240m)"),
):
    """Return 501 until segment-level SHAP artifacts are generated and tested."""
    try:
        normalized = normalize_horizon(horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(
        status_code=501,
        detail={
            "segment_id": segment_id,
            "horizon": normalized,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "message": "Segment-level SHAP explanations are not implemented. Existing explainability endpoint uses baseline perturbation, not SHAP artifacts.",
        },
    )
