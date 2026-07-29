from __future__ import annotations

import pickle
import shutil
import time
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.ref_comparison.models import RefCaseSpec, RefVisualizationCandidate
from dev.experiments.study.io_utils import write_json
from dev.experiments.study.main_output_layout import get_main_config_artifact_dir
from dev.experiments.study.models import DynamicBranchState, VisualizationCandidate
from dev.paths import FRAME_BY_FRAME_REF_COMPARISON_ROOT


FRAME_BY_FRAME_FORMAT_VERSION = 1
FRAME_BY_FRAME_FILENAME = "frame_by_frame.pkl"
FRAME_BY_FRAME_METADATA_FILENAME = "metadata.json"
FRAME_BY_FRAME_MANIFEST_FILENAME = "manifest.json"
SHARED_CONTEXT_DIR_NAME = "shared_context"
SHARED_CONTEXT_FILENAME = "shared_context.pkl"
SHARED_CONTEXT_METADATA_FILENAME = "metadata.json"


def _saved_at_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _frame_count_from_solver_result(solver_result: dict[str, Any] | None) -> int:
    paths_by_agent = (solver_result or {}).get("paths_by_agent") or {}
    lengths = [len(path) for path in paths_by_agent.values() if path is not None]
    return max(lengths, default=0)


def _has_successful_paths(solver_result: dict[str, Any] | None) -> bool:
    return bool(
        solver_result
        and solver_result.get("status") == "solved"
        and solver_result.get("paths_by_agent")
    )


def _is_retryable_windows_filesystem_error(exc: OSError) -> bool:
    return (
        isinstance(exc, PermissionError)
        or getattr(exc, "winerror", None) in {5, 32, 33}
    )


def _rename_tree_with_retry(
    source: Path,
    target: Path,
    *,
    operation: str,
    attempts: int = 8,
    initial_delay_seconds: float = 0.05,
) -> None:
    """Rename a directory, tolerating brief Windows file-handle locks."""
    delay_seconds = initial_delay_seconds
    last_error: OSError | None = None

    for attempt_number in range(1, attempts + 1):
        try:
            source.rename(target)
            return
        except OSError as exc:
            if not _is_retryable_windows_filesystem_error(exc):
                raise
            last_error = exc
            if attempt_number == attempts:
                break
            time.sleep(delay_seconds)
            delay_seconds *= 2

    raise RuntimeError(
        f"Could not {operation} after {attempts} attempts: {source} -> {target}. "
        "A Windows process may still have a file or directory handle open."
    ) from last_error


def _remove_tree_with_retry(
    path: Path,
    *,
    attempts: int = 8,
    initial_delay_seconds: float = 0.05,
) -> bool:
    """Best-effort cleanup for directories that may be briefly locked on Windows."""
    delay_seconds = initial_delay_seconds
    for attempt_number in range(1, attempts + 1):
        if not path.exists():
            return True
        try:
            shutil.rmtree(path)
            return True
        except OSError as exc:
            if not _is_retryable_windows_filesystem_error(exc):
                return False
            if attempt_number == attempts:
                return False
            time.sleep(delay_seconds)
            delay_seconds *= 2
    return not path.exists()


