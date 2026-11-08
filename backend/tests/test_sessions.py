from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, storage


def setup_function(_: object) -> None:
    storage.initialize()
    storage.delete_owner_data("session-user")


def test_session_event_is_idempotent_and_exportable() -> None:
    headers = {"X-Demo-User-Id": "session-user"}
    event_id = str(uuid4())

    with TestClient(app) as client:
        session = client.post(
            "/v1/sessions",
            headers=headers,
            json={"consent_to_store_session": True, "label": "guided demo"},
        )
        assert session.status_code == 201
        session_id = session.json()["id"]

        payload = {
            "client_event_id": event_id,
            "task": "face_video",
            "outcome": "completed",
            "occurred_at": "2026-11-08T12:00:00Z",
            "signal": {
                "status": "no_concerning_signal",
                "capture_quality": 0.92,
                "measurement_score": 0.08,
                "model_version": "face-landmark-observer@0.1.0",
            },
        }
        first = client.post(f"/v1/sessions/{session_id}/events", headers=headers, json=payload)
        second = client.post(f"/v1/sessions/{session_id}/events", headers=headers, json=payload)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

        events = client.get(f"/v1/sessions/{session_id}/events", headers=headers)
        assert events.status_code == 200
        assert len(events.json()) == 1

        exported = client.get("/v1/me/export", headers=headers)
        assert exported.status_code == 200
        assert len(exported.json()["sessions"]) == 1
        assert len(exported.json()["task_events"]) == 1


def test_model_registry_never_claims_diagnosis() -> None:
    with TestClient(app) as client:
        response = client.get("/v1/model-registry")
    assert response.status_code == 200
    assert len(response.json()) == 4
    assert all("not a stroke diagnosis" in item["medical_claim"] for item in response.json())
