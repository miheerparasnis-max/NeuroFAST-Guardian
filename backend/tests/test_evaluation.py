import csv

import pytest

from evaluation.model_eval import evaluate, load_rows


def test_evaluation_reports_metrics_calibration_and_subgroups() -> None:
    rows = [
        {"subject_id": "a", "label": 1, "score": 0.9, "split": "test", "subgroup": "group_a"},
        {"subject_id": "b", "label": 0, "score": 0.8, "split": "test", "subgroup": "group_a"},
        {"subject_id": "c", "label": 0, "score": 0.1, "split": "test", "subgroup": "group_b"},
        {"subject_id": "d", "label": 1, "score": 0.2, "split": "test", "subgroup": "group_b"},
    ]
    report = evaluate(rows, 0.5)
    assert report["overall"]["confusion_matrix"] == {
        "true_positive": 1,
        "false_positive": 1,
        "true_negative": 1,
        "false_negative": 1,
    }
    assert report["calibration"]["expected_calibration_error"] >= 0
    assert set(report["by_subgroup"]) == {"group_a", "group_b"}


def test_loader_rejects_subject_leakage(tmp_path) -> None:
    path = tmp_path / "leak.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["subject_id", "label", "score", "split"])
        writer.writeheader()
        writer.writerow({"subject_id": "same", "label": "1", "score": "0.9", "split": "train"})
        writer.writerow({"subject_id": "same", "label": "1", "score": "0.8", "split": "test"})
    with pytest.raises(ValueError, match="subject leakage"):
        load_rows(path)
