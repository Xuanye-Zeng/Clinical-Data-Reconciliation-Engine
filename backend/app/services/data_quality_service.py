"""
Data quality validation service.

Scores a patient record across four dimensions:
  - Completeness: are key fields populated?
  - Accuracy: do values look correct?
  - Timeliness: is the record fresh enough?
  - Clinical plausibility: are vital signs within realistic ranges?

Each dimension starts at 100 and gets penalties for detected issues.
The overall score is the mean of all four dimensions.

After rule-based scoring, the LLM may suggest up to 2 additional issues.
"""

from datetime import date

from app.models.data_quality import (
    DataQualityRequest,
    DataQualityResponse,
    QualityIssue,
    ScoreBreakdown,
)
from app.services.llm_service import generate_additional_quality_issues


# How much each LLM-suggested issue severity deducts from clinical_plausibility
SEVERITY_PENALTIES = {
    "low": 4,
    "medium": 8,
    "high": 15,
}


def _score_completeness(payload: DataQualityRequest, issues: list[QualityIssue]) -> int:
    """Check whether key record sections are populated."""
    score = 100

    if not payload.allergies:
        issues.append(
            QualityIssue(
                field="allergies",
                issue="No allergies documented - likely incomplete.",
                severity="medium",
            )
        )
        score -= 25

    if not payload.conditions:
        issues.append(
            QualityIssue(
                field="conditions",
                issue="No conditions recorded - clinical context may be incomplete.",
                severity="medium",
            )
        )
        score -= 15

    if not payload.demographics.name or not payload.demographics.dob:
        issues.append(
            QualityIssue(
                field="demographics",
                issue="Missing key demographic details.",
                severity="high",
            )
        )
        score -= 30

    return max(score, 0)


def _score_accuracy(payload: DataQualityRequest, issues: list[QualityIssue]) -> int:
    """Check whether field values look valid and normalized."""
    score = 100

    if payload.demographics.gender and payload.demographics.gender not in {"M", "F", "Male", "Female", "Other"}:
        issues.append(
            QualityIssue(
                field="demographics.gender",
                issue="Gender value is outside expected normalized values.",
                severity="low",
            )
        )
        score -= 10

    return max(score, 0)


def _score_timeliness(payload: DataQualityRequest, issues: list[QualityIssue]) -> int:
    """Score based on how recently the record was updated."""
    if payload.last_updated is None:
        issues.append(
            QualityIssue(
                field="last_updated",
                issue="Record freshness is unknown because last_updated is missing.",
                severity="medium",
            )
        )
        return 40

    age_days = (date.today() - payload.last_updated).days
    if age_days <= 30:
        return 100
    if age_days <= 180:
        return 80
    if age_days <= 365:
        issues.append(
            QualityIssue(
                field="last_updated",
                issue="Data is more than 6 months old.",
                severity="medium",
            )
        )
        return 65

    issues.append(
        QualityIssue(
            field="last_updated",
            issue="Data is more than 12 months old and may be stale.",
            severity="high",
        )
    )
    return 45


def _score_clinical_plausibility(payload: DataQualityRequest, issues: list[QualityIssue]) -> int:
    """Flag vital signs that are outside plausible clinical ranges."""
    score = 100
    blood_pressure = payload.vital_signs.blood_pressure

    if blood_pressure:
        try:
            systolic_raw, diastolic_raw = blood_pressure.split("/")
            systolic = int(systolic_raw)
            diastolic = int(diastolic_raw)
            if systolic > 300 or diastolic > 180 or systolic < 60 or diastolic < 30:
                issues.append(
                    QualityIssue(
                        field="vital_signs.blood_pressure",
                        issue=f"Blood pressure {blood_pressure} is physiologically implausible.",
                        severity="high",
                    )
                )
                score -= 60
        except ValueError:
            issues.append(
                QualityIssue(
                    field="vital_signs.blood_pressure",
                    issue="Blood pressure format is invalid. Expected systolic/diastolic.",
                    severity="medium",
                )
            )
            score -= 25

    heart_rate = payload.vital_signs.heart_rate
    if heart_rate is not None and (heart_rate < 20 or heart_rate > 250):
        issues.append(
            QualityIssue(
                field="vital_signs.heart_rate",
                issue=f"Heart rate {heart_rate} is outside a plausible clinical range.",
                severity="high",
            )
        )
        score -= 40

    return max(score, 0)


def validate_data_quality(payload: DataQualityRequest) -> DataQualityResponse:
    """Main entry point for the data quality validation flow.

    Steps:
    1. Run rule-based checks across all four dimensions
    2. Optionally ask the LLM for up to 2 additional issues
    3. Apply severity penalties from LLM issues to clinical_plausibility
    4. Compute overall score as the mean of all four dimensions
    """
    issues: list[QualityIssue] = []

    # Step 1: rule-based scoring
    completeness = _score_completeness(payload, issues)
    accuracy = _score_accuracy(payload, issues)
    timeliness = _score_timeliness(payload, issues)
    clinical_plausibility = _score_clinical_plausibility(payload, issues)

    # Step 2: optional LLM enhancement (falls back to empty list if unavailable)
    llm_issues = generate_additional_quality_issues(payload, issues)
    issues.extend(llm_issues)

    # Step 3: deduct from clinical_plausibility based on LLM issue severity
    llm_penalty = sum(SEVERITY_PENALTIES.get(issue.severity, 0) for issue in llm_issues)
    if llm_penalty:
        clinical_plausibility = max(clinical_plausibility - llm_penalty, 0)

    # Step 4: overall score is the mean of all four dimensions
    overall_score = round((completeness + accuracy + timeliness + clinical_plausibility) / 4)

    return DataQualityResponse(
        overall_score=overall_score,
        breakdown=ScoreBreakdown(
            completeness=completeness,
            accuracy=accuracy,
            timeliness=timeliness,
            clinical_plausibility=clinical_plausibility,
        ),
        issues_detected=issues,
    )
