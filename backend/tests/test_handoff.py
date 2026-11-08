from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, storage


def setup_function(_: object) -> None:
    storage.initialize()
    storage.delete_owner_data("handoff-user")


def test_finalize_session_uses_latest_persisted_modality_signal() -> None:
    headers = {"X-Demo-User-Id": "handoff-user"}
    with TestClient(app) as client:
        session = client.post(
            "/v1/sessions",
            headers=headers,
            json={"consent_to_store_session": True},
        )
        session_id = session.json()["id"]
        event = {
            "client_event_id": str(uuid4()),
            "task": "face_video",
            "outcome": "completed",
            "occurred_at": "2026-11-08T12:00:00Z",
            "signal": {
                "status": "concerning",
                "capture_quality": 0.93,
                "measurement_score": 0.8,
                "model_version": "face-landmark-observer@0.1.0",
            },
        }
        assert client.post(f"/v1/sessions/{session_id}/events", headers=headers, json=event).status_code == 201
        finalized = client.post(
            f"/v1/sessions/{session_id}/finalize",
            headers=headers,
            json={
                "assessment": {
                    "sudden_onset": False,
                    "consent_to_store_assessment": True,
                }
            },
        )

    assert finalized.status_code == 201
    body = finalized.json()
    assert body["assessment"]["decision"]["emergency_recommended"] is True
    assert "possible facial asymmetry" in body["assessment"]["decision"]["reasons"]
    assert len(body["provenance"]) == 1