def _atomic_replace_tree(final_root: Path, build_tree: Any) -> None:
    """Build a replacement tree and promote it without risking the last valid tree."""
    final_root.parent.mkdir(parents=True, exist_ok=True)
    unique_suffix = uuid.uuid4().hex[:10]
    temp_root = (
        final_root.parent
        / f".{final_root.name}__frame_by_frame_tmp_{unique_suffix}"
    )
    backup_root = (
        final_root.parent
        / f".{final_root.name}__frame_by_frame_backup_{unique_suffix}"
    )
    temp_root.mkdir(parents=True, exist_ok=False)

    build_completed = False
    original_moved = False
    promotion_completed = False

    try:
        build_tree(temp_root)
        build_completed = True

        if final_root.exists():
            _rename_tree_with_retry(
                final_root,
                backup_root,
                operation="move the existing frame-by-frame directory aside",
            )
            original_moved = True

        _rename_tree_with_retry(
            temp_root,
            final_root,
            operation="promote the completed frame-by-frame directory",
        )
        promotion_completed = True
    except Exception as exc:
        rollback_error: Exception | None = None
        if original_moved and not promotion_completed and backup_root.exists():
            if final_root.exists():
                try:
                    if not _remove_tree_with_retry(final_root):
                        raise RuntimeError(
                            f"Could not clear incomplete replacement directory: {final_root}"
                        )
                except Exception as cleanup_exc:
                    rollback_error = cleanup_exc
            if rollback_error is None:
                try:
                    _rename_tree_with_retry(
                        backup_root,
                        final_root,
                        operation="restore the previous frame-by-frame directory",
                    )
                except Exception as restore_exc:
                    rollback_error = restore_exc

        if not build_completed and temp_root.exists():
            _remove_tree_with_retry(temp_root)

        if rollback_error is not None:
            raise RuntimeError(
                "Frame-by-frame directory replacement failed and the previous directory "
                f"could not be restored automatically. Completed replacement data: {temp_root}. "
                f"Previous valid data: {backup_root}."
            ) from rollback_error

        if build_completed and temp_root.exists():
            raise RuntimeError(
                "Frame-by-frame directory replacement failed after serialization completed. "
                f"The completed data was preserved for recovery at: {temp_root}. "
                f"Destination: {final_root}."
            ) from exc
        raise

    if backup_root.exists() and not _remove_tree_with_retry(backup_root):
        warnings.warn(
            "The new frame-by-frame directory was saved successfully, but the previous "
            f"backup could not yet be removed because it is locked: {backup_root}",
            RuntimeWarning,
            stacklevel=2,
        )


def _write_package(run_root: Path, package: dict[str, Any], metadata: dict[str, Any]) -> None:
    run_root.mkdir(parents=True, exist_ok=True)
    with (run_root / FRAME_BY_FRAME_FILENAME).open("wb") as handle:
        pickle.dump(package, handle, protocol=pickle.HIGHEST_PROTOCOL)
    write_json(run_root / FRAME_BY_FRAME_METADATA_FILENAME, metadata)


