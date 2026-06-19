from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from dev.experiments.ref_comparison.io_utils import write_json
from dev.experiments.ref_comparison.models import RefVisualizationCandidate
from dev.mapf.mapf_logger import write_empty_map_config_frame, write_mapf_frames, write_setup_frame, write_showcase_frame


def _slugify(text: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return compact or "run"


def _select_candidates(
    candidates: list[RefVisualizationCandidate],
    *,
    num_last_successful_runs_per_mapping: int,
) -> list[RefVisualizationCandidate]:
    grouped: dict[str, list[RefVisualizationCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate.mapping_name].append(candidate)

    selected: list[RefVisualizationCandidate] = []
    for mapping_name in sorted(grouped):
        selected.extend(grouped[mapping_name][-max(0, int(num_last_successful_runs_per_mapping)) :])
    return selected


def render_reference_visualizations(
    *,
    candidates: list[RefVisualizationCandidate],
    output_root: Path,
    num_last_successful_runs_per_mapping: int,
) -> dict[str, Any]:
    selected = _select_candidates(
        candidates,
        num_last_successful_runs_per_mapping=num_last_successful_runs_per_mapping,
    )

    rendered_entries: list[dict[str, Any]] = []
    for candidate in selected:
        run_id_slug = _slugify(candidate.run_configuration.run_config_id)
        run_output_dir = output_root / run_id_slug / candidate.mapping_name
        run_output_dir.mkdir(parents=True, exist_ok=True)

        write_empty_map_config_frame(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            output_root=run_output_dir,
            nest_by_map=False,
        )
        write_showcase_frame(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            output_root=run_output_dir,
            nest_by_map=False,
        )
        write_setup_frame(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            agents=candidate.agents,
            output_root=run_output_dir,
            nest_by_map=False,
        )
        frame_paths = write_mapf_frames(
            map_name=candidate.mapping_name,
            composite_map=candidate.composite_map,
            agents=candidate.agents,
            paths_by_agent=candidate.solver_result["paths_by_agent"],
            output_root=run_output_dir,
            nest_by_map=False,
        )
        rendered_entries.append(
            {
                "case_id": candidate.case_spec.case_id,
                "mapping_name": candidate.mapping_name,
                "run_config_id": candidate.run_configuration.run_config_id,
                "run_index": candidate.run_configuration.run_index,
                "agent_number": candidate.run_configuration.agent_number,
                "frames_count": len(frame_paths),
                "output_dir": str(run_output_dir),
            }
        )

    summary = {
        "num_last_successful_runs_per_mapping": int(num_last_successful_runs_per_mapping),
        "available_candidates": len(candidates),
        "selected_candidates": len(selected),
        "rendered_entries": rendered_entries,
    }
    write_json(output_root / "visualization_summary.json", summary)
    return summary
