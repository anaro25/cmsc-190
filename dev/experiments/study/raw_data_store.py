from __future__ import annotations

import json
import pickle
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.io_utils import write_json
from dev.paths import RAW_MAPF_DATA_ROOT


RAW_MAPF_DATA_FORMAT_VERSION = 2


class BranchRawDataStore:
    def __init__(self, branch_spec: BranchSpec):
        self.branch_spec = branch_spec
        self.branch_root = RAW_MAPF_DATA_ROOT / branch_spec.map_type
        self.manifest_path = self.branch_root / "manifest.json"
        self.summary_path = self.branch_root / "raw_mapf_data_summary.json"
        self.metadata_dir = self.branch_root / "metadata"
        self.conditions_dir = self.branch_root / "conditions"
        self.legacy_payload_path = self.branch_root / "raw_mapf_data.pkl"
        self.legacy_summary_path = self.branch_root / "raw_mapf_data_summary.json"

    def save(self, payload: dict[str, Any]) -> None:
        saved_at_utc = datetime.now(timezone.utc).isoformat()
        temp_root = self.branch_root.parent / f".{self.branch_spec.map_type}__raw_tmp"
        backup_root = self.branch_root.parent / f".{self.branch_spec.map_type}__raw_backup"
        if temp_root.exists():
            shutil.rmtree(temp_root)
        if backup_root.exists():
            shutil.rmtree(backup_root)
        temp_root.mkdir(parents=True, exist_ok=True)

        metadata_dir = temp_root / "metadata"
        conditions_dir = temp_root / "conditions"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        conditions_dir.mkdir(parents=True, exist_ok=True)

        branch_spec = payload["branch_spec"]
        dynamic_state = payload.get("dynamic_state")
        run_configurations = list(payload.get("run_configurations", []))
        run_records = list(payload.get("run_records", []))
        aggregates_payload = list(payload.get("aggregates_payload", []))
        branch_stop_summary = dict(payload.get("branch_stop_summary", {}))
        all_visualization_candidates = list(payload.get("all_visualization_candidates", []))

        write_json(metadata_dir / "branch_spec.json", branch_spec.to_dict())
        write_json(metadata_dir / "branch_stop_summary.json", branch_stop_summary)
        if dynamic_state is not None:
            with (metadata_dir / "dynamic_state.pkl").open("wb") as handle:
                pickle.dump(dynamic_state, handle, protocol=pickle.HIGHEST_PROTOCOL)
            write_json(
                metadata_dir / "dynamic_state_metadata.json",
                self._build_dynamic_state_metadata(dynamic_state),
            )

        run_configurations_by_condition = self._group_dict_rows_by_condition(run_configurations)
        run_records_by_condition = self._group_dict_rows_by_condition(run_records)
        visualization_candidates_by_condition = self._group_visualization_candidates_by_condition(
            all_visualization_candidates
        )

        condition_entries: list[dict[str, Any]] = []
        reported_agent_numbers: list[int] = []
        for condition_position, aggregate in enumerate(aggregates_payload, start=1):
            agent_number = int(aggregate["agent_number"])
            agent_number_index = int(aggregate["agent_number_index"])
            condition_key = (agent_number_index, agent_number)
            reported_agent_numbers.append(agent_number)
            condition_dir_name = (
                f"condition_{condition_position:03d}__agent_number_{agent_number:03d}"
            )
            condition_dir = conditions_dir / condition_dir_name
            visualization_dir = condition_dir / "visualization_candidates"
            condition_dir.mkdir(parents=True, exist_ok=True)
            visualization_dir.mkdir(parents=True, exist_ok=True)

            condition_run_configurations = list(run_configurations_by_condition.get(condition_key, []))
            condition_run_records = list(run_records_by_condition.get(condition_key, []))
            condition_visualization_candidates = list(
                visualization_candidates_by_condition.get(condition_key, [])
            )

            write_json(condition_dir / "condition_aggregate.json", aggregate)
            write_json(condition_dir / "run_configurations.json", condition_run_configurations)
            write_json(condition_dir / "run_records.json", condition_run_records)

            visualization_index: list[dict[str, Any]] = []
            for candidate_index, candidate in enumerate(condition_visualization_candidates, start=1):
                candidate_filename = (
                    f"{candidate_index:04d}__{candidate.mapping_name}__"
                    f"{self._slugify(candidate.run_configuration.run_config_id)}.pkl"
                )
                candidate_path = visualization_dir / candidate_filename
                with candidate_path.open("wb") as handle:
                    pickle.dump(candidate, handle, protocol=pickle.HIGHEST_PROTOCOL)
                visualization_index.append(
                    {
                        "candidate_index": candidate_index,
                        "mapping_name": candidate.mapping_name,
                        "run_config_id": candidate.run_configuration.run_config_id,
                        "agent_number": candidate.run_configuration.agent_number,
                        "run_index": candidate.run_configuration.run_index,
                        "relative_path": str(candidate_path.relative_to(temp_root)),
                    }
                )
            write_json(visualization_dir / "index.json", visualization_index)

            condition_entries.append(
                {
                    "condition_position": condition_position,
                    "condition_dir": str(condition_dir.relative_to(temp_root)),
                    "agent_number": agent_number,
                    "agent_number_index": agent_number_index,
                    "condition_aggregate_path": str(
                        (condition_dir / "condition_aggregate.json").relative_to(temp_root)
                    ),
                    "run_configurations_path": str(
                        (condition_dir / "run_configurations.json").relative_to(temp_root)
                    ),
                    "run_records_path": str(
                        (condition_dir / "run_records.json").relative_to(temp_root)
                    ),
                    "visualization_index_path": str(
                        (visualization_dir / "index.json").relative_to(temp_root)
                    ),
                    "run_configurations_count": len(condition_run_configurations),
                    "run_records_count": len(condition_run_records),
                    "visualization_candidates_count": len(condition_visualization_candidates),
                }
            )

        manifest = {
            "format_version": RAW_MAPF_DATA_FORMAT_VERSION,
            "saved_at_utc": saved_at_utc,
            "branch_map_type": self.branch_spec.map_type,
            "layout": "split_by_condition",
            "branch_spec_path": str((metadata_dir / "branch_spec.json").relative_to(temp_root)),
            "branch_stop_summary_path": str(
                (metadata_dir / "branch_stop_summary.json").relative_to(temp_root)
            ),
            "dynamic_state_path": (
                str((metadata_dir / "dynamic_state.pkl").relative_to(temp_root))
                if dynamic_state is not None
                else None
            ),
            "dynamic_state_metadata_path": (
                str((metadata_dir / "dynamic_state_metadata.json").relative_to(temp_root))
                if dynamic_state is not None
                else None
            ),
            "conditions": condition_entries,
        }
        write_json(temp_root / "manifest.json", manifest)
        write_json(temp_root / "raw_mapf_data_summary.json", self._build_summary(manifest, branch_spec, branch_stop_summary))

        try:
            if self.branch_root.exists():
                self.branch_root.replace(backup_root)
            temp_root.replace(self.branch_root)
            if backup_root.exists():
                shutil.rmtree(backup_root)
        except Exception:
            if self.branch_root.exists():
                shutil.rmtree(self.branch_root)
            if backup_root.exists():
                backup_root.replace(self.branch_root)
            raise
        finally:
            if temp_root.exists():
                shutil.rmtree(temp_root)
            if backup_root.exists():
                shutil.rmtree(backup_root)

    def load_graphs_and_data_payload(self) -> dict[str, Any]:
        manifest = self._load_manifest()
        branch_spec = self._load_branch_spec(manifest)
        dynamic_state = self._load_dynamic_state(manifest)
        run_configurations: list[dict[str, Any]] = []
        run_records: list[dict[str, Any]] = []
        aggregates_payload: list[dict[str, Any]] = []
        for condition_entry in manifest.get("conditions", []):
            run_configurations.extend(
                self._read_json_relative(condition_entry["run_configurations_path"])
            )
            run_records.extend(self._read_json_relative(condition_entry["run_records_path"]))
            aggregates_payload.append(
                self._read_json_relative(condition_entry["condition_aggregate_path"])
            )
        branch_stop_summary = self._read_json_relative(manifest["branch_stop_summary_path"])
        return {
            "branch_spec": branch_spec,
            "dynamic_state": dynamic_state,
            "run_configurations": run_configurations,
            "run_records": run_records,
            "aggregates_payload": aggregates_payload,
            "branch_stop_summary": branch_stop_summary,
        }

    def load_visualization_payload(self) -> dict[str, Any]:
        manifest = self._load_manifest()
        branch_spec = self._load_branch_spec(manifest)
        dynamic_state = self._load_dynamic_state(manifest)
        all_visualization_candidates: list[Any] = []
        for condition_entry in manifest.get("conditions", []):
            visualization_index = self._read_json_relative(condition_entry["visualization_index_path"])
            for candidate_ref in visualization_index:
                all_visualization_candidates.append(
                    self._read_pickle_relative(candidate_ref["relative_path"])
                )
        return {
            "branch_spec": branch_spec,
            "dynamic_state": dynamic_state,
            "all_visualization_candidates": all_visualization_candidates,
        }

    def load(self) -> dict[str, Any]:
        payload = self.load_graphs_and_data_payload()
        payload.update(self.load_visualization_payload())
        return payload

    def has_payload(self) -> bool:
        return self.manifest_path.exists() or self.legacy_payload_path.exists()

    def _load_manifest(self) -> dict[str, Any]:
        self._ensure_current_layout()
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                "No persisted raw MAPF data exists for "
                f"branch '{self.branch_spec.map_type}'. "
                "Set recompute_MAPF = True first so the program computes and saves raw MAPF data for this branch."
            )
        return self._read_json(self.manifest_path)

    def _ensure_current_layout(self) -> None:
        if self.manifest_path.exists():
            return
        if not self.legacy_payload_path.exists():
            return
        legacy_payload = self._load_legacy_payload()
        self.save(legacy_payload)

    def _load_legacy_payload(self) -> dict[str, Any]:
        with self.legacy_payload_path.open("rb") as handle:
            wrapped_payload = pickle.load(handle)
        payload = wrapped_payload.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(
                f"Persisted raw MAPF data for branch '{self.branch_spec.map_type}' is malformed."
            )
        return payload

    def _load_branch_spec(self, manifest: dict[str, Any]) -> BranchSpec:
        branch_spec_payload = dict(self._read_json_relative(manifest["branch_spec_path"]))
        if isinstance(branch_spec_payload.get("agent_number_range"), list):
            branch_spec_payload["agent_number_range"] = tuple(branch_spec_payload["agent_number_range"])
        if isinstance(branch_spec_payload.get("dynamic_group_stay_durations"), list):
            branch_spec_payload["dynamic_group_stay_durations"] = tuple(
                branch_spec_payload["dynamic_group_stay_durations"]
            )
        return BranchSpec(**branch_spec_payload)

    def _load_dynamic_state(self, manifest: dict[str, Any]) -> Any:
        dynamic_state_path = manifest.get("dynamic_state_path")
        if not dynamic_state_path:
            return None
        return self._read_pickle_relative(dynamic_state_path)

    def _read_json_relative(self, relative_path: str) -> Any:
        return self._read_json(self.branch_root / relative_path)

    def _read_pickle_relative(self, relative_path: str) -> Any:
        with (self.branch_root / relative_path).open("rb") as handle:
            return pickle.load(handle)

    def _build_summary(
        self,
        manifest: dict[str, Any],
        branch_spec: BranchSpec,
        branch_stop_summary: dict[str, Any],
    ) -> dict[str, Any]:
        conditions = manifest.get("conditions", [])
        return {
            "format_version": manifest["format_version"],
            "saved_at_utc": manifest["saved_at_utc"],
            "branch_map_type": manifest["branch_map_type"],
            "branch_display_name": branch_spec.display_name,
            "layout": manifest["layout"],
            "conditions_count": len(conditions),
            "reported_agent_numbers": [entry["agent_number"] for entry in conditions],
            "run_configurations_count": sum(entry["run_configurations_count"] for entry in conditions),
            "run_records_count": sum(entry["run_records_count"] for entry in conditions),
            "visualization_candidates_count": sum(
                entry["visualization_candidates_count"] for entry in conditions
            ),
            "has_dynamic_state": manifest.get("dynamic_state_path") is not None,
            "branch_spec": branch_spec.to_dict(),
            "branch_stop_summary": branch_stop_summary,
            "conditions": [
                {
                    "condition_position": entry["condition_position"],
                    "agent_number": entry["agent_number"],
                    "agent_number_index": entry["agent_number_index"],
                    "condition_dir": entry["condition_dir"],
                    "run_configurations_count": entry["run_configurations_count"],
                    "run_records_count": entry["run_records_count"],
                    "visualization_candidates_count": entry["visualization_candidates_count"],
                }
                for entry in conditions
            ],
        }

    def _group_dict_rows_by_condition(
        self, rows: list[dict[str, Any]]
    ) -> dict[tuple[int, int], list[dict[str, Any]]]:
        grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for row in rows:
            condition_key = (int(row["agent_number_index"]), int(row["agent_number"]))
            grouped.setdefault(condition_key, []).append(row)
        return grouped

    def _group_visualization_candidates_by_condition(self, candidates: list[Any]) -> dict[tuple[int, int], list[Any]]:
        grouped: dict[tuple[int, int], list[Any]] = {}
        for candidate in candidates:
            run_configuration = candidate.run_configuration
            condition_key = (int(run_configuration.agent_number_index), int(run_configuration.agent_number))
            grouped.setdefault(condition_key, []).append(candidate)
        return grouped

    def _build_dynamic_state_metadata(self, dynamic_state: Any) -> dict[str, Any]:
        return {
            "map_identifier": dynamic_state.map_identifier,
            "schedule_seed": dynamic_state.schedule_seed,
            "generation_mode": dynamic_state.generation_mode,
            "static_rows": len(dynamic_state.static_matrix),
            "static_cols": len(dynamic_state.static_matrix[0]) if dynamic_state.static_matrix else 0,
            "dynamic_loop_length": len(dynamic_state.dynamic_loop_frames),
        }

    def _read_json(self, path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _slugify(self, text: str) -> str:
        compact = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
        return compact or "item"
