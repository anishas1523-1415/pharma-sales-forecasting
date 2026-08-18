from fastapi import APIRouter
from backend.services.model_service import model_service

router = APIRouter()

@router.get("/models")
def list_models():
    return {
        "models": model_service.available_models,
        "categories": model_service.available_categories,
    }
