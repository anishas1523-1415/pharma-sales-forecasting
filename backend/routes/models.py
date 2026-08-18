from fastapi import APIRouter
from backend.data_loader import list_available_models_and_categories

router = APIRouter()

@router.get("/models")
def list_models():
    # Derived from forecast CSVs on disk, not from ModelService's live-model
    # registry (that registry only reflects .pkl/.keras binaries, which are
    # gitignored and not present in this deployment — forecast serving reads
    # pre-generated CSVs, so "available" here means "has a forecast file").
    return list_available_models_and_categories()
