from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .handoff import create_assessment_response, merge_session_observations
from .protocol import next_protocol_step
from .registry import MODEL_REGISTRY
from .safety import decide
from .schemas import (
    AlertPreviewRequest,
    AlertPreviewResponse,
    AssessmentRequest,
    AssessmentResponse,
    BaselineResponse,
    CreateBaselineRequest,
    CreateSessionRequest,
    DataExportResponse,
    FinalizeSessionRequest,
    SessionHandoffResponse,
    ModelPolicyResponse,
    ProtocolRequest,
    ProtocolResponse,
    ModelManifest,
    SessionResponse,
    TaskEventRequest,
    TaskEventResponse,
    TrustedContactRequest,
    TrustedContactResponse,
)
from .security import FixedWindowRateLimiter, resolve_api_key_owner
from .settings import settings
from .storage import Storage, utcnow


app = FastAPI(
    title="NeuroFAST Guardian API",
    version="0.1.0",
    description=(
        "Hackathon prototype API. It is non-diagnostic and must not be used to delay "
        "emergency care."
    ),
)
logger = logging.getLogger("neurofast.api")
storage = Storage(settings.database_path)
rate_limiter = FixedWindowRateLimiter(settings.rate_limit_per_minute)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Demo-User-Id", "X-API-Key"],
)



