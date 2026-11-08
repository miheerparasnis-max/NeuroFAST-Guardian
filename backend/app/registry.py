from __future__ import annotations

from .schemas import Modality, ModelManifest


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
