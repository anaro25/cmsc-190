from __future__ import annotations

import filecmp
import shutil
from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import BranchSpec
from dev.paths import OUTPUTS_MAIN_ROOT


MAIN_OUTPUT_ARTIFACT_DIR_NAMES: tuple[str, ...] = (
    "frame_by_frame",
    "metrics_data",
    "metrics_data_inspection",
    "terminal_logs",
    "visualization",
)
PROJECT_LEVEL_FILES_DIR_NAME = "project_level_files"
PROJECT_LEVEL_FILES_ROOT = OUTPUTS_MAIN_ROOT / PROJECT_LEVEL_FILES_DIR_NAME

_LEGACY_INSPECTION_EVALUATION_SUFFIX = "_evaluation.xml"
_LEGACY_INSPECTION_RAW_DATA_SUFFIX = "_raw_data.json"
_LEGACY_PROJECT_LEVEL_METRICS_FILE_NAMES = {
    "dataset_manifest.json",
    "README.txt",
}

_TEXT_OUTPUT_SUFFIXES = {".csv", ".json", ".log", ".txt", ".xml"}


def get_main_config_root(branch_spec: BranchSpec) -> Path:
    """Return the map-category/configuration root for one main-experiment case."""
    return (
        OUTPUTS_MAIN_ROOT
        / branch_spec.data_log_category_dir_name
        / branch_spec.data_log_file_stem
    )


def get_main_config_artifact_dir(branch_spec: BranchSpec, artifact_name: str) -> Path:
    """Return one artifact directory inside an exact map configuration."""
    if artifact_name not in MAIN_OUTPUT_ARTIFACT_DIR_NAMES:
        allowed = ", ".join(MAIN_OUTPUT_ARTIFACT_DIR_NAMES)
        raise ValueError(f"Unknown main-output artifact '{artifact_name}'. Expected one of: {allowed}.")
    return get_main_config_root(branch_spec) / artifact_name


def invalidate_main_config_visualization_outputs(branch_spec: BranchSpec) -> list[Path]:
    """Delete visualization artifacts that became stale after raw-data regeneration starts."""
    removed_paths: list[Path] = []

    visualization_root = get_main_config_artifact_dir(branch_spec, "visualization")
    if visualization_root.is_symlink() or visualization_root.is_file():
        visualization_root.unlink()
        removed_paths.append(visualization_root)
    elif visualization_root.is_dir():
        shutil.rmtree(visualization_root)
        removed_paths.append(visualization_root)

    visualization_log_path = (
        get_main_config_artifact_dir(branch_spec, "terminal_logs")
        / "visualization.log"
    )
    if visualization_log_path.exists() or visualization_log_path.is_symlink():
        visualization_log_path.unlink()
        removed_paths.append(visualization_log_path)

    return removed_paths


def _files_are_identical(first: Path, second: Path) -> bool:
    return first.is_file() and second.is_file() and filecmp.cmp(first, second, shallow=False)


def _merge_path(source: Path, destination: Path, *, moved_paths: list[str]) -> None:
    """Move source into destination without silently overwriting different data."""
    if source.is_dir():
        if destination.exists() and not destination.is_dir():
            raise FileExistsError(
                f"Cannot migrate directory '{source}' because destination is a file: '{destination}'."
            )
        destination.mkdir(parents=True, exist_ok=True)
        for child in list(source.iterdir()):
            _merge_path(child, destination / child.name, moved_paths=moved_paths)
        source.rmdir()
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if _files_are_identical(source, destination):
            source.unlink()
            return
        raise FileExistsError(
            "Cannot automatically merge legacy main-experiment outputs because both locations "
            f"contain different files: '{source}' and '{destination}'."
        )

    shutil.move(str(source), str(destination))
    moved_paths.append(str(destination))


