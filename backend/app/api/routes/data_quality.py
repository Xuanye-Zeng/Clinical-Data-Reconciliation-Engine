from fastapi import APIRouter, Depends

from app.api.deps.auth import require_api_key
from app.models.data_quality import DataQualityRequest, DataQualityResponse
from app.services.data_quality_service import validate_data_quality


router = APIRouter(prefix="/api/validate", tags=["data-quality"])


@router.post("/data-quality", response_model=DataQualityResponse)
def validate_data_quality_route(
    payload: DataQualityRequest,
    _: None = Depends(require_api_key),
) -> DataQualityResponse:
    return validate_data_quality(payload)
