from fastapi import APIRouter
from backend.schemas.whatif import WhatIfRequest, WhatIfResponse
from backend.services.whatif_service import run_what_if

router = APIRouter(prefix="/api/what-if", tags=["What-If Analysis"])


@router.post("", response_model=WhatIfResponse)
def what_if(request: WhatIfRequest):
    """
    Apply a demand scenario to teammate's forecast output.

    Loads from disk:
    - data/outputs/forecasts/{category}_{model}_forecast.csv

    Scenario parameters:
    - change_percent    : uniform % shift on all forecast values
    - disruption_start  : (optional) start of supply disruption window
    - disruption_end    : (optional) end of supply disruption window (zeroed out)
    """
    return run_what_if(request)