def _remove_empty_directory(path: Path) -> None:
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def _migrate_project_level_files(*, moved_paths: list[str], removed_paths: list[str]) -> None:
    PROJECT_LEVEL_FILES_ROOT.mkdir(parents=True, exist_ok=True)

    root_readme = OUTPUTS_MAIN_ROOT / "readme.txt"
    if root_readme.exists():
        _merge_path(
            root_readme,
            PROJECT_LEVEL_FILES_ROOT / root_readme.name,
            moved_paths=moved_paths,
        )

    legacy_metrics_root = OUTPUTS_MAIN_ROOT / "metrics_data"
    if not legacy_metrics_root.is_dir():
        return

    for file_path in list(legacy_metrics_root.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.name.startswith("main_experiment_") and file_path.suffix == ".csv":
            file_path.unlink()
            removed_paths.append(str(file_path))
            continue
        if file_path.name in _LEGACY_PROJECT_LEVEL_METRICS_FILE_NAMES:
            file_path.unlink()
            removed_paths.append(str(file_path))
            continue
        _merge_path(
            file_path,
            PROJECT_LEVEL_FILES_ROOT / file_path.name,
            moved_paths=moved_paths,
        )


def _migrate_standard_artifact_root(
    artifact_name: str,
    *,
    moved_paths: list[str],
) -> None:
    legacy_root = OUTPUTS_MAIN_ROOT / artifact_name
    if not legacy_root.is_dir():
        return

    for category_dir in list(legacy_root.iterdir()):
        if not category_dir.is_dir():
            continue
        for config_dir in list(category_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            destination = (
                OUTPUTS_MAIN_ROOT
                / category_dir.name
                / config_dir.name
                / artifact_name
            )
            _merge_path(config_dir, destination, moved_paths=moved_paths)
        _remove_empty_directory(category_dir)

    _remove_empty_directory(legacy_root)


def _migrate_metrics_inspection_root(
    *,
    moved_paths: list[str],
    removed_paths: list[str],
) -> None:
    artifact_name = "metrics_data_inspection"
    legacy_root = OUTPUTS_MAIN_ROOT / artifact_name
    if not legacy_root.is_dir():
        return

    for general_summary in list(legacy_root.glob("selected_map_configs_*_summary.json")):
        if general_summary.is_file():
            general_summary.unlink()
            removed_paths.append(str(general_summary))

    for category_dir in list(legacy_root.iterdir()):
        if not category_dir.is_dir():
            continue

        for child in list(category_dir.iterdir()):
            if child.is_dir():
                destination = (
                    OUTPUTS_MAIN_ROOT
                    / category_dir.name
                    / child.name
                    / artifact_name
                )
                _merge_path(child, destination, moved_paths=moved_paths)
                continue

            if child.name.endswith(_LEGACY_INSPECTION_RAW_DATA_SUFFIX):
                child.unlink()
                removed_paths.append(str(child))
                continue

            if child.name.endswith(_LEGACY_INSPECTION_EVALUATION_SUFFIX):
                config_name = child.name[: -len(_LEGACY_INSPECTION_EVALUATION_SUFFIX)]
                destination = (
                    OUTPUTS_MAIN_ROOT
                    / category_dir.name
                    / config_name
                    / artifact_name
                    / child.name
                )
                _merge_path(child, destination, moved_paths=moved_paths)
                continue

            raise ValueError(
                "Cannot infer the exact map configuration for legacy metrics-inspection file "
                f"'{child}'."
            )

        _remove_empty_directory(category_dir)

    _remove_empty_directory(legacy_root)



def _replace_legacy_path_references(
    text: str,
    *,
    category_name: str,
    config_name: str,
) -> str:
    updated = text
    for separator in ("/", "\\", "\\\\"):
        old_outputs_root = f"outputs_main{separator}"
        new_config_root = (
            f"outputs_main{separator}{category_name}{separator}{config_name}"
        )

        updated = updated.replace(
            f"{old_outputs_root}metrics_data{separator}data_dictionary.csv",
            f"{old_outputs_root}project_level_files{separator}data_dictionary.csv",
        )
        updated = updated.replace(
            f"{old_outputs_root}readme.txt",
            f"{old_outputs_root}project_level_files{separator}readme.txt",
        )

        for artifact_name in (
            "frame_by_frame",
            "metrics_data",
            "terminal_logs",
            "visualization",
        ):
            old_config_artifact_root = (
                f"{old_outputs_root}{artifact_name}{separator}"
                f"{category_name}{separator}{config_name}"
            )
            new_config_artifact_root = (
                f"{new_config_root}{separator}{artifact_name}"
            )
            updated = updated.replace(
                old_config_artifact_root,
                new_config_artifact_root,
            )

        for inspection_suffix in (
            _LEGACY_INSPECTION_EVALUATION_SUFFIX,
            _LEGACY_INSPECTION_RAW_DATA_SUFFIX,
        ):
            old_inspection_file = (
                f"{old_outputs_root}metrics_data_inspection{separator}"
                f"{category_name}{separator}{config_name}{inspection_suffix}"
            )
            new_inspection_file = (
                f"{new_config_root}{separator}metrics_data_inspection{separator}"
                f"{config_name}{inspection_suffix}"
            )
            updated = updated.replace(old_inspection_file, new_inspection_file)

        for artifact_name in MAIN_OUTPUT_ARTIFACT_DIR_NAMES:
            updated = updated.replace(
                f"{old_outputs_root}{artifact_name}",
                f"{new_config_root}{separator}{artifact_name}",
            )

    return updated


def _rewrite_migrated_config_text_paths() -> list[str]:
    rewritten_files: list[str] = []
    if not OUTPUTS_MAIN_ROOT.is_dir():
        return rewritten_files

    excluded_root_names = {
        PROJECT_LEVEL_FILES_DIR_NAME,
        *MAIN_OUTPUT_ARTIFACT_DIR_NAMES,
    }
    for category_dir in OUTPUTS_MAIN_ROOT.iterdir():
        if not category_dir.is_dir() or category_dir.name in excluded_root_names:
            continue
        for config_dir in category_dir.iterdir():
            if not config_dir.is_dir():
                continue
            for file_path in config_dir.rglob("*"):
                if not file_path.is_file() or file_path.suffix.lower() not in _TEXT_OUTPUT_SUFFIXES:
                    continue
                try:
                    original = file_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                updated = _replace_legacy_path_references(
                    original,
                    category_name=category_dir.name,
                    config_name=config_dir.name,
                )
                if updated == original:
                    continue
                file_path.write_text(updated, encoding="utf-8")
                rewritten_files.append(str(file_path))

    return rewritten_files


def migrate_legacy_main_output_layout() -> dict[str, Any]:
    """Migrate the artifact-first outputs_main layout to the map-config-first layout.

    The operation is idempotent. It removes only known obsolete project-level files and
    refuses to overwrite different files when old and new layouts coexist.
    """
    OUTPUTS_MAIN_ROOT.mkdir(parents=True, exist_ok=True)
    moved_paths: list[str] = []
    removed_paths: list[str] = []

    _migrate_project_level_files(
        moved_paths=moved_paths,
        removed_paths=removed_paths,
    )
    for artifact_name in (
        "frame_by_frame",
        "metrics_data",
        "terminal_logs",
        "visualization",
    ):
        _migrate_standard_artifact_root(
            artifact_name,
            moved_paths=moved_paths,
        )
    _migrate_metrics_inspection_root(
        moved_paths=moved_paths,
        removed_paths=removed_paths,
    )
    rewritten_path_reference_files = _rewrite_migrated_config_text_paths()

    return {
        "layout": "map_config_first",
        "outputs_main_root": str(OUTPUTS_MAIN_ROOT),
        "project_level_files_root": str(PROJECT_LEVEL_FILES_ROOT),
        "moved_paths": moved_paths,
        "removed_obsolete_paths": removed_paths,
        "rewritten_path_reference_files": rewritten_path_reference_files,
        "migrated": bool(moved_paths or removed_paths or rewritten_path_reference_files),
    }
