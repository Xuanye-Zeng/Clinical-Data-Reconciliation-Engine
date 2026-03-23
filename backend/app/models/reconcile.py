from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class PatientContext(BaseModel):
    age: int | None = None
    conditions: list[str] = Field(default_factory=list)
    recent_labs: dict[str, Any] = Field(default_factory=dict)


class MedicationSource(BaseModel):
    system: str
    medication: str
    last_updated: date | None = None
    last_filled: date | None = None
    source_reliability: str = "medium"


class ReconcileMedicationRequest(BaseModel):
    patient_context: PatientContext
    sources: list[MedicationSource] = Field(min_length=1)


class ReconcileMedicationResponse(BaseModel):
    reconciled_medication: str
    confidence_score: float
    reasoning: str
    recommended_actions: list[str]
    clinical_safety_check: str
