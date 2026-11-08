from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SignalStatus(StrEnum):
    NOT_CAPTURED = "not_captured"
    INCONCLUSIVE = "inconclusive"
    NO_CONCERNING_SIGNAL = "no_concerning_signal"
    CONCERNING = "concerning"


class Symptoms(BaseModel):
    model_config = ConfigDict(extra="forbid")

    balance_loss: bool = False
    vision_change: bool = False
    face_droop: bool = False
    arm_weakness: bool = False
    speech_difficulty: bool = False
    one_sided_numbness: bool = False
    confusion: bool = False
    severe_headache: bool = False
    nausea_or_vomiting: bool = False

    def any_reported(self) -> bool:
        return any(self.model_dump().values())


class ModelSignal(BaseModel):
    """A device-side measurement, never a diagnosis probability."""

    model_config = ConfigDict(extra="forbid")

    status: SignalStatus = SignalStatus.NOT_CAPTURED
    capture_quality: Annotated[float | None, Field(ge=0, le=1)] = None
    measurement_score: Annotated[float | None, Field(ge=0, le=1)] = None
    model_version: Annotated[str | None, Field(max_length=80)] = None


class ObservableSignals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    face_asymmetry: ModelSignal = Field(default_factory=ModelSignal)
    speech_change: ModelSignal = Field(default_factory=ModelSignal)
    arm_drift: ModelSignal = Field(default_factory=ModelSignal)
    eye_movement: ModelSignal = Field(default_factory=ModelSignal)
    capture_quality: SignalStatus = SignalStatus.NOT_CAPTURED

    def concerning_names(self) -> list[str]:
        labels = {
            "face_asymmetry": "possible facial asymmetry",
            "speech_change": "possible speech change",
            "arm_drift": "possible arm drift",
            "eye_movement": "possible eye-movement abnormality",
        }
        return [
            labels[name]
            for name in labels
            if getattr(self, name).status == SignalStatus.CONCERNING
        ]


class BaselineFeatures(BaseModel):
    """Derived client-side values only. Do not submit raw video or audio."""

    model_config = ConfigDict(extra="forbid")

    face_symmetry_index: Annotated[float, Field(ge=0, le=1)]
    smile_symmetry_index: Annotated[float, Field(ge=0, le=1)]
    eyebrow_symmetry_index: Annotated[float, Field(ge=0, le=1)]
    eye_closure_symmetry_index: Annotated[float, Field(ge=0, le=1)]
    speech_embedding: Annotated[list[float], Field(min_length=8, max_length=1024)]
    capture_device: Annotated[str, Field(min_length=1, max_length=120)]
    consent_to_store_features: bool

    @field_validator("speech_embedding")
    @classmethod
    def finite_embedding(cls, value: list[float]) -> list[float]:
        if any(not (-1_000_000 < item < 1_000_000) for item in value):
            raise ValueError("speech_embedding contains an invalid value")
        return value


class CreateBaselineRequest(BaselineFeatures):
    pass


class BaselineResponse(BaseModel):
    id: UUID
    created_at: datetime
    message: str


class AssessmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sudden_onset: bool
    symptoms: Symptoms = Field(default_factory=Symptoms)
    signals: ObservableSignals = Field(default_factory=ObservableSignals)
    symptoms_noticed_at: datetime | None = None
    last_known_well_at: datetime | None = None
    witness_name: Annotated[str | None, Field(max_length=100)] = None
    witness_phone: Annotated[str | None, Field(max_length=32)] = None
    taking_blood_thinners: bool | None = None
    location_label: Annotated[str | None, Field(max_length=240)] = None
    consent_to_store_assessment: bool = False

    @model_validator(mode="after")
    def timeline_is_valid(self) -> "AssessmentRequest":
        if (
            self.last_known_well_at
            and self.symptoms_noticed_at
            and self.last_known_well_at > self.symptoms_noticed_at
        ):
            raise ValueError("last_known_well_at cannot be later than symptoms_noticed_at")
        return self


