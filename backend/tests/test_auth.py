"""Tests for API key authentication.

Verifies that protected endpoints reject missing/wrong keys and accept correct ones.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_PAYLOAD = {
    "patient_context": {"age": 67, "conditions": ["Hypertension"], "recent_labs": {"eGFR": 60}},
    "sources": [
        {
            "system": "Hospital EHR",
            "medication": "Metformin 500mg twice daily",
            "last_updated": "2025-01-20",
            "source_reliability": "high",
        }
    ],
}


def test_reconcile_rejects_missing_api_key():
    response = client.post("/api/reconcile/medication", json=VALID_PAYLOAD)
    assert response.status_code == 401


def test_reconcile_rejects_wrong_api_key():
    response = client.post(
        "/api/reconcile/medication",
        json=VALID_PAYLOAD,
        headers={"x-api-key": "wrong-key"},
    )
    assert response.status_code == 401


def test_reconcile_accepts_correct_api_key():
    response = client.post(
        "/api/reconcile/medication",
        json=VALID_PAYLOAD,
        headers={"x-api-key": "demo-key"},
    )
    assert response.status_code == 200
    assert "reconciled_medication" in response.json()
