from datetime import date

import pytest
from pydantic import ValidationError

from app.models.reconcile import MedicationSource, PatientContext, ReconcileMedicationRequest
from app.services.reconciliation_service import reconcile_medication


def test_reconcile_prefers_recent_high_reliability_record():
    payload = ReconcileMedicationRequest(
        patient_context=PatientContext(age=67, conditions=["Hypertension"], recent_labs={"eGFR": 60}),
        sources=[
            MedicationSource(
                system="Hospital EHR",
                medication="Metformin 1000mg twice daily",
                last_updated=date(2024, 10, 15),
                source_reliability="high",
            ),
            MedicationSource(
                system="Primary Care",
                medication="Metformin 500mg twice daily",
                last_updated=date.today(),
                source_reliability="high",
            ),
        ],
    )

    result = reconcile_medication(payload)

    assert result.reconciled_medication == "Metformin 500mg twice daily"
    assert result.confidence_score >= 0.7


def test_reconcile_marks_review_for_high_dose_with_low_egfr():
    payload = ReconcileMedicationRequest(
        patient_context=PatientContext(age=67, conditions=["Diabetes"], recent_labs={"eGFR": 40}),
        sources=[
            MedicationSource(
                system="Hospital EHR",
                medication="Metformin 1000mg twice daily",
                last_updated=date.today(),
                source_reliability="high",
            ),
        ],
    )

    result = reconcile_medication(payload)

    assert result.clinical_safety_check == "REVIEW"
    assert any("renal function" in action for action in result.recommended_actions)


def test_reconcile_request_requires_at_least_one_source():
    with pytest.raises(ValidationError):
        ReconcileMedicationRequest(
            patient_context=PatientContext(age=67, conditions=["Hypertension"], recent_labs={"eGFR": 60}),
            sources=[],
        )


def test_reconcile_handles_string_egfr_without_crashing():
    payload = ReconcileMedicationRequest(
        patient_context=PatientContext(age=67, conditions=["Diabetes"], recent_labs={"eGFR": "40"}),
        sources=[
            MedicationSource(
                system="Hospital EHR",
                medication="Metformin 1000mg twice daily",
                last_updated=date.today(),
                source_reliability="high",
            ),
        ],
    )

    result = reconcile_medication(payload)

    assert result.clinical_safety_check == "REVIEW"
    assert result.reconciled_medication == "Metformin 1000mg twice daily"


def test_reconcile_handles_non_numeric_egfr_gracefully():
    payload = ReconcileMedicationRequest(
        patient_context=PatientContext(age=67, conditions=["Diabetes"], recent_labs={"eGFR": "not-a-number"}),
        sources=[
            MedicationSource(
                system="Hospital EHR",
                medication="Metformin 1000mg twice daily",
                last_updated=date.today(),
                source_reliability="high",
            ),
        ],
    )

    result = reconcile_medication(payload)

    assert result.clinical_safety_check == "PASSED"
    assert result.reconciled_medication == "Metformin 1000mg twice daily"
