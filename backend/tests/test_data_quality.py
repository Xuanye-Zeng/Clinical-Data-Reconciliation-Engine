from datetime import date

from app.models.data_quality import DataQualityRequest, Demographics, VitalSigns
from app.services.data_quality_service import validate_data_quality


def test_data_quality_flags_implausible_blood_pressure():
    payload = DataQualityRequest(
        demographics=Demographics(name="John Doe", dob=date(1955, 3, 15), gender="M"),
        medications=["Metformin 500mg"],
        allergies=[],
        conditions=["Type 2 Diabetes"],
        vital_signs=VitalSigns(blood_pressure="340/180", heart_rate=72),
        last_updated=date(2024, 6, 15),
    )

    result = validate_data_quality(payload)

    assert result.overall_score < 90
    assert any(issue.field == "vital_signs.blood_pressure" for issue in result.issues_detected)


def test_data_quality_flags_stale_records_when_last_updated_missing():
    payload = DataQualityRequest(
        demographics=Demographics(name="John Doe", dob=date(1955, 3, 15), gender="M"),
        medications=["Metformin 500mg"],
        allergies=["Penicillin"],
        conditions=["Type 2 Diabetes"],
        vital_signs=VitalSigns(blood_pressure="120/80", heart_rate=72),
        last_updated=None,
    )

    result = validate_data_quality(payload)

    assert result.breakdown.timeliness == 40
    assert any(issue.field == "last_updated" for issue in result.issues_detected)


def test_data_quality_reduces_accuracy_for_unexpected_gender_value():
    payload = DataQualityRequest(
        demographics=Demographics(name="John Doe", dob=date(1955, 3, 15), gender="UnknownCode"),
        medications=["Metformin 500mg"],
        allergies=["Penicillin"],
        conditions=["Type 2 Diabetes"],
        vital_signs=VitalSigns(blood_pressure="120/80", heart_rate=72),
        last_updated=date.today(),
    )

    result = validate_data_quality(payload)

    assert result.breakdown.accuracy == 90
    assert any(issue.field == "demographics.gender" for issue in result.issues_detected)
