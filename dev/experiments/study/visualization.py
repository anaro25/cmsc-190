from __future__ import annotations

import re
from collections import OrderedDict
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
    visually_free_vertex_positions: set[tuple[int, int]] | None = None,
) -> list[Path]:
    write_empty_map_config_frame(
        map_name=mapping_name,
        composite_map=composite_map,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
    )
    write_showcase_frame(
        map_name=mapping_name,
        composite_map=composite_map,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
    )
    write_setup_frame(
        map_name=mapping_name,
        composite_map=composite_map,
        agents=agents,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
    )
    return write_mapf_frames(
        map_name=mapping_name,
        composite_map=composite_map,
        agents=agents,
        paths_by_agent=paths_by_agent,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
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
    visually_free_vertex_positions: set[tuple[int, int]] | None = None,
) -> list[Path]:
    write_dynamic_obstacle_only_frame(
        map_name=mapping_name,
        composite_map=setup_composite_map,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
    )
    write_dynamic_showcase_frame(
        map_name=mapping_name,
        composite_map=setup_composite_map,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
    )
    write_dynamic_setup_frame(
        map_name=mapping_name,
        composite_map=setup_composite_map,
        agents=agents,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
    )
    return write_dynamic_mapf_frames(
        map_name=mapping_name,
        composite_loop=composite_loop,
        dynamic_matrix_loop=dynamic_matrix_loop,
        agents=agents,
        paths_by_agent=paths_by_agent,
        output_root=run_output_dir,
        visually_free_vertex_positions=visually_free_vertex_positions,
        nest_by_map=False,
    )


def _render_candidate(
    *,
    branch_spec: BranchSpec,
    dynamic_state: DynamicBranchState | None,
    candidate: VisualizationCandidate,
    run_output_dir: Path,
    classical_setup_map: list[list[Any]] | None,
    cyclic_setup_map: list[list[Any]] | None,
) -> list[Path]:
    mapping_name = candidate.mapping_name
    if branch_spec.is_dynamic:
        if dynamic_state is None:
            raise ValueError("dynamic_state is required for dynamic visualization rendering")
        composite_loop = dynamic_state.classical_loop if mapping_name == "classical" else dynamic_state.cyclic_loop
        setup_composite_map = classical_setup_map if mapping_name == "classical" else cyclic_setup_map
        if setup_composite_map is None:
            raise ValueError("missing dynamic setup map for visualization rendering")
        return _render_dynamic_mapping(
            mapping_name=mapping_name,
            composite_loop=composite_loop,
            dynamic_matrix_loop=dynamic_state.dynamic_loop_frames,
            setup_composite_map=setup_composite_map,
            agents=candidate.agents,
            paths_by_agent=candidate.solver_result["paths_by_agent"],
            run_output_dir=run_output_dir,
            visually_free_vertex_positions=dynamic_state.visually_free_vertices or None,
        )

    if candidate.composite_map is None:
        raise ValueError("static visualization candidates require composite_map")
    return _render_static_mapping(
        mapping_name=mapping_name,
        composite_map=candidate.composite_map,
        agents=candidate.agents,
        paths_by_agent=candidate.solver_result["paths_by_agent"],
        run_output_dir=run_output_dir,
        visually_free_vertex_positions=None,
    )


def _build_joint_groups(
    all_candidates: list[VisualizationCandidate],
) -> list[dict[str, VisualizationCandidate]]:
    grouped: OrderedDict[str, dict[str, VisualizationCandidate]] = OrderedDict()
    for candidate in all_candidates:
        grouped.setdefault(candidate.run_configuration.run_config_id, {})[candidate.mapping_name] = candidate
    return [
        group
        for group in grouped.values()
        if "classical" in group and "cyclic" in group
    ]



def _empty_selection_section(*, selection_mode: str, num_last_runs_to_visualize: int, output_root: Path) -> dict[str, Any]:
    return {
        "selection_mode": selection_mode,
        "num_last_runs_to_visualize": int(num_last_runs_to_visualize),
        "selected_agent_numbers": [],
        "selected_agent_numbers_by_mapping": {"classical": [], "cyclic": []},
        "selected_run_configurations": [],
        "selected_run_configurations_by_mapping": {"classical": [], "cyclic": []},
        "visualizations_root": str(output_root),
        "notes": "",
    }


