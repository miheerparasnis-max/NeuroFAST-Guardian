from __future__ import annotations

from .schemas import AssessmentRequest, SafetyDecision, SignalStatus


EMERGENCY_MESSAGE = (
    "Possible sudden neurological warning signs were reported or observed. "
    "Call emergency services now. This tool does not diagnose or rule out stroke."
)


def decide(request: AssessmentRequest) -> SafetyDecision:
    """Apply deliberately conservative, non-diagnostic escalation rules."""
    reasons: list[str] = []
    concerning = request.signals.concerning_names()

    if request.sudden_onset and request.symptoms.any_reported():
        reasons.append("sudden stroke warning sign reported")

    if concerning:
        reasons.extend(concerning)

    quality_message = None
    if request.signals.capture_quality == SignalStatus.INCONCLUSIVE:
        quality_message = (
            "Capture quality was insufficient for interpretation. A poor-quality capture "
            "does not lower concern or exclude stroke."
        )

    if reasons:
        return SafetyDecision(
            emergency_recommended=True,
            state="emergency_recommended",
            reasons=reasons,
            safety_message=EMERGENCY_MESSAGE,
            quality_message=quality_message,
        )

    if request.sudden_onset:
        return SafetyDecision(
            emergency_recommended=True,
            state="emergency_recommended",
            reasons=["sudden symptom onset reported"],
            safety_message=(
                "Sudden neurological symptoms can be serious even when this capture is "
                "inconclusive. Call emergency services now."
            ),
            quality_message=quality_message,
        )

    return SafetyDecision(
        emergency_recommended=False,
        state="no_concerning_signal_captured",
        reasons=["no concerning observable signal was captured"],
        safety_message=(
            "No concerning observable signal was captured. This is not a medical "
            "clearance and does not rule out stroke. If symptoms are sudden or concerning, "
            "call emergency services."
        ),
        quality_message=quality_message,
    )
