from training.train_psst_baseline import is_test_subject, metrics


def test_subject_split_is_deterministic() -> None:
    assert is_test_subject("subject-a") == is_test_subject("subject-a")


def test_baseline_metrics() -> None:
    result = metrics(
        [
            {"subject_id": "a", "label": 1, "score": 0.9},
            {"subject_id": "b", "label": 0, "score": 0.8},
            {"subject_id": "c", "label": 0, "score": 0.1},
            {"subject_id": "d", "label": 1, "score": 0.2},
        ]
    )
    assert result["records"] == 4
    assert result["subjects"] == 4
    assert result["accuracy"] == 0.5
