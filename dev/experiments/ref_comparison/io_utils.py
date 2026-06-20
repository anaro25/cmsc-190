from __future__ import annotations

import csv
import json
import pickle
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dev.experiments.ref_comparison.models import RefCaseSpec
from dev.paths import OUTPUTS_REF_COMPARISON_ROOT, RAW_REF_COMPARISON_DATA_ROOT


def format_elapsed_mmss(elapsed_seconds: float) -> str:
    total_seconds = max(0, int(round(elapsed_seconds)))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}m {seconds:02d}s"


class RefExperimentLogger:
    def __init__(self, output_path: Path, *, start_time: float | None = None):
        self.output_path = output_path
        self.start_time = time.perf_counter() if start_time is None else start_time
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text("", encoding="utf-8")

    def log(self, message: str = "") -> None:
        print(message, flush=True)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    def elapsed_seconds(self) -> float:
        return time.perf_counter() - self.start_time

    def log_elapsed(self, milestone: str) -> None:
        self.log(f"[Elapsed: {format_elapsed_mmss(self.elapsed_seconds())}] {milestone}")


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _execution_stage_name(*, recompute_mapf: bool, generation_target: str) -> str:
    stages: list[str] = []
    if recompute_mapf:
        stages.append("computation")
    if generation_target != "nothing":
        stages.append(generation_target)
    return "__and__".join(stages) if stages else "no_generation"


class RefCaseOutputManager:
    def __init__(self, case_spec: RefCaseSpec, *, generation_target: str, recompute_mapf: bool):
        self.case_spec = case_spec
        self.case_root = OUTPUTS_REF_COMPARISON_ROOT / case_spec.case_id
        self.case_root.mkdir(parents=True, exist_ok=True)
        self.generation_target = generation_target
        self.execution_stage_name = _execution_stage_name(
            recompute_mapf=recompute_mapf,
            generation_target=generation_target,
        )
        self.aggregates_dir = self.case_root / "aggregates" / "graphs_and_data"
        self.graphs_dir = self.case_root / "graphs" / "graphs_and_data"
        self.logs_dir = self.case_root / "logs" / self.execution_stage_name
        self.metadata_dir = self.case_root / "metadata" / generation_target
        self.records_dir = self.case_root / "records" / "graphs_and_data"
        self.visualizations_dir = self.case_root / "visualizations"

    def prepare_log_output(self) -> Path:
        _reset_dir(self.logs_dir)
        return self.logs_dir / "reference_comparison.log"

    def clear_graphs_and_data_outputs(self) -> None:
        _reset_dir(self.aggregates_dir)
        _reset_dir(self.graphs_dir)
        _reset_dir(self.metadata_dir)
        _reset_dir(self.records_dir)

    def clear_visualization_outputs(self) -> None:
        _reset_dir(self.metadata_dir)
        _reset_dir(self.visualizations_dir)


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
            writer.writerow(row)


class RefRawDataStore:
    def __init__(self, case_spec: RefCaseSpec):
        self.case_spec = case_spec
        self.case_root = RAW_REF_COMPARISON_DATA_ROOT / case_spec.case_id
        self.manifest_path = self.case_root / "manifest.json"
        self.payload_path = self.case_root / "raw_reference_payload.pkl"
        self.summary_path = self.case_root / "raw_reference_summary.json"

    def save(self, payload: dict[str, Any]) -> None:
        temp_root = self.case_root.parent / f".{self.case_spec.case_id}__raw_tmp"
        backup_root = self.case_root.parent / f".{self.case_spec.case_id}__raw_backup"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        if backup_root.exists():
            shutil.rmtree(backup_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        payload_path = temp_root / "raw_reference_payload.pkl"
        with payload_path.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)

        manifest = {
            "format_version": 1,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "case_id": self.case_spec.case_id,
            "payload_path": payload_path.name,
            "case_spec": self.case_spec.to_dict(),
        }
        write_json(temp_root / "manifest.json", manifest)
        write_json(
            temp_root / "raw_reference_summary.json",
            {
                "case_id": self.case_spec.case_id,
                "display_name": self.case_spec.display_name,
                "experiment_mode": self.case_spec.experiment_mode,
                "map_size": self.case_spec.map_size,
                "agent_number": self.case_spec.agent_number,
                "map_agent_numbers": {str(key): value for key, value in sorted(self.case_spec.map_agent_numbers.items())},
                "run_configurations_count": len(payload.get("run_configurations", [])),
                "run_records_count": len(payload.get("run_records", [])),
                "discarded_attempts_count": len(payload.get("discarded_attempts", [])),
                "has_aggregate": payload.get("aggregate") is not None,
                "stop_summary": payload.get("stop_summary", {}),
            },
        )

        try:
            if self.case_root.exists():
                self.case_root.replace(backup_root)
            temp_root.replace(self.case_root)
            if backup_root.exists():
                shutil.rmtree(backup_root)
        except Exception:
            if self.case_root.exists():
                shutil.rmtree(self.case_root)
            if backup_root.exists():
                backup_root.replace(self.case_root)
            raise
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)
            if backup_root.exists():
                shutil.rmtree(backup_root)

    def load(self) -> dict[str, Any]:
        if not self.manifest_path.exists() or not self.payload_path.exists():
            raise FileNotFoundError(
                "No persisted reference-comparison raw data exists for "
                f"case '{self.case_spec.case_id}'. Set recompute_MAPF = True first."
            )
        with self.payload_path.open("rb") as handle:
            return pickle.load(handle)
