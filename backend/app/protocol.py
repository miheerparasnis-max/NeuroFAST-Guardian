from __future__ import annotations

from .safety import decide
from .schemas import AssessmentRequest, ProtocolRequest, ProtocolResponse, SignalStatus, TaskName


TASK_ORDER = (
    TaskName.FACE_VIDEO,
    TaskName.SPEECH_CLIP,
    TaskName.ARM_DRIFT,
    TaskName.EYE_GAZE,
    TaskName.HANDOFF,
)

RETAKE_TASKS = {
    "face_asymmetry": TaskName.FACE_VIDEO,
    "speech_change": TaskName.SPEECH_CLIP,
    "arm_drift": TaskName.ARM_DRIFT,
    "eye_movement": TaskName.EYE_GAZE,
}


def next_protocol_step(request: ProtocolRequest) -> ProtocolResponse:
    """Choose a capture step without using AI output to grade medical severity."""
    assessment: AssessmentRequest = request.assessment
    decision = decide(assessment)

    if decision.emergency_recommended:
        return ProtocolResponse(
            mode="emergency_handoff",
            emergency_recommended=True,
            next_task=TaskName.EMERGENCY_CALL,
            remaining_tasks=[
                TaskName.LAST_KNOWN_WELL,
                TaskName.TRUSTED_CONTACT,
                TaskName.HANDOFF,
            ],
            instructions=[
                "Call local emergency services now.",
                "Record the last-known-well time if it is available.",
                "Keep the person safe and follow dispatcher instructions.",
                "Do not let additional app tasks delay the emergency call.",
            ],
            safety_message=decision.safety_message,
        )

    completed = set(request.completed_tasks)
    for signal_name, task in RETAKE_TASKS.items():
        signal = getattr(assessment.signals, signal_name)
        if signal.status == SignalStatus.INCONCLUSIVE and task not in completed:
            return ProtocolResponse(
                mode="guided_capture",
                emergency_recommended=False,
                next_task=task,
                remaining_tasks=[task, *[item for item in TASK_ORDER if item != task]],
                instructions=[
                    "The previous capture was not usable. Retake this guided task in good lighting and a quiet setting.",
                    "An inconclusive capture does not provide reassurance or rule out stroke.",
                ],
                safety_message=decision.safety_message,
            )

    for task in TASK_ORDER:
        if task not in completed:
            return ProtocolResponse(
                mode="guided_capture",
                emergency_recommended=False,
                next_task=task,
                remaining_tasks=[item for item in TASK_ORDER if item not in completed],
                instructions=[
                    "Complete this optional guided measurement.",
                    "Stop and seek emergency help immediately if sudden neurological symptoms occur.",
                ],
                safety_message=decision.safety_message,
            )

    return ProtocolResponse(
        mode="complete",
        emergency_recommended=False,
        next_task=None,
        remaining_tasks=[],
        instructions=[
            "Capture sequence complete.",
            "This result is not a medical clearance and does not rule out stroke.",
        ],
        safety_message=decision.safety_message,
    )
