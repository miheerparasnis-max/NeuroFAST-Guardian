from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .protocol import next_protocol_step
from .safety import decide
from .schemas import (
    AlertPreviewRequest,
    AlertPreviewResponse,
    AssessmentRequest,
    AssessmentResponse,
    BaselineResponse,
    CreateBaselineRequest,
    EmergencyHandoff,
    ModelPolicyResponse,
    ProtocolRequest,
    ProtocolResponse,
    TrustedContactRequest,
    TrustedContactResponse,
)
from .settings import settings
from .storage import Storage


app = FastAPI(
    title="NeuroFAST Guardian API",
    version="0.1.0",
    description=(
        "Hackathon prototype API. It is non-diagnostic and must not be used to delay "
        "emergency care."
    ),
)
storage = Storage(settings.database_path)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Demo-User-Id"],
)


@app.on_event("startup")
def startup() -> None:
    storage.initialize()


def demo_owner_id(
    x_demo_user_id: Annotated[str | None, Header()] = None,
) -> str:
    if not x_demo_user_id or len(x_demo_user_id) > 100:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Demo-User-Id header is required for the prototype.",
        )
    return x_demo_user_id


OwnerId = Annotated[str, Depends(demo_owner_id)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "demo" if settings.demo_mode else "configured"}


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
    decision = decide(request)
    assessment_id, created_at = storage.create_assessment(owner_id, request, decision)
    handoff = EmergencyHandoff(
        assessment_id=assessment_id,
        created_at=created_at,
        symptoms_noticed_at=request.symptoms_noticed_at,
        last_known_well_at=request.last_known_well_at,
        observed_signs=decision.reasons.copy(),
        witness_name=request.witness_name,
        witness_phone=request.witness_phone,
        taking_blood_thinners=request.taking_blood_thinners,
        location_label=request.location_label,
        disclaimer=(
            "Prototype only. This handoff summarizes reported and device-observed signals; "
            "it does not diagnose or rule out stroke."
        ),
    )
    return AssessmentResponse(id=assessment_id, decision=decision, handoff=handoff)


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
