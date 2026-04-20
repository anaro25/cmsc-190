from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.io_utils import write_json
from dev.paths import RAW_MAPF_DATA_ROOT


RAW_MAPF_DATA_FORMAT_VERSION = 1


class BranchRawDataStore:
    def __init__(self, branch_spec: BranchSpec):
        self.branch_spec = branch_spec
        self.branch_root = RAW_MAPF_DATA_ROOT / branch_spec.map_type
        self.branch_root.mkdir(parents=True, exist_ok=True)
        self.payload_path = self.branch_root / "raw_mapf_data.pkl"
        self.summary_path = self.branch_root / "raw_mapf_data_summary.json"

    def save(self, payload: dict[str, Any]) -> None:
        wrapped_payload = {
            "format_version": RAW_MAPF_DATA_FORMAT_VERSION,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "branch_map_type": self.branch_spec.map_type,
            "payload": payload,
        }
        temp_path = self.payload_path.with_suffix(".tmp")
        with temp_path.open("wb") as handle:
            pickle.dump(wrapped_payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temp_path.replace(self.payload_path)
        write_json(self.summary_path, self._build_summary(wrapped_payload))

    def load(self) -> dict[str, Any]:
        if not self.payload_path.exists():
            raise FileNotFoundError(
                "No persisted raw MAPF data exists for "
                f"branch '{self.branch_spec.map_type}'. "
                "Set recompute_MAPF = True first so the program computes and saves raw MAPF data for this branch."
            )
        with self.payload_path.open("rb") as handle:
            wrapped_payload = pickle.load(handle)
        payload = wrapped_payload.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(
                f"Persisted raw MAPF data for branch '{self.branch_spec.map_type}' is malformed."
            )
        return payload

    def has_payload(self) -> bool:
        return self.payload_path.exists()

    def _build_summary(self, wrapped_payload: dict[str, Any]) -> dict[str, Any]:
        payload = wrapped_payload["payload"]
        branch_spec = payload["branch_spec"]
        dynamic_state = payload.get("dynamic_state")
        return {
            "format_version": wrapped_payload["format_version"],
            "saved_at_utc": wrapped_payload["saved_at_utc"],
            "branch_map_type": wrapped_payload["branch_map_type"],
            "branch_display_name": branch_spec.display_name,
            "run_configurations_count": len(payload.get("run_configurations", [])),
            "run_records_count": len(payload.get("run_records", [])),
            "condition_aggregates_count": len(payload.get("aggregates_payload", [])),
            "visualization_candidates_count": len(payload.get("all_visualization_candidates", [])),
            "has_dynamic_state": dynamic_state is not None,
            "branch_spec": branch_spec.to_dict(),
            "branch_stop_summary": payload.get("branch_stop_summary", {}),
        }
