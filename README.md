# NeuroFAST Guardian

Safety-first backend for the NeuroFAST Guardian hackathon prototype. It stores consented baseline feature summaries, combines client-side observable-signal measurements with symptom reports, creates emergency handoffs, and produces demo-safe trusted-contact alerts.

> **Not a medical device.** This prototype does not diagnose, rule out, or predict stroke. A sudden symptom must always keep emergency options visible, even if no model signal is captured.

## What the API does

- Stores only derived baseline features, not raw face video or audio.
- Combines face, speech, arm, eye, and symptom signals using conservative safety rules.
- Returns `emergency_recommended` when a sudden symptom or concerning observable signal is present.
- Creates a time-stamped emergency handoff card.
- Produces preview-only trusted-contact notifications unless an approved provider is configured.
- Supports deleting a user's stored baselines, assessments, contacts, alerts, sessions, and task-event history.
- Persists consented modality provenance with idempotent client event IDs, so retries cannot duplicate an event.
- Exposes a versioned, reviewable model registry rather than hiding model behavior behind an unexplained score.
- Provides a portable user-data export.
- Orchestrates an adaptive face, speech, arm, and eye capture sequence without using any model score as a severity grade.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

For a browser frontend, configure `NEUROFAST_CORS_ORIGINS` with only the trusted frontend origins. The development defaults are `http://localhost:3000` and `http://localhost:5173`.

## Demo identity

For the hackathon prototype, every user-owned endpoint requires an `X-Demo-User-Id` header. This is **not authentication** and must be replaced with real authentication before deployment.

```bash
curl -X POST http://127.0.0.1:8000/v1/assessments \
  -H 'Content-Type: application/json' \
  -H 'X-Demo-User-Id: demo-user-001' \
  -d '{
    "sudden_onset": true,
    "symptoms": {"face_droop": true, "speech_difficulty": true},
    "signals": {
      "face_asymmetry": {"status": "concerning", "capture_quality": 0.94, "measurement_score": 0.78, "model_version": "face-landmarks-0.1"},
      "speech_change": {"status": "concerning", "capture_quality": 0.88, "measurement_score": 0.72, "model_version": "speech-features-0.1"}
    },
    "last_known_well_at": "2026-11-08T02:50:00Z",
    "symptoms_noticed_at": "2026-11-08T03:10:00Z"
  }'
```

## Safety rules

- A sudden reported warning sign always recommends emergency care.
- A concerning face, speech, arm, or eye signal always recommends emergency care.
- Inconclusive or poor-quality capture never produces a reassuring result.
- The API never returns `stroke_negative`, `safe`, or a stroke probability.
- Emergency-service calling is deliberately client initiated. The backend does not place calls.

## API surface

- `GET /health` - service status.
- `GET /v1/model-policy` - exposes the non-diagnostic privacy and safety contract.
- `POST /v1/protocol/next` - returns the next guided capture step or immediately prioritizes emergency handoff.
- `GET /v1/model-registry` - documents every modality's input contract, derived output, and non-diagnostic claim.
- `POST /v1/sessions` - creates a consented evidence-capture session.
- `POST /v1/sessions/{session_id}/events` and `GET /v1/sessions/{session_id}/events` - record and retrieve idempotent modality events.
- `POST /v1/baselines` - stores consented derived baseline features only.
- `POST /v1/assessments` - produces a conservative escalation decision and handoff.
- `POST /v1/trusted-contacts` and `GET /v1/trusted-contacts` - manages consented contacts.
- `POST /v1/alerts/preview` - records and previews an alert; never sends SMS in demo mode.
- `GET /v1/me/export` - returns a portable copy of data owned by the demo user.
- `DELETE /v1/me/data` - deletes all data owned by the demo user.

`POST /v1/alerts/preview` requires that the assessment was created with `consent_to_store_assessment: true`; this prevents storing an emergency event merely to send an alert without the user's explicit consent.



## Backend data and model boundaries

- The server accepts no image, video, audio, or raw voice embedding upload.
- A modality event contains only a client-generated status, capture-quality measurement, optional derived score, model version, and task timestamp.
- Session event writes use a client-generated UUID. Repeating a request with the same UUID returns the original event instead of creating a duplicate.
- The model registry makes the claimed inputs and outputs inspectable. Every listed module is explicitly marked as a prototype observation tool, not a clinical classifier.
- The database keeps a minimal audit record for storage actions, while data export and deletion remain available to the data owner.
- This demo identity header is not production authentication. Before real-world use, add verified authentication, encryption at rest, secure secrets, audit retention policy, consent review, provider integration safeguards, and clinical/legal validation.

## Adaptive protocol

The frontend sends derived measurements and the tasks already completed to `POST /v1/protocol/next`.

- If a sudden symptom is reported or any observable signal is concerning, the next task is always `emergency_call`. The remaining items collect last-known-well time and a handoff without delaying the call.
- If a capture is inconclusive and no acute warning sign is present, the protocol requests a retake of that specific task. It never converts a poor capture into reassurance.
- Otherwise, the protocol sequences face video, speech clip, arm drift, eye gaze, then the handoff card.
- The endpoint has no "severity" field, no prediction probability, and no "wait-and-see" path.

## Tests

```bash
cd backend
pytest
```