def _read_package(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        package = pickle.load(handle)
    if not isinstance(package, dict):
        raise ValueError(f"Malformed frame-by-frame package: {path}")
    version = int(package.get("format_version", 0) or 0)
    if version != FRAME_BY_FRAME_FORMAT_VERSION:
        raise ValueError(
            f"Incompatible frame-by-frame package version at {path}: "
            f"found {version}, expected {FRAME_BY_FRAME_FORMAT_VERSION}. "
            "Run with to_generate = 'raw_data' to regenerate it."
        )
    return package


class ReferenceFrameByFrameStore:
    """Persist only the designated successful reference-comparison trajectories."""

    def __init__(self, case_spec: RefCaseSpec, *, root: Path | None = None):
        self.case_spec = case_spec
        self.root = Path(root) if root is not None else FRAME_BY_FRAME_REF_COMPARISON_ROOT
        self.mode_dir_name = (
            "single_agent_pf" if case_spec.experiment_mode == "single_agent" else "multi_agent_pf"
        )
        self.mode_root = self.root / self.mode_dir_name
        self.manifest_path = self.mode_root / FRAME_BY_FRAME_MANIFEST_FILENAME

    def save(self, candidates: Iterable[RefVisualizationCandidate]) -> dict[str, Any]:
        # The computation phase already provides only final-comparison candidates.
        # Keep the first successful candidate for each map/mapping pair defensively.
        selected_by_key: dict[tuple[int, str], RefVisualizationCandidate] = {}
        for candidate in candidates:
            if not _has_successful_paths(candidate.solver_result):
                continue
            map_number = int(candidate.run_configuration.map_number or 0)
            if map_number <= 0:
                continue
            key = (map_number, str(candidate.mapping_name))
            selected_by_key.setdefault(key, candidate)

        saved_at = _saved_at_utc()
        manifest_entries: list[dict[str, Any]] = []

        def build_tree(temp_root: Path) -> None:
            for (map_number, mapping_name), candidate in sorted(selected_by_key.items()):
                map_dir_name = f"map_{map_number}"
                if self.case_spec.experiment_mode == "multi_agent":
                    capacity_dir_name = (
                        f"classical_capacity_{int(candidate.run_configuration.agent_number):03d}_agents"
                    )
                    relative_run_root = (
                        Path(map_dir_name)
                        / capacity_dir_name
                        / mapping_name
                        / "first_successful_run"
                    )
                else:
                    capacity_dir_name = None
                    relative_run_root = (
                        Path(map_dir_name) / mapping_name / "first_successful_run"
                    )

                metadata = {
                    "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                    "saved_at_utc": saved_at,
                    "experiment_family": "reference_comparison",
                    "experiment_mode": self.case_spec.experiment_mode,
                    "selection_rule": "first successful timing repetition from the final comparison",
                    "case_id": self.case_spec.case_id,
                    "map_number": map_number,
                    "map_label": candidate.run_configuration.map_label,
                    "map_identifier": candidate.run_configuration.map_identifier,
                    "capacity_directory": capacity_dir_name,
                    "agent_number": int(candidate.run_configuration.agent_number),
                    "mapping_name": mapping_name,
                    "run_config_id": candidate.run_configuration.run_config_id,
                    "run_index": int(candidate.run_configuration.run_index),
                    "solver_status": candidate.solver_result.get("status"),
                    "frame_count": _frame_count_from_solver_result(candidate.solver_result),
                    "package_file": FRAME_BY_FRAME_FILENAME,
                }
                package = {
                    "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                    "experiment_family": "reference_comparison",
                    "selection": metadata,
                    "candidate": candidate,
                }
                _write_package(temp_root / relative_run_root, package, metadata)
                manifest_entries.append(
                    {
                        **metadata,
                        "relative_run_root": str(relative_run_root),
                        "relative_package_path": str(
                            relative_run_root / FRAME_BY_FRAME_FILENAME
                        ),
                        "relative_metadata_path": str(
                            relative_run_root / FRAME_BY_FRAME_METADATA_FILENAME
                        ),
                    }
                )

            write_json(
                temp_root / FRAME_BY_FRAME_MANIFEST_FILENAME,
                {
                    "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                    "saved_at_utc": saved_at,
                    "experiment_family": "reference_comparison",
                    "experiment_mode": self.case_spec.experiment_mode,
                    "case_id": self.case_spec.case_id,
                    "layout": (
                        "map / classical capacity / mapping / first successful run"
                        if self.case_spec.experiment_mode == "multi_agent"
                        else "map / mapping / first successful run"
                    ),
                    "saved_run_count": len(manifest_entries),
                    "runs": manifest_entries,
                },
            )

        _atomic_replace_tree(self.mode_root, build_tree)
        return {
            "frame_by_frame_root": str(self.mode_root),
            "manifest_path": str(self.manifest_path),
            "saved_run_count": len(manifest_entries),
            "runs": manifest_entries,
        }

    def load_candidates(self) -> list[RefVisualizationCandidate]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                "No saved reference-comparison frame-by-frame data exists for "
                f"'{self.case_spec.experiment_mode}' at {self.mode_root}. "
                "Run with to_generate = 'raw_data' for that reference case first."
            )
        import json

        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        version = int(manifest.get("format_version", 0) or 0)
        if version != FRAME_BY_FRAME_FORMAT_VERSION:
            raise ValueError(
                "The saved reference frame-by-frame manifest is incompatible. "
                "Run with to_generate = 'raw_data' to regenerate it."
            )

        candidates: list[RefVisualizationCandidate] = []
        for entry in manifest.get("runs", []):
            package_path = self.mode_root / Path(
                str(entry["relative_package_path"]).replace("\\", "/")
            )
            package = _read_package(package_path)
            candidate = package.get("candidate")
            if not isinstance(candidate, RefVisualizationCandidate):
                raise ValueError(f"Malformed reference frame-by-frame candidate: {package_path}")
            candidates.append(candidate)
        return candidates