class SafetyDecision(BaseModel):
    emergency_recommended: bool
    state: str
    reasons: list[str]
    safety_message: str
    quality_message: str | None = None


class EmergencyHandoff(BaseModel):
    assessment_id: UUID
    created_at: datetime
    symptoms_noticed_at: datetime | None
    last_known_well_at: datetime | None
    observed_signs: list[str]
    witness_name: str | None
    witness_phone: str | None
    taking_blood_thinners: bool | None
    location_label: str | None
    disclaimer: str


class AssessmentResponse(BaseModel):
    id: UUID
    decision: SafetyDecision
    handoff: EmergencyHandoff


class TrustedContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    phone_e164: Annotated[str, Field(pattern=r"^\+[1-9]\d{7,14}$")]
    consent_to_contact: bool


class TrustedContactResponse(BaseModel):
    id: UUID
    name: str
    phone_e164: str


class AlertPreviewRequest(BaseModel):
    assessment_id: UUID
    trusted_contact_id: UUID
    share_location: bool = False


class AlertPreviewResponse(BaseModel):
    id: UUID
    delivery_mode: str
    message: str
    disclaimer: str


class ModelPolicyResponse(BaseModel):
    raw_media_accepted: bool
    diagnostic_output_provided: bool
    emergency_call_placed_by_server: bool
    model_location: str
    safety_rule: str


class TaskName(StrEnum):
    EMERGENCY_CALL = "emergency_call"
    LAST_KNOWN_WELL = "last_known_well"
    FACE_VIDEO = "face_video"
    SPEECH_CLIP = "speech_clip"
    ARM_DRIFT = "arm_drift"
    EYE_GAZE = "eye_gaze"
    TRUSTED_CONTACT = "trusted_contact"
    HANDOFF = "handoff"


class ProtocolRequest(BaseModel):
    """Protocol state only; client-side models supply derived observations separately."""

    model_config = ConfigDict(extra="forbid")

    assessment: AssessmentRequest
    completed_tasks: list[TaskName] = Field(default_factory=list)

    @field_validator("completed_tasks")
    @classmethod
    def completed_tasks_are_unique(cls, value: list[TaskName]) -> list[TaskName]:
        if len(set(value)) != len(value):
            raise ValueError("completed_tasks must not contain duplicates")
        return value


class ProtocolResponse(BaseModel):
    mode: str
    emergency_recommended: bool
    next_task: TaskName | None
    remaining_tasks: list[TaskName]
    instructions: list[str]
    safety_message: str


class Modality(StrEnum):
    FACE = "face"
    SPEECH = "speech"
    ARM = "arm"
    EYE = "eye"


class TaskEventOutcome(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    RETAKE_REQUESTED = "retake_requested"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_to_store_session: bool
    label: Annotated[str | None, Field(max_length=80)] = None


class SessionResponse(BaseModel):
    id: UUID
    created_at: datetime
    label: str | None


class TaskEventRequest(BaseModel):
    """Privacy-preserving event metadata; raw media and embeddings are not accepted."""

    model_config = ConfigDict(extra="forbid")

    client_event_id: UUID
    task: TaskName
    outcome: TaskEventOutcome
    occurred_at: datetime
    signal: ModelSignal | None = None
    note: Annotated[str | None, Field(max_length=240)] = None


class TaskEventResponse(TaskEventRequest):
    id: UUID
    session_id: UUID
    created_at: datetime


class ModelManifest(BaseModel):
    model_id: str
    version: str
    modality: Modality
    input_contract: str
    derived_outputs: list[str]
    raw_media_leaves_device: bool
    medical_claim: str
    status: str


class DataExportResponse(BaseModel):
    exported_at: datetime
    schema_version: str
    baselines: list[dict]
    assessments: list[dict]
    trusted_contacts: list[dict]
    alerts: list[dict]
    sessions: list[dict]
    task_events: list[dict]
