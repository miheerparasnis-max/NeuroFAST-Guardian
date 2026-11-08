from app.safety import decide
from app.schemas import AssessmentRequest, ModelSignal, ObservableSignals, SignalStatus, Symptoms


def test_sudden_symptom_always_recommends_emergency() -> None:
    decision = decide(
        AssessmentRequest(sudden_onset=True, symptoms=Symptoms(face_droop=True))
    )
    assert decision.emergency_recommended is True
    assert decision.state == "emergency_recommended"


def test_concerning_signal_recommends_emergency_without_symptom_report() -> None:
    decision = decide(
        AssessmentRequest(
            sudden_onset=False,
            signals=ObservableSignals(
                face_asymmetry=ModelSignal(status=SignalStatus.CONCERNING)
            ),
        )
    )
    assert decision.emergency_recommended is True
    assert "possible facial asymmetry" in decision.reasons


def test_no_signal_is_not_presented_as_clearance() -> None:
    decision = decide(AssessmentRequest(sudden_onset=False))
    assert decision.emergency_recommended is False
    assert "does not rule out stroke" in decision.safety_message


def test_inconclusive_quality_does_not_override_sudden_symptoms() -> None:
    decision = decide(
        AssessmentRequest(
            sudden_onset=True,
            symptoms=Symptoms(speech_difficulty=True),
            signals=ObservableSignals(capture_quality=SignalStatus.INCONCLUSIVE),
        )
    )
    assert decision.emergency_recommended is True
    assert decision.quality_message is not None
