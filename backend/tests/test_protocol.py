from app.protocol import next_protocol_step
from app.schemas import ProtocolRequest, TaskName


def test_sudden_symptom_prioritizes_emergency_call() -> None:
    result = next_protocol_step(
        ProtocolRequest.model_validate(
            {
                "assessment": {
                    "sudden_onset": True,
                    "symptoms": {"speech_difficulty": True},
                }
            }
        )
    )
    assert result.mode == "emergency_handoff"
    assert result.next_task == TaskName.EMERGENCY_CALL
    assert TaskName.LAST_KNOWN_WELL in result.remaining_tasks


def test_inconclusive_capture_requests_retake_without_clearance() -> None:
    result = next_protocol_step(
        ProtocolRequest.model_validate(
            {
                "assessment": {
                    "sudden_onset": False,
                    "signals": {
                        "face_asymmetry": {"status": "inconclusive", "capture_quality": 0.2}
                    },
                }
            }
        )
    )
    assert result.mode == "guided_capture"
    assert result.next_task == TaskName.FACE_VIDEO
    assert "does not provide reassurance" in result.instructions[1]


def test_routine_path_sequences_all_modalities_then_handoff() -> None:
    request = ProtocolRequest.model_validate({"assessment": {"sudden_onset": False}})
    assert next_protocol_step(request).next_task == TaskName.FACE_VIDEO

    request.completed_tasks = [
        TaskName.FACE_VIDEO,
        TaskName.SPEECH_CLIP,
        TaskName.ARM_DRIFT,
        TaskName.EYE_GAZE,
    ]
    assert next_protocol_step(request).next_task == TaskName.HANDOFF
