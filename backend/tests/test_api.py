from fastapi.testclient import TestClient

from app.main import app, storage


def setup_function() -> None:
    storage.initialize()
    storage.delete_owner_data("test-user")


def test_assessment_requires_demo_identity() -> None:
    with TestClient(app) as client:
        response = client.post("/v1/assessments", json={"sudden_onset": True})
    assert response.status_code == 401


def test_assessment_never_returns_a_clearance() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/assessments",
            headers={"X-Demo-User-Id": "test-user"},
            json={"sudden_onset": False, "consent_to_store_assessment": True},
        )
    assert response.status_code == 201
    body = response.json()
    assert body["decision"]["state"] == "no_concerning_signal_captured"
    assert "does not rule out stroke" in body["decision"]["safety_message"]


def test_contact_requires_explicit_consent() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/trusted-contacts",
            headers={"X-Demo-User-Id": "test-user"},
            json={"name": "Alex", "phone_e164": "+14155552671", "consent_to_contact": False},
        )
    assert response.status_code == 400
