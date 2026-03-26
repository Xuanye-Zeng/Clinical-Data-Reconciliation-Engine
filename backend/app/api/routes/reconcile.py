"""Medication reconciliation route.

Thin HTTP layer: validates the request via Pydantic, checks the API key,
and delegates all business logic to reconciliation_service.
"""

from fastapi import APIRouter, Depends

from app.api.deps.auth import require_api_key
from app.models.reconcile import ReconcileMedicationRequest, ReconcileMedicationResponse
from app.services.reconciliation_service import reconcile_medication


router = APIRouter(prefix="/api/reconcile", tags=["reconcile"])


@router.post("/medication", response_model=ReconcileMedicationResponse)
def reconcile_medication_route(
    payload: ReconcileMedicationRequest,
    _: None = Depends(require_api_key),
) -> ReconcileMedicationResponse:
    return reconcile_medication(payload)
