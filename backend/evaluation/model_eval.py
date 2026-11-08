"""Offline, subject-level evaluation for derived model outputs.

Input CSV columns: subject_id,label,score,split[,subgroup]
- label must be 0 or 1.
- score must be a [0, 1] derived model score.
- each subject must appear in one split only.
This reports engineering metrics. It does not create a clinical validation claim.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist


def proportion_ci(successes: int, total: int, confidence: float = 0.95) -> dict[str, float | None]:
    if total == 0:
        return {"estimate": None, "lower": None, "upper": None}
    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return {"estimate": p, "lower": max(0.0, center - margin), "upper": min(1.0, center + margin)}


def metrics(rows: list[dict], threshold: float) -> dict:
    tp = sum(row["label"] == 1 and row["score"] >= threshold for row in rows)
    fp = sum(row["label"] == 0 and row["score"] >= threshold for row in rows)
    tn = sum(row["label"] == 0 and row["score"] < threshold for row in rows)
    fn = sum(row["label"] == 1 and row["score"] < threshold for row in rows)
    positives, negatives = tp + fn, tn + fp
    sensitivity = proportion_ci(tp, positives)
    specificity = proportion_ci(tn, negatives)
    false_positive_rate = None if negatives == 0 else fp / negatives
    ppv = proportion_ci(tp, tp + fp)
    npv = proportion_ci(tn, tn + fn)
    return {
        "n_subjects": len({row["subject_id"] for row in rows}),
        "n_records": len(rows),
        "confusion_matrix": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "sensitivity_wilson_95": sensitivity,
        "specificity_wilson_95": specificity,
        "false_positive_rate": false_positive_rate,
        "positive_predictive_value_wilson_95": ppv,
        "negative_predictive_value_wilson_95": npv,
    }


def calibration(rows: list[dict], bins: int = 10) -> dict:
    buckets = [{"count": 0, "score_total": 0.0, "label_total": 0} for _ in range(bins)]
    for row in rows:
        index = min(bins - 1, int(row["score"] * bins))
        bucket = buckets[index]
        bucket["count"] += 1
        bucket["score_total"] += row["score"]
        bucket["label_total"] += row["label"]
    report, ece = [], 0.0
    for index, bucket in enumerate(buckets):
        if not bucket["count"]:
            continue
        mean_score = bucket["score_total"] / bucket["count"]
        observed_rate = bucket["label_total"] / bucket["count"]
        ece += (bucket["count"] / len(rows)) * abs(mean_score - observed_rate)
        report.append({"bin": index, "count": bucket["count"], "mean_score": mean_score, "observed_rate": observed_rate})
    return {"expected_calibration_error": ece, "bins": report}


def load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    subject_splits: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=2):
            required = ("subject_id", "label", "score", "split")
            if any(not row.get(key) for key in required):
                raise ValueError(f"row {number}: subject_id, label, score, and split are required")
            label, score = int(row["label"]), float(row["score"])
            if label not in (0, 1) or not 0 <= score <= 1:
                raise ValueError(f"row {number}: label must be 0/1 and score must be in [0, 1]")
            prior_split = subject_splits.setdefault(row["subject_id"], row["split"])
            if prior_split != row["split"]:
                raise ValueError(f"subject leakage: {row['subject_id']} appears in {prior_split} and {row['split']}")
            rows.append({**row, "label": label, "score": score})
    return rows


def evaluate(rows: list[dict], threshold: float) -> dict:
    by_split: dict[str, list[dict]] = defaultdict(list)
    by_subgroup: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_split[row["split"]].append(row)
        if row.get("subgroup"):
            by_subgroup[row["subgroup"]].append(row)
    return {
        "evaluation_notice": "Offline engineering evaluation only. Do not describe results as clinical validation without a prospectively designed, clinically governed study.",
        "threshold": threshold,
        "overall": metrics(rows, threshold),
        "calibration": calibration(rows),
        "by_split": {name: metrics(values, threshold) for name, values in by_split.items()},
        "by_subgroup": {name: metrics(values, threshold) for name, values in by_subgroup.items()},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    if not 0 <= args.threshold <= 1:
        raise SystemExit("--threshold must be in [0, 1]")
    result = evaluate(load_rows(args.input), args.threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
