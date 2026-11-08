from __future__ import annotations

from .schemas import Modality, ModelManifest, ObservableSignals, SignalStatus


MODEL_REGISTRY = (
    ModelManifest(
        model_id="face-landmark-observer",
        version="0.1.0",
        modality=Modality.FACE,
        input_contract="Client-side guided face video; server receives only status, quality, and derived score.",
        derived_outputs=["capture_quality", "facial_asymmetry_measurement", "status"],
        raw_media_leaves_device=False,
        medical_claim="Observation support only; not a stroke diagnosis or exclusion.",
        status="prototype",
    ),
    ModelManifest(
        model_id="speech-feature-observer",
        version="0.1.0",
        modality=Modality.SPEECH,
        input_contract="Client-side prompted speech capture; server receives only status, quality, and derived score.",
        derived_outputs=["capture_quality", "speech_change_measurement", "status"],
        raw_media_leaves_device=False,
        medical_claim="Observation support only; not a stroke diagnosis or exclusion.",
        status="prototype",
    ),
    ModelManifest(
        model_id="arm-pose-observer",
        version="0.1.0",
        modality=Modality.ARM,
        input_contract="Client-side pose tracking during a guided arm task; no video upload.",
        derived_outputs=["capture_quality", "arm_drift_measurement", "status"],
        raw_media_leaves_device=False,
        medical_claim="Observation support only; not a stroke diagnosis or exclusion.",
        status="prototype",
    ),
    ModelManifest(
        model_id="eye-motion-observer",
        version="0.1.0",
        modality=Modality.EYE,
        input_contract="Client-side guided visual task; no video upload.",
        derived_outputs=["capture_quality", "eye_movement_measurement", "status"],
        raw_media_leaves_device=False,
        medical_claim="Observation support only; not a stroke diagnosis or exclusion.",
        status="prototype",
    ),
)


TASK_TO_MODALITY = {
    "face_video": Modality.FACE,
    "speech_clip": Modality.SPEECH,
    "arm_drift": Modality.ARM,
    "eye_gaze": Modality.EYE,
}


def validate_registered_signal(task: str, model_version: str | None) -> None:
    """Reject unregistered model provenance for a modality measurement."""
    expected_modality = TASK_TO_MODALITY.get(task)
    if expected_modality is None:
        return
    if not model_version:
        raise ValueError("A registered model_version is required for a modality measurement.")
    registered = {
        f"{item.model_id}@{item.version}"
        for item in MODEL_REGISTRY
        if item.modality == expected_modality
    }
    if model_version not in registered:
        raise ValueError(
            f"Unregistered model_version for {expected_modality}: use one of {sorted(registered)}"
        )


def validate_observable_signals(signals: ObservableSignals) -> None:
    """Require registered provenance for every client-model observation in an assessment."""
    field_to_task = {
        "face_asymmetry": "face_video",
        "speech_change": "speech_clip",
        "arm_drift": "arm_drift",
        "eye_movement": "eye_gaze",
    }
    for field_name, task in field_to_task.items():
        signal = getattr(signals, field_name)
        if signal.status != SignalStatus.NOT_CAPTURED:
            validate_registered_signal(task, signal.model_version)