def _write_visualization_summary(
    *,
    output_manager: BranchOutputManager,
    summary: dict[str, Any],
    logger: ExperimentLogger,
) -> None:
    summary_path = output_manager.metadata_dir / "visualization_selection_summary.json"
    write_json(summary_path, summary)
    logger.log(f"Visualization summary written to {summary_path}")


def _render_jointly_successful_visualizations(
    *,
    branch_spec: BranchSpec,
    output_root: Path,
    dynamic_state: DynamicBranchState | None,
    all_candidates: list[VisualizationCandidate],
    logger: ExperimentLogger,
    num_last_runs_to_visualize: int,
    classical_setup_map: list[list[Any]] | None,
    cyclic_setup_map: list[list[Any]] | None,
) -> dict[str, Any]:
    section = _empty_selection_section(
        selection_mode="jointly_successful_mappings",
        num_last_runs_to_visualize=num_last_runs_to_visualize,
        output_root=output_root,
    )
    if num_last_runs_to_visualize <= 0:
        section["notes"] = (
            "Jointly successful visualization generation skipped because "
            "num_last_runs_to_visualize_jointly_successful <= 0."
        )
        logger.log(
            "Jointly successful visualization generation skipped because "
            "num_last_runs_to_visualize_jointly_successful <= 0."
        )
        return section

    joint_groups = _build_joint_groups(all_candidates)
    selected_groups = joint_groups[-num_last_runs_to_visualize :]
    if not selected_groups:
        section["notes"] = (
            "No jointly successful classical-cyclic run configurations were available among the "
            "reported branch results, so no jointly successful Pillow visualizations were generated."
        )
        logger.log(
            "No jointly successful classical-cyclic run configurations were available, "
            "so the jointly successful visualization folder was left empty."
        )
        return section

    classical_root = output_root / "classical"
    cyclic_root = output_root / "cyclic"
    classical_root.mkdir(parents=True, exist_ok=True)
    cyclic_root.mkdir(parents=True, exist_ok=True)
    logger.log("")
    logger.log("Generating jointly successful Pillow visualizations...")

    for selection_index, group in enumerate(selected_groups, start=1):
        classical_candidate = group["classical"]
        cyclic_candidate = group["cyclic"]
        run_configuration = classical_candidate.run_configuration
        run_slug = _slugify(run_configuration.run_config_id)
        agent_number = run_configuration.agent_number
        classical_run_output_dir = classical_root / (
            f"selection_{selection_index:02d}__agent_number_{agent_number:03d}__{run_slug}"
        )
        cyclic_run_output_dir = cyclic_root / (
            f"selection_{selection_index:02d}__agent_number_{agent_number:03d}__{run_slug}"
        )
        classical_run_output_dir.mkdir(parents=True, exist_ok=True)
        cyclic_run_output_dir.mkdir(parents=True, exist_ok=True)
        logger.log(
            f"  Rendering jointly successful visualization set {selection_index}/{len(selected_groups)} | "
            f"run_config_id={run_configuration.run_config_id}"
        )

        classical_frames = _render_candidate(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            candidate=classical_candidate,
            run_output_dir=classical_run_output_dir,
            classical_setup_map=classical_setup_map,
            cyclic_setup_map=cyclic_setup_map,
        )
        cyclic_frames = _render_candidate(
            branch_spec=branch_spec,
            dynamic_state=dynamic_state,
            candidate=cyclic_candidate,
            run_output_dir=cyclic_run_output_dir,
            classical_setup_map=classical_setup_map,
            cyclic_setup_map=cyclic_setup_map,
        )

        record = {
            "selection_index": selection_index,
            "run_config_id": run_configuration.run_config_id,
            "agent_number": run_configuration.agent_number,
            "run_index": run_configuration.run_index,
            "assignment_seed": run_configuration.assignment_seed,
            "map_identifier": run_configuration.map_identifier,
            "output_dir": {
                "classical": str(classical_run_output_dir),
                "cyclic": str(cyclic_run_output_dir),
            },
            "classical_dir": str(classical_run_output_dir),
            "cyclic_dir": str(cyclic_run_output_dir),
            "classical_num_frames": len(classical_frames),
            "cyclic_num_frames": len(cyclic_frames),
        }
        section["selected_run_configurations"].append(record)
        section["selected_agent_numbers"].append(run_configuration.agent_number)
        section["selected_agent_numbers_by_mapping"]["classical"].append(run_configuration.agent_number)
        section["selected_agent_numbers_by_mapping"]["cyclic"].append(run_configuration.agent_number)
        section["selected_run_configurations_by_mapping"]["classical"].append(record)
        section["selected_run_configurations_by_mapping"]["cyclic"].append(record)

    section["notes"] = (
        "These are the final jointly successful classical-cyclic run configurations from the "
        "reported experiment, limited by num_last_runs_to_visualize_jointly_successful."
    )
    return section


