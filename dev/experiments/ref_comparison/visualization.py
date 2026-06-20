from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from dev.experiments.ref_comparison.io_utils import write_json
from dev.experiments.ref_comparison.models import RefVisualizationCandidate
from dev.experiments.ref_comparison.runtime import load_reference_port_obstacle_data
from dev.mapf.mapf_logger import write_empty_map_config_frame, write_mapf_frames, write_setup_frame, write_showcase_frame


def _slugify(text: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return compact or "run"


def _candidate_selection_key(candidate: RefVisualizationCandidate) -> tuple[int | str, str]:
    """Select visualization runs independently for each map and mapping.

    The reference-comparison experiment compares three different port maps.
    A plain mapping-only grouping would keep only the last classical/cyclic
    candidate overall, which usually means only one port map is rendered.
    """
    map_number = candidate.run_configuration.map_number
    if map_number is None:
        map_number = candidate.run_configuration.map_identifier or candidate.run_configuration.run_config_id
    return map_number, candidate.mapping_name


def _select_candidates(
    candidates: list[RefVisualizationCandidate],
    *,
    num_last_successful_runs_per_mapping: int,
) -> list[RefVisualizationCandidate]:
    grouped: dict[tuple[int | str, str], list[RefVisualizationCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[_candidate_selection_key(candidate)].append(candidate)

    selected: list[RefVisualizationCandidate] = []
    limit = max(0, int(num_last_successful_runs_per_mapping))
    if limit <= 0:
        return selected
    for key in sorted(grouped, key=lambda item: (str(item[0]), item[1])):
        selected.extend(grouped[key][-limit:])
    return selected


def _log(progress_logger: Callable[[str], None] | None, message: str) -> None:
    if progress_logger is not None:
        progress_logger(message)


def _resolve_visually_free_vertices(candidate: RefVisualizationCandidate) -> set[tuple[int, int]] | None:
    existing = getattr(candidate, "visually_free_vertex_positions", None)
    if existing:
        return set(existing)

    # Backward-compatible fallback for raw payloads saved before invisible
    # obstacles were stored on visualization candidates. The current input image
    # is authoritative for visualization-only regeneration.
    try:
        map_index = candidate.run_configuration.map_index
        map_paths = list(candidate.case_spec.map_image_paths or [])
        if map_index is None or map_index < 0 or map_index >= len(map_paths):
            return None
        loaded = load_reference_port_obstacle_data(map_paths[map_index])
        vertices = loaded.get("invisible_obstacle_vertices") or set()
        return set(vertices) or None
    except Exception:
        return None


def render_reference_visualizations(
    *,
    candidates: list[RefVisualizationCandidate],
    output_root: Path,
    num_last_successful_runs_per_mapping: int,
    progress_logger: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    selected = _select_candidates(
        candidates,
        num_last_successful_runs_per_mapping=num_last_successful_runs_per_mapping,
    )

    available_map_numbers = sorted(
        {
            candidate.run_configuration.map_number
            for candidate in candidates
            if candidate.run_configuration.map_number is not None
        }
    )
    selected_map_numbers = sorted(
        {
            candidate.run_configuration.map_number
            for candidate in selected
            if candidate.run_configuration.map_number is not None
        }
    )

    _log(
        progress_logger,
        "Visualization selection | "
        f"available_candidates={len(candidates)} | selected_candidates={len(selected)} | "
        f"available_maps={available_map_numbers or 'n/a'} | selected_maps={selected_map_numbers or 'n/a'}",
    )

    rendered_entries: list[dict[str, Any]] = []
    total_selected = len(selected)
    for render_index, candidate in enumerate(selected, start=1):
        map_number = candidate.run_configuration.map_number
        map_label = candidate.run_configuration.map_label or (f"Map {map_number}" if map_number is not None else "Map n/a")
        _log(
            progress_logger,
            f"Rendering visualization {render_index}/{total_selected} | "
            f"{map_label} | mapping={candidate.mapping_name} | "
            f"run_config_id={candidate.run_configuration.run_config_id}",
        )

        visually_free_vertex_positions = _resolve_visually_free_vertices(candidate)
        visually_free_count = len(visually_free_vertex_positions or [])
        run_id_slug = _slugify(candidate.run_configuration.run_config_id)
        run_output_dir = output_root / run_id_slug / candidate.mapping_name
        run_output_dir.mkdir(parents=True, exist_ok=True)

        _log(progress_logger, f"  Invisible obstacles rendered as free cells: {visually_free_count}")
        _log(progress_logger, f"  Writing empty-map frame -> {run_output_dir}")
        write_empty_map_config_frame(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            output_root=run_output_dir,
            visually_free_vertex_positions=visually_free_vertex_positions,
            nest_by_map=False,
        )
        _log(progress_logger, "  Writing showcase frame")
        write_showcase_frame(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            output_root=run_output_dir,
            visually_free_vertex_positions=visually_free_vertex_positions,
            nest_by_map=False,
        )
        _log(progress_logger, "  Writing setup frame")
        write_setup_frame(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            agents=candidate.agents,
            output_root=run_output_dir,
            visually_free_vertex_positions=visually_free_vertex_positions,
            nest_by_map=False,
        )
        _log(progress_logger, "  Writing MAPF execution frames")
        frame_paths = write_mapf_frames(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            agents=candidate.agents,
            paths_by_agent=candidate.solver_result["paths_by_agent"],
            output_root=run_output_dir,
            visually_free_vertex_positions=visually_free_vertex_positions,
            nest_by_map=False,
        )
        _log(progress_logger, f"  Done | frames_count={len(frame_paths)}")
        rendered_entries.append(
            {
                "case_id": candidate.case_spec.case_id,
                "mapping_name": candidate.mapping_name,
                "run_config_id": candidate.run_configuration.run_config_id,
                "run_index": candidate.run_configuration.run_index,
                "agent_number": candidate.run_configuration.agent_number,
                "map_index": candidate.run_configuration.map_index,
                "map_number": candidate.run_configuration.map_number,
                "map_label": candidate.run_configuration.map_label,
                "map_identifier": candidate.run_configuration.map_identifier,
                "invisible_obstacles_rendered_as_free": visually_free_count,
                "frames_count": len(frame_paths),
                "output_dir": str(run_output_dir),
            }
        )

    summary = {
        "num_last_successful_runs_per_mapping": int(num_last_successful_runs_per_mapping),
        "available_candidates": len(candidates),
        "selected_candidates": len(selected),
        "available_map_numbers": available_map_numbers,
        "selected_map_numbers": selected_map_numbers,
        "rendered_entries": rendered_entries,
    }
    write_json(output_root / "visualization_summary.json", summary)
    _log(progress_logger, f"Visualization summary written -> {output_root / 'visualization_summary.json'}")
    return summary
