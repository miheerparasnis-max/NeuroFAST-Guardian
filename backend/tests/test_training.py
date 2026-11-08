import io
import wave

from training.prepare_psst import wav_features


def test_wav_features_extracts_duration_and_signal_measurements() -> None:
    payload = io.BytesIO()
    with wave.open(payload, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes((1000).to_bytes(2, "little", signed=True) * 16000)

    features = wav_features(payload.getvalue())
    assert features["duration_seconds"] == 1.0
    assert features["rms"] > 0