class MainExperimentFrameByFrameStore:
    """Persist the two designated main-experiment capacity trajectories per config."""

    def __init__(self, branch_spec: BranchSpec, *, root: Path | None = None):
        self.branch_spec = branch_spec
        self.config_root = (
            Path(root)
            if root is not None
            else get_main_config_artifact_dir(branch_spec, "frame_by_frame")
        )
        self.manifest_path = self.config_root / FRAME_BY_FRAME_MANIFEST_FILENAME

    def save_selected_runs(
        self,
        *,
        classical_attempt: Any | None,
        cyclic_attempt: Any | None,
        dynamic_state: DynamicBranchState | None,
    ) -> dict[str, Any]:
        selected_attempts = (
            ("classical", "classical_capacity", classical_attempt),
            ("cyclic", "cyclic_capacity", cyclic_attempt),
        )
        saved_at = _saved_at_utc()
        manifest_entries: list[dict[str, Any]] = []

        def build_tree(temp_root: Path) -> None:
            shared_context_root = temp_root / SHARED_CONTEXT_DIR_NAME
            shared_context_root.mkdir(parents=True, exist_ok=True)
            shared_context = {
                "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                "branch_spec": self.branch_spec,
                "dynamic_state": dynamic_state,
            }
            with (shared_context_root / SHARED_CONTEXT_FILENAME).open("wb") as handle:
                pickle.dump(shared_context, handle, protocol=pickle.HIGHEST_PROTOCOL)
            write_json(
                shared_context_root / SHARED_CONTEXT_METADATA_FILENAME,
                {
                    "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                    "saved_at_utc": saved_at,
                    "map_config": self.branch_spec.map_type,
                    "is_dynamic": bool(self.branch_spec.is_dynamic),
                    "has_dynamic_state": dynamic_state is not None,
                    "shared_context_file": SHARED_CONTEXT_FILENAME,
                    "note": "Shared once by both selected mapping-capacity trajectory packages.",
                },
            )

            for mapping_name, capacity_name, attempt in selected_attempts:
                if attempt is None or not _has_successful_paths(attempt.solver_result):
                    continue

                prepared_context = attempt.prepared_context
                run_configuration = prepared_context.run_configuration
                composite_map = None
                if not self.branch_spec.is_dynamic:
                    composite_map = (
                        prepared_context.classical_map
                        if mapping_name == "classical"
                        else prepared_context.cyclic_map
                    )
                candidate = VisualizationCandidate(
                    mapping_name=mapping_name,
                    run_configuration=run_configuration,
                    agents=prepared_context.agents,
                    solver_result=attempt.solver_result,
                    composite_map=composite_map,
                )

                agent_number = int(run_configuration.agent_number)
                capacity_dir_name = f"{capacity_name}_{agent_number:03d}_agents"
                relative_run_root = (
                    Path(capacity_dir_name)
                    / mapping_name
                    / "final_selected_successful_run"
                )
                metadata = {
                    "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                    "saved_at_utc": saved_at,
                    "experiment_family": "main_experiment",
                    "selection_rule": "final selected successful run at the mapping's own capacity",
                    "map_config": self.branch_spec.map_type,
                    "category_map_type": self.branch_spec.category_map_type,
                    "category_directory": self.branch_spec.data_log_category_dir_name,
                    "config_directory": self.branch_spec.data_log_file_stem,
                    "capacity_name": capacity_name,
                    "capacity_directory": capacity_dir_name,
                    "agent_number": agent_number,
                    "mapping_name": mapping_name,
                    "run_config_id": run_configuration.run_config_id,
                    "run_index": int(run_configuration.run_index),
                    "solver_status": attempt.solver_result.get("status"),
                    "frame_count": _frame_count_from_solver_result(attempt.solver_result),
                    "is_dynamic": bool(self.branch_spec.is_dynamic),
                    "package_file": FRAME_BY_FRAME_FILENAME,
                }
                package = {
                    "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                    "experiment_family": "main_experiment",
                    "selection": metadata,
                    "candidate": candidate,
                }
                _write_package(temp_root / relative_run_root, package, metadata)
                manifest_entries.append(
                    {
                        **metadata,
                        "relative_run_root": str(relative_run_root),
                        "relative_package_path": str(
                            relative_run_root / FRAME_BY_FRAME_FILENAME
                        ),
                        "relative_metadata_path": str(
                            relative_run_root / FRAME_BY_FRAME_METADATA_FILENAME
                        ),
                    }
                )

            write_json(
                temp_root / FRAME_BY_FRAME_MANIFEST_FILENAME,
                {
                    "format_version": FRAME_BY_FRAME_FORMAT_VERSION,
                    "saved_at_utc": saved_at,
                    "experiment_family": "main_experiment",
                    "map_config": self.branch_spec.map_type,
                    "category_map_type": self.branch_spec.category_map_type,
                    "layout": "mapping capacity / mapping / final selected successful run",
                    "shared_context_path": str(
                        Path(SHARED_CONTEXT_DIR_NAME) / SHARED_CONTEXT_FILENAME
                    ),
                    "shared_context_metadata_path": str(
                        Path(SHARED_CONTEXT_DIR_NAME) / SHARED_CONTEXT_METADATA_FILENAME
                    ),
                    "saved_run_count": len(manifest_entries),
                    "runs": manifest_entries,
                },
            )

        _atomic_replace_tree(self.config_root, build_tree)
        return {
            "frame_by_frame_root": str(self.config_root),
            "manifest_path": str(self.manifest_path),
            "saved_run_count": len(manifest_entries),
            "runs": manifest_entries,
        }

    def load_packages(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(
                "No saved main-experiment frame-by-frame data exists for "
                f"'{self.branch_spec.map_type}' at {self.config_root}. "
                "Run with to_generate = 'raw_data' for this map configuration first."
            )
        import json

        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        version = int(manifest.get("format_version", 0) or 0)
        if version != FRAME_BY_FRAME_FORMAT_VERSION:
            raise ValueError(
                "The saved main-experiment frame-by-frame manifest is incompatible. "
                "Run with to_generate = 'raw_data' to regenerate it."
            )

        shared_context_relative_path = manifest.get("shared_context_path")
        if not shared_context_relative_path:
            raise ValueError(
                "The main-experiment frame-by-frame manifest is missing its shared context. "
                "Run with to_generate = 'raw_data' to regenerate it."
            )
        shared_context_path = self.config_root / Path(
            str(shared_context_relative_path).replace("\\", "/")
        )
        with shared_context_path.open("rb") as handle:
            shared_context = pickle.load(handle)
        if not isinstance(shared_context, dict):
            raise ValueError(f"Malformed shared frame-by-frame context: {shared_context_path}")
        if int(shared_context.get("format_version", 0) or 0) != FRAME_BY_FRAME_FORMAT_VERSION:
            raise ValueError(
                "The main-experiment shared frame-by-frame context is incompatible. "
                "Run with to_generate = 'raw_data' to regenerate it."
            )

        branch_spec = shared_context.get("branch_spec")
        dynamic_state = shared_context.get("dynamic_state")
        packages: list[dict[str, Any]] = []
        for entry in manifest.get("runs", []):
            package_path = self.config_root / Path(
                str(entry["relative_package_path"]).replace("\\", "/")
            )
            package = _read_package(package_path)
            candidate = package.get("candidate")
            if not isinstance(candidate, VisualizationCandidate):
                raise ValueError(f"Malformed main-experiment frame-by-frame candidate: {package_path}")
            package["branch_spec"] = branch_spec
            package["dynamic_state"] = dynamic_state
            packages.append(package)
        return packages
