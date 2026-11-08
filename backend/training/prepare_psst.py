"""Convert the public PSST archive into derived, non-identifying speech features.

Output is a CSV suitable for exploratory research. It does not generate a stroke
prediction label and must not be used for clinical claims.
"""

from __future__ import annotations

import argparse
import array
import csv
import io
import tarfile
import wave
from pathlib import Path


def wav_features(payload: bytes) -> dict[str, float]:
    with wave.open(io.BytesIO(payload), "rb") as audio:
        if audio.getsampwidth() != 2:
            raise ValueError("Only 16-bit PCM audio is supported")
        frames, rate = audio.getnframes(), audio.getframerate()
        samples = array.array("h", audio.readframes(frames))
    if not samples:
        return {"duration_seconds": 0.0, "rms": 0.0, "zero_crossing_rate": 0.0}
    normalized = [value / 32768 for value in samples]
    rms = (sum(value * value for value in normalized) / len(normalized)) ** 0.5
    crossings = sum(
        (normalized[index - 1] >= 0) != (normalized[index] >= 0)
        for index in range(1, len(normalized))
    )
    return {
        "duration_seconds": frames / rate,
        "rms": rms,
        "zero_crossing_rate": crossings / max(1, len(normalized) - 1),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with tarfile.open(args.archive, "r:gz") as archive:
        labels_member = next(item for item in archive.getmembers() if item.name.endswith("utterances.tsv"))
        labels = list(csv.DictReader(io.TextIOWrapper(archive.extractfile(labels_member), encoding="utf-8"), delimiter="\t"))
        members = {
            "/".join(item.name.lstrip("./").split("/")[1:]): item
            for item in archive.getmembers()
            if item.name.endswith(".wav")
        }
        rows = []
        for label in labels:
            member = members.get(label["filename"].lstrip("./"))
            if not member:
                continue
            features = wav_features(archive.extractfile(member).read())
            rows.append(
                {
                    "subject_id": label["session"],
                    "utterance_id": label["utterance_id"],
                    "correctness_label": int(label["correctness"].upper() == "TRUE"),
                    "aphasia_quotient": label["aq_index"],
                    **features,
                }
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys() if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} derived feature rows to {args.output}")