def _render_independently_successful_visualizations(
    *,
    branch_spec: BranchSpec,
    output_root: Path,
    dynamic_state: DynamicBranchState | None,
    all_candidates: list[VisualizationCandidate],
    logger: ExperimentLogger,
    num_last_runs_to_visualize: int,
    classical_setup_map: list[list[Any]] | None,
    cyclic_setup_map: list[list[Any]] | None,
) -> dict[str, Any]:
    section = _empty_selection_section(
        selection_mode="independently_successful_mappings",
        num_last_runs_to_visualize=num_last_runs_to_visualize,
        output_root=output_root,
    )
    if num_last_runs_to_visualize <= 0:
        section["notes"] = (
            "Independently successful visualization generation skipped because "
            "num_last_runs_to_visualize_independently_successful <= 0."
        )
        logger.log(
            "Independently successful visualization generation skipped because "
            "num_last_runs_to_visualize_independently_successful <= 0."
        )
        return section

    output_root.mkdir(parents=True, exist_ok=True)
    logger.log("")
    logger.log("Generating independently successful Pillow visualizations...")

    total_selected = 0
    for mapping_name in ("classical", "cyclic"):
        mapping_candidates = [
            candidate for candidate in all_candidates if candidate.mapping_name == mapping_name
        ]
        selected_candidates = mapping_candidates[-num_last_runs_to_visualize :]
        if not selected_candidates:
            logger.log(
                f"  No successful {mapping_name} runs were available for independent visualization selection."
            )
            continue

        mapping_root = output_root / mapping_name
        mapping_root.mkdir(parents=True, exist_ok=True)
        logger.log(
            f"  Rendering {len(selected_candidates)} independently successful {mapping_name} run(s)..."
        )

        for selection_index, candidate in enumerate(selected_candidates, start=1):
            run_configuration = candidate.run_configuration
            run_slug = _slugify(run_configuration.run_config_id)
            agent_number = run_configuration.agent_number
            run_output_dir = mapping_root / (
                f"selection_{selection_index:02d}__agent_number_{agent_number:03d}__{run_slug}"
            )
            run_output_dir.mkdir(parents=True, exist_ok=True)
            logger.log(
                f"    Rendering {mapping_name} visualization set {selection_index}/{len(selected_candidates)} | "
                f"run_config_id={run_configuration.run_config_id}"
            )
            frames = _render_candidate(
                branch_spec=branch_spec,
                dynamic_state=dynamic_state,
                candidate=candidate,
                run_output_dir=run_output_dir,
                classical_setup_map=classical_setup_map,
                cyclic_setup_map=cyclic_setup_map,
            )
            record = {
                "mapping_name": mapping_name,
                "selection_index": selection_index,
                "run_config_id": run_configuration.run_config_id,
                "agent_number": run_configuration.agent_number,
                "run_index": run_configuration.run_index,
                "assignment_seed": run_configuration.assignment_seed,
                "map_identifier": run_configuration.map_identifier,
                "output_dir": str(run_output_dir),
                "mapping_dir": str(run_output_dir),
                "num_frames": len(frames),
            }
            section["selected_run_configurations"].append(record)
            section["selected_run_configurations_by_mapping"][mapping_name].append(record)
            section["selected_agent_numbers"].append(run_configuration.agent_number)
            section["selected_agent_numbers_by_mapping"][mapping_name].append(run_configuration.agent_number)
            total_selected += 1

    if total_selected == 0:
        section["notes"] = (
            "No successful mapping-specific run configurations were available among the reported branch "
            "results, so no independently successful Pillow visualizations were generated."
        )
        logger.log(
            "No successful mapping-specific run configurations were available, "
            "so the independently successful visualization folder was left empty."
        )
        return section

    section["notes"] = (
        "These are the final independently successful runs per mapping from the reported experiment, "
        "limited by num_last_runs_to_visualize_independently_successful for each mapping."
    )
    return section


