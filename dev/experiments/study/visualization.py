from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.dynamic_port.pipeline import build_static_only_setup_maps
from dev.experiments.study.io_utils import BranchOutputManager, ExperimentLogger, write_json
from dev.experiments.study.models import DynamicBranchState, VisualizationCandidate
from dev.mapf.mapf_logger import (
    write_empty_map_config_frame,
    write_mapf_frames,
    write_setup_frame,
    write_showcase_frame,
)
from dev.mapf.mapf_logger_dynamic import (
    write_dynamic_mapf_frames,
    write_dynamic_obstacle_only_frame,
    write_dynamic_setup_frame,
    write_dynamic_showcase_frame,
)


def _slugify(text: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return compact or "run"


def _render_static_mapping(
    *,
    mapping_name: str,
    composite_map: list[list[Any]],
    agents: list[dict[str, Any]],
    paths_by_agent: dict[int, list[tuple[int, int]]],
    run_output_dir: Path,
) -> list[Path]:
    write_empty_map_config_frame(
        map_name=mapping_name,
        composite_map=composite_map,
        output_root=run_output_dir,
    )
    write_showcase_frame(
        map_name=mapping_name,
        composite_map=composite_map,
        output_root=run_output_dir,
    )
    write_setup_frame(
        map_name=mapping_name,
        composite_map=composite_map,
        agents=agents,
        output_root=run_output_dir,
    )
    return write_mapf_frames(
        map_name=mapping_name,
        composite_map=composite_map,
        agents=agents,
        paths_by_agent=paths_by_agent,
        output_root=run_output_dir,
    )


def _render_dynamic_mapping(
    *,
    mapping_name: str,
    composite_loop: list[list[list[Any]]],
    dynamic_matrix_loop: list[list[list[int]]],
    setup_composite_map: list[list[Any]],
    agents: list[dict[str, Any]],
    paths_by_agent: dict[int, list[tuple[int, int]]],
    run_output_dir: Path,
) -> list[Path]:
    write_dynamic_obstacle_only_frame(
        map_name=mapping_name,
        composite_map=setup_composite_map,
        output_root=run_output_dir,
    )
    write_dynamic_showcase_frame(
        map_name=mapping_name,
        composite_map=setup_composite_map,
        output_root=run_output_dir,
    )
    write_dynamic_setup_frame(
        map_name=mapping_name,
        composite_map=setup_composite_map,
        agents=agents,
        output_root=run_output_dir,
    )
    return write_dynamic_mapf_frames(
        map_name=mapping_name,
        composite_loop=composite_loop,
        dynamic_matrix_loop=dynamic_matrix_loop,
        agents=agents,
        paths_by_agent=paths_by_agent,
        output_root=run_output_dir,
    )


def render_selected_visualizations(
    *,
    branch_spec: BranchSpec,
    output_manager: BranchOutputManager,
    dynamic_state: DynamicBranchState | None,
    selected_candidates: list[VisualizationCandidate],
    logger: ExperimentLogger,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "num_last_runs_to_visualize": branch_spec.num_last_runs_to_visualize,
        "selected_agent_numbers": [],
        "selected_run_configurations": [],
        "visualizations_root": str(output_manager.visualizations_dir),
        "notes": "",
    }

    if branch_spec.num_last_runs_to_visualize <= 0:
        summary["notes"] = "Visualization disabled because num_last_runs_to_visualize <= 0."
        write_json(output_manager.metadata_dir / "visualization_selection_summary.json", summary)
        logger.log("Visualization rendering skipped because num_last_runs_to_visualize <= 0.")
        return summary

    if not selected_candidates:
        summary["notes"] = (
            "No fully successful paired run configurations were available among the reported branch results, "
            "so no Pillow visualizations were generated."
        )
        write_json(output_manager.metadata_dir / "visualization_selection_summary.json", summary)
        logger.log(
            "Visualization rendering skipped because no fully successful paired run configurations "
            "were available in the reported branch results."
        )
        return summary

    selected_root = output_manager.visualizations_dir / "selected_successful_runs"
    selected_root.mkdir(parents=True, exist_ok=True)
    logger.log("")
    logger.log(
        "Generating Pillow visualizations for the final successful paired runs of the entire experiment..."
    )

    classical_setup_map = None
    cyclic_setup_map = None
    if branch_spec.is_dynamic:
        if dynamic_state is None:
            raise ValueError("dynamic_state is required for dynamic visualization rendering")
        classical_setup_map, cyclic_setup_map = build_static_only_setup_maps(dynamic_state.static_matrix)

    for selection_index, candidate in enumerate(selected_candidates, start=1):
        run_slug = _slugify(candidate.run_configuration.run_config_id)
        agent_number = candidate.run_configuration.agent_number
        run_output_dir = selected_root / (
            f"selection_{selection_index:02d}__agent_number_{agent_number:03d}__{run_slug}"
        )
        run_output_dir.mkdir(parents=True, exist_ok=True)
        logger.log(
            f"  Rendering visualization set {selection_index}/{len(selected_candidates)} | "
            f"run_config_id={candidate.run_configuration.run_config_id}"
        )

        if branch_spec.is_dynamic:
            classical_frames = _render_dynamic_mapping(
                mapping_name="classical",
                composite_loop=dynamic_state.classical_loop,
                dynamic_matrix_loop=dynamic_state.dynamic_loop_frames,
                setup_composite_map=classical_setup_map,
                agents=candidate.agents,
                paths_by_agent=candidate.classical_solver_result["paths_by_agent"],
                run_output_dir=run_output_dir,
            )
            cyclic_frames = _render_dynamic_mapping(
                mapping_name="cyclic",
                composite_loop=dynamic_state.cyclic_loop,
                dynamic_matrix_loop=dynamic_state.dynamic_loop_frames,
                setup_composite_map=cyclic_setup_map,
                agents=candidate.agents,
                paths_by_agent=candidate.cyclic_solver_result["paths_by_agent"],
                run_output_dir=run_output_dir,
            )
        else:
            if candidate.classical_map is None or candidate.cyclic_map is None:
                raise ValueError("static visualization candidates require classical_map and cyclic_map")
            classical_frames = _render_static_mapping(
                mapping_name="classical",
                composite_map=candidate.classical_map,
                agents=candidate.agents,
                paths_by_agent=candidate.classical_solver_result["paths_by_agent"],
                run_output_dir=run_output_dir,
            )
            cyclic_frames = _render_static_mapping(
                mapping_name="cyclic",
                composite_map=candidate.cyclic_map,
                agents=candidate.agents,
                paths_by_agent=candidate.cyclic_solver_result["paths_by_agent"],
                run_output_dir=run_output_dir,
            )

        summary["selected_run_configurations"].append(
            {
                "selection_index": selection_index,
                "run_config_id": candidate.run_configuration.run_config_id,
                "agent_number": candidate.run_configuration.agent_number,
                "run_index": candidate.run_configuration.run_index,
                "assignment_seed": candidate.run_configuration.assignment_seed,
                "map_identifier": candidate.run_configuration.map_identifier,
                "output_dir": str(run_output_dir),
                "classical_dir": str(run_output_dir / "classical"),
                "cyclic_dir": str(run_output_dir / "cyclic"),
                "classical_num_frames": len(classical_frames),
                "cyclic_num_frames": len(cyclic_frames),
            }
        )

    summary["selected_agent_numbers"] = [
        candidate.run_configuration.agent_number for candidate in selected_candidates
    ]
    summary["notes"] = (
        "These are the final successful paired run configurations from the entire reported experiment, "
        "limited by num_last_runs_to_visualize."
    )
    write_json(output_manager.metadata_dir / "visualization_selection_summary.json", summary)
    logger.log(f"Visualization summary written to {output_manager.metadata_dir / 'visualization_selection_summary.json'}")
    return summary
