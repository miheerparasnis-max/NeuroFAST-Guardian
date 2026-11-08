"""Download a named public dataset outside this repository.

Example:
  python training/download_public.py --dataset psst_train --output-dir /path/out
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).parents[1] / "data" / "public_datasets.json"


def load_dataset(dataset_id: str) -> dict:
    datasets = json.loads(MANIFEST.read_text(encoding="utf-8"))["datasets"]
    for item in datasets:
        if item["id"] == dataset_id:
            return item
    raise SystemExit(f"Unknown dataset: {dataset_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--accept-terms", action="store_true")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    if not args.accept_terms:
        raise SystemExit("Read the source terms first, then repeat with --accept-terms.")
    url = dataset.get("download_url")
    if not url:
        raise SystemExit("This dataset has a public download page but no stable direct URL in the manifest.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / Path(url).name
    with urllib.request.urlopen(url) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    print(destination)