def render_selected_visualizations(
    *,
    branch_spec: BranchSpec,
    output_manager: BranchOutputManager,
    dynamic_state: DynamicBranchState | None,
    all_candidates: list[VisualizationCandidate],
    logger: ExperimentLogger,
    num_last_runs_to_visualize_jointly_successful: int | None = None,
    num_last_runs_to_visualize_independently_successful: int | None = None,
) -> dict[str, Any]:
    effective_jointly_successful_limit = (
        branch_spec.num_last_runs_to_visualize_jointly_successful
        if num_last_runs_to_visualize_jointly_successful is None
        else int(num_last_runs_to_visualize_jointly_successful)
    )
    effective_independently_successful_limit = (
        branch_spec.num_last_runs_to_visualize_independently_successful
        if num_last_runs_to_visualize_independently_successful is None
        else int(num_last_runs_to_visualize_independently_successful)
    )

    summary: dict[str, Any] = {
        "selection_config_source": "current_master_config",
        "visualizations_root": str(output_manager.visualizations_dir),
        "jointly_successful": {},
        "independently_successful": {},
        "total_selected_run_configurations": 0,
        "notes": "",
    }

    classical_setup_map = None
    cyclic_setup_map = None
    if branch_spec.is_dynamic:
        if dynamic_state is None:
            raise ValueError("dynamic_state is required for dynamic visualization rendering")
        classical_setup_map, cyclic_setup_map = build_static_only_setup_maps(dynamic_state.static_matrix)

    jointly_successful_root = output_manager.visualizations_dir / "jointly_successful"
    independently_successful_root = output_manager.visualizations_dir / "independently_successful"
    jointly_successful_root.mkdir(parents=True, exist_ok=True)
    independently_successful_root.mkdir(parents=True, exist_ok=True)

    summary["jointly_successful"] = _render_jointly_successful_visualizations(
        branch_spec=branch_spec,
        output_root=jointly_successful_root,
        dynamic_state=dynamic_state,
        all_candidates=all_candidates,
        logger=logger,
        num_last_runs_to_visualize=effective_jointly_successful_limit,
        classical_setup_map=classical_setup_map,
        cyclic_setup_map=cyclic_setup_map,
    )
    summary["independently_successful"] = _render_independently_successful_visualizations(
        branch_spec=branch_spec,
        output_root=independently_successful_root,
        dynamic_state=dynamic_state,
        all_candidates=all_candidates,
        logger=logger,
        num_last_runs_to_visualize=effective_independently_successful_limit,
        classical_setup_map=classical_setup_map,
        cyclic_setup_map=cyclic_setup_map,
    )
    summary["total_selected_run_configurations"] = (
        len(summary["jointly_successful"].get("selected_run_configurations", []))
        + len(summary["independently_successful"].get("selected_run_configurations", []))
    )

    if summary["total_selected_run_configurations"] == 0:
        summary["notes"] = (
            "No jointly successful or independently successful visualization selections were available, "
            "so no Pillow visualizations were generated."
        )
    else:
        summary["notes"] = (
            "Both jointly successful and independently successful visualization variants were generated "
            "using the current master_config.py selection limits."
        )

    _write_visualization_summary(output_manager=output_manager, summary=summary, logger=logger)
    return summary
