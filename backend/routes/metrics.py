from fastapi import APIRouter
from backend.services.model_service import model_service

router = APIRouter()

@router.get("/metrics")
def get_metrics():
    return model_service.metrics
