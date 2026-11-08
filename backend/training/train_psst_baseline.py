"""Train a subject-held-out post-stroke speech correctness research baseline.

This models item correctness within the public PSST task. It is not a stroke
classifier and its output must not be used for triage or clinical decisions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


FEATURES = ("duration_seconds", "rms", "zero_crossing_rate")


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-max(-30, min(30, value))))


def is_test_subject(subject_id: str) -> bool:
    return int(hashlib.sha256(subject_id.encode()).hexdigest(), 16) % 5 == 0


def metrics(rows: list[dict]) -> dict[str, float | int]:
    tp = sum(row["label"] == 1 and row["score"] >= 0.5 for row in rows)
    fp = sum(row["label"] == 0 and row["score"] >= 0.5 for row in rows)
    tn = sum(row["label"] == 0 and row["score"] < 0.5 for row in rows)
    fn = sum(row["label"] == 1 and row["score"] < 0.5 for row in rows)
    return {
        "records": len(rows),
        "subjects": len({row["subject_id"] for row in rows}),
        "accuracy": (tp + tn) / max(1, len(rows)),
        "sensitivity_for_correctness": tp / max(1, tp + fn),
        "specificity_for_incorrectness": tn / max(1, tn + fp),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--model-output", required=True, type=Path)
    parser.add_argument("--predictions-output", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=500)
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = [
            {
                "subject_id": row["subject_id"],
                "label": int(row["correctness_label"]),
                "features": [float(row[name]) for name in FEATURES],
            }
            for row in csv.DictReader(handle)
        ]
    train = [row for row in rows if not is_test_subject(row["subject_id"])]
    test = [row for row in rows if is_test_subject(row["subject_id"])]
    means = [sum(row["features"][i] for row in train) / len(train) for i in range(len(FEATURES))]
    deviations = [
        max(1e-9, (sum((row["features"][i] - means[i]) ** 2 for row in train) / len(train)) ** 0.5)
        for i in range(len(FEATURES))
    ]

    def scaled(row: dict) -> list[float]:
        return [(value - means[i]) / deviations[i] for i, value in enumerate(row["features"])]

    weights = [0.0] * len(FEATURES)
    bias, learning_rate = 0.0, 0.08
    for _ in range(args.epochs):
        gradient = [0.0] * len(FEATURES)
        bias_gradient = 0.0
        for row in train:
            values = scaled(row)
            error = sigmoid(bias + sum(weight * value for weight, value in zip(weights, values))) - row["label"]
            for i, value in enumerate(values):
                gradient[i] += error * value
            bias_gradient += error
        for i in range(len(weights)):
            weights[i] -= learning_rate * gradient[i] / len(train)
        bias -= learning_rate * bias_gradient / len(train)

    predictions = []
    for row in rows:
        values = scaled(row)
        predictions.append(
            {
                "subject_id": row["subject_id"],
                "label": row["label"],
                "score": sigmoid(bias + sum(weight * value for weight, value in zip(weights, values))),
                "split": "test" if is_test_subject(row["subject_id"]) else "train",
            }
        )
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.write_text(json.dumps({
        "model_type": "logistic_regression",
        "research_target": "PSST item correctness",
        "clinical_use": "prohibited",
        "features": FEATURES,
        "means": means,
        "standard_deviations": deviations,
        "weights": weights,
        "bias": bias,
        "test_metrics": metrics([row for row in predictions if row["split"] == "test"]),
    }, indent=2), encoding="utf-8")
    with args.predictions_output.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=("subject_id", "label", "score", "split"))
        writer.writeheader()
        writer.writerows(predictions)
