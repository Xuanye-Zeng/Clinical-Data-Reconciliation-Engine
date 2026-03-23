from datetime import date

from pydantic import BaseModel, Field


class Demographics(BaseModel):
    name: str | None = None
    dob: date | None = None
    gender: str | None = None


class VitalSigns(BaseModel):
    blood_pressure: str | None = None
    heart_rate: int | None = None


class DataQualityRequest(BaseModel):
    demographics: Demographics
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    vital_signs: VitalSigns = Field(default_factory=VitalSigns)
    last_updated: date | None = None


class ScoreBreakdown(BaseModel):
    completeness: int
    accuracy: int
    timeliness: int
    clinical_plausibility: int


class QualityIssue(BaseModel):
    field: str
    issue: str
    severity: str


class DataQualityResponse(BaseModel):
    overall_score: int
    breakdown: ScoreBreakdown
    issues_detected: list[QualityIssue]
