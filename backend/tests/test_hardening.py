from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, storage


def setup_function(_: object) -> None:
    storage.initialize()
    storage.delete_owner_data("hardening-user")


def test_conflicting_idempotency_key_is_rejected() -> None:
    headers = {"X-Demo-User-Id": "hardening-user"}
    client_event_id = str(uuid4())
    with TestClient(app) as client:
        session = client.post("/v1/sessions", headers=headers, json={"consent_to_store_session": True})
        session_id = session.json()["id"]
        first = {
            "client_event_id": client_event_id,
            "task": "face_video",
            "outcome": "completed",
            "occurred_at": "2026-11-08T12:00:00Z",
            "signal": {
                "status": "no_concerning_signal",
                "model_version": "face-landmark-observer@0.1.0",
            },
        }
        assert client.post(f"/v1/sessions/{session_id}/events", headers=headers, json=first).status_code == 201
        conflict = {**first, "note": "different content"}
        assert client.post(f"/v1/sessions/{session_id}/events", headers=headers, json=conflict).status_code == 409


def test_unregistered_model_provenance_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/v1/assessments",
            headers={"X-Demo-User-Id": "hardening-user"},
            json={
                "sudden_onset": False,
                "signals": {
                    "face_asymmetry": {
                        "status": "no_concerning_signal",
                        "model_version": "made-up-model@9.9.9",
                    }
                },
            },
        )
    assert response.status_code == 422
