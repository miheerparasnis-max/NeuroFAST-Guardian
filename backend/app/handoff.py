from __future__ import annotations

from typing import Iterable

from .safety import decide
from .schemas import (
    AssessmentRequest,
    AssessmentResponse,
    EmergencyHandoff,
    TaskEventRequest,
    TaskName,
)
from .storage import Storage


TASK_TO_SIGNAL = {
    TaskName.FACE_VIDEO: "face_asymmetry",
    TaskName.SPEECH_CLIP: "speech_change",
    TaskName.ARM_DRIFT: "arm_drift",
    TaskName.EYE_GAZE: "eye_movement",
}


def merge_session_observations(
    assessment: AssessmentRequest, task_events: Iterable[TaskEventRequest]
) -> AssessmentRequest:
    """Use the latest persisted measurement for each modality, never raw media."""
    merged = assessment.model_copy(deep=True)
    for event in task_events:
        signal_name = TASK_TO_SIGNAL.get(event.task)
        if signal_name and event.signal:
            setattr(merged.signals, signal_name, event.signal)
    return merged


def create_assessment_response(
    storage: Storage, owner_id: str, request: AssessmentRequest
) -> AssessmentResponse:
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
