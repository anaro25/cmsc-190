from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import BranchSpec
from dev.paths import OUTPUTS_ROOT


class ExperimentLogger:
    def __init__(self, output_path: Path):
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text("", encoding="utf-8")

    def log(self, message: str = "") -> None:
        print(message)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")


class BranchOutputManager:
    def __init__(self, branch_spec: BranchSpec):
        self.branch_root = OUTPUTS_ROOT / branch_spec.map_type
        if self.branch_root.exists():
            shutil.rmtree(self.branch_root)
        self.branch_root.mkdir(parents=True, exist_ok=True)
        self.metadata_dir = self.branch_root / "metadata"
        self.records_dir = self.branch_root / "records"
        self.aggregates_dir = self.branch_root / "aggregates"
        self.graphs_dir = self.branch_root / "graphs"
        self.logs_dir = self.branch_root / "logs"
        for directory in (
            self.metadata_dir,
            self.records_dir,
            self.aggregates_dir,
            self.graphs_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def _clean_csv_value(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _clean_csv_value(value) for key, value in row.items()})