@app.middleware("http")
async def enforce_transport_guardrails(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.request_max_bytes:
        return JSONResponse(status_code=413, content={"detail": "Request body exceeds configured limit."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.on_event("startup")
def startup() -> None:
    storage.initialize()


def authenticated_owner_id(
    x_api_key: Annotated[str | None, Header()] = None,
    x_demo_user_id: Annotated[str | None, Header()] = None,
) -> str:
    owner_id = resolve_api_key_owner(x_api_key, settings.api_keys)
    if settings.api_keys:
        if not owner_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Valid X-API-Key required.")
    elif settings.demo_mode:
        owner_id = x_demo_user_id
        if not owner_id or len(owner_id) > 100:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Demo-User-Id header is required in demo mode.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    if not rate_limiter.allow(owner_id):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded.")
    return owner_id


OwnerId = Annotated[str, Depends(authenticated_owner_id)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "demo" if settings.demo_mode else "configured"}


@app.get("/ready")
def ready() -> dict[str, str]:
    if not storage.is_ready():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable.")
    return {"status": "ready"}


@app.get("/v1/model-policy", response_model=ModelPolicyResponse)
def model_policy() -> ModelPolicyResponse:
    return ModelPolicyResponse(
        raw_media_accepted=False,
        diagnostic_output_provided=False,
        emergency_call_placed_by_server=False,
        model_location="Client device; backend receives derived measurements only.",
        safety_rule=(
            "Sudden reported symptoms or concerning observable signals recommend emergency "
            "care. No result rules out stroke."
        ),
    )


@app.post("/v1/protocol/next", response_model=ProtocolResponse)
def protocol_next(request: ProtocolRequest, owner_id: OwnerId) -> ProtocolResponse:
    """Return the next guided capture or emergency-handoff action.

    The owner header is required for a consistent API boundary even though this endpoint
    does not persist the request. The result is intentionally non-diagnostic.
    """
    _ = owner_id
    return next_protocol_step(request)


@app.get("/v1/model-registry", response_model=list[ModelManifest])
def model_registry() -> list[ModelManifest]:
    """Expose the exact prototype modality contracts to make model provenance reviewable."""
    return list(MODEL_REGISTRY)


@app.post("/v1/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(request: CreateSessionRequest, owner_id: OwnerId) -> SessionResponse:
    if not request.consent_to_store_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit consent is required before storing a task-event session.",
        )
    session_id, created_at = storage.create_session(owner_id, request)
    return SessionResponse(id=session_id, created_at=created_at, label=request.label)


@app.post(
    "/v1/sessions/{session_id}/events",
    response_model=TaskEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_task_event(
    session_id: UUID, request: TaskEventRequest, owner_id: OwnerId
) -> TaskEventResponse:
    if not storage.get_session(owner_id, session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    event_id, created_at, _created = storage.create_task_event(owner_id, session_id, request)
    return TaskEventResponse(
        id=event_id,
        session_id=session_id,
        created_at=created_at,
        **request.model_dump(),
    )


@app.get("/v1/sessions/{session_id}/events", response_model=list[TaskEventResponse])
def list_task_events(session_id: UUID, owner_id: OwnerId) -> list[TaskEventResponse]:
    if not storage.get_session(owner_id, session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return [
        TaskEventResponse(
            id=row["id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            **TaskEventRequest.model_validate_json(row["event_json"]).model_dump(),
        )
        for row in storage.list_task_events(owner_id, session_id)
    ]


@app.post(
    "/v1/sessions/{session_id}/finalize",
    response_model=SessionHandoffResponse,
    status_code=status.HTTP_201_CREATED,
)
def finalize_session(
    session_id: UUID, request: FinalizeSessionRequest, owner_id: OwnerId
) -> SessionHandoffResponse:
    """Compile stored derived observations with symptom/timeline context into a handoff."""
    if not storage.get_session(owner_id, session_id):
        raise HTTPException(status_code=404, detail="Session not found.")

    provenance = [
        TaskEventResponse(
            id=row["id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
            **TaskEventRequest.model_validate_json(row["event_json"]).model_dump(),
        )
        for row in storage.list_task_events(owner_id, session_id)
    ]
    merged = merge_session_observations(
        request.assessment,
        [
            TaskEventRequest(
                client_event_id=event.client_event_id,
                task=event.task,
                outcome=event.outcome,
                occurred_at=event.occurred_at,
                signal=event.signal,
                note=event.note,
            )
            for event in provenance
        ],
    )
    return SessionHandoffResponse(
        session_id=session_id,
        assessment=create_assessment_response(storage, owner_id, merged),
        provenance=provenance,
    )


@app.get("/v1/me/export", response_model=DataExportResponse)
def export_my_data(owner_id: OwnerId) -> DataExportResponse:
    """Portable copy of stored data for the authenticated demo identity."""
    return DataExportResponse(
        exported_at=utcnow(),
        schema_version="1.0",
        **storage.export_owner_data(owner_id),
    )


@app.post("/v1/baselines", response_model=BaselineResponse, status_code=status.HTTP_201_CREATED)
def create_baseline(request: CreateBaselineRequest, owner_id: OwnerId) -> BaselineResponse:
    if not request.consent_to_store_features:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit consent is required before storing baseline features.",
        )
    baseline_id, created_at = storage.create_baseline(owner_id, request)
    return BaselineResponse(
        id=baseline_id,
        created_at=created_at,
        message="Derived baseline features stored. Raw face video and audio are not accepted.",
    )


@app.post("/v1/assessments", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def create_assessment(request: AssessmentRequest, owner_id: OwnerId) -> AssessmentResponse:
    return create_assessment_response(storage, owner_id, request)


@app.post(
    "/v1/trusted-contacts",
    response_model=TrustedContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_trusted_contact(
    request: TrustedContactRequest, owner_id: OwnerId
) -> TrustedContactResponse:
    if not request.consent_to_contact:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit consent is required before adding a trusted contact.",
        )
    contact_id = storage.create_contact(owner_id, request)
    return TrustedContactResponse(id=contact_id, name=request.name, phone_e164=request.phone_e164)


@app.get("/v1/trusted-contacts", response_model=list[TrustedContactResponse])
def list_trusted_contacts(owner_id: OwnerId) -> list[TrustedContactResponse]:
    contacts = storage.list_contacts(owner_id)
    return [
        TrustedContactResponse(id=row["id"], name=row["name"], phone_e164=row["phone_e164"])
        for row in contacts
    ]


@app.post("/v1/alerts/preview", response_model=AlertPreviewResponse)
def preview_alert(request: AlertPreviewRequest, owner_id: OwnerId) -> AlertPreviewResponse:
    assessment = storage.get_assessment(owner_id, request.assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Stored assessment not found.")
    contact = storage.get_contact(owner_id, request.trusted_contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Trusted contact not found.")

    assessment_request = AssessmentRequest.model_validate_json(assessment["request_json"])
    details = [
        "Possible neurological emergency reported.",
        f"Symptoms noticed: {assessment_request.symptoms_noticed_at or 'unknown'}.",
        f"Last known well: {assessment_request.last_known_well_at or 'unknown'}.",
    ]
    if request.share_location and assessment_request.location_label:
        details.append(f"Location: {assessment_request.location_label}.")
    details.append("Please call or check on them. Emergency services should be contacted for sudden symptoms.")
    message = " ".join(details)
    alert_id = storage.save_alert(owner_id, request.assessment_id, request.trusted_contact_id, message)
    return AlertPreviewResponse(
        id=alert_id,
        delivery_mode="preview_only" if settings.demo_mode else "provider_not_configured",
        message=message,
        disclaimer=(
            "No SMS was sent by this endpoint. Production notifications require a verified "
            "provider, consent, rate limits, audit logging, and legal review."
        ),
    )


@app.delete("/v1/me/data", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_data(owner_id: OwnerId) -> Response:
    storage.delete_owner_data(owner_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
