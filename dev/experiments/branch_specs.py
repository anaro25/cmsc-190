from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


# STATIC_AGENT_NUMBERS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40]
STATIC_AGENT_NUMBERS = [12, 16, 20]  # temporary
DYNAMIC_AGENT_NUMBERS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]


@dataclass(frozen=True)
class BranchSpec:
    map_type: str
    branch_id: str
    branch_decimal: str
    map_obstacle_type: str
    map_obstacle_index: int
    map_type_index: int
    display_name: str
    target_type_documented: str
    target_type_active: str
    agent_numbers: list[int]
    runtime_limit_seconds: float
    counted_runs_required: int
    path_length_graph_enabled: bool
    is_dynamic: bool
    base_rows: int | None = None
    base_cols: int | None = None
    static_obstacle_density: float | None = None
    image_path: str | None = None
    image_threshold: int = 127
    image_resize_longest_side: int | None = None
    dynamic_target_static_obstacle_density: float | None = None
    dynamic_target_dynamic_obstacle_density: float | None = None
    dynamic_loop_sequence_length: int | None = None
    dynamic_group_stay_durations: tuple[int, ...] | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.image_path is not None:
            payload["image_path"] = str(Path(self.image_path))
        return payload


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
INPUTS_ROOT = PACKAGE_ROOT / "inputs"


BRANCH_SPECS: dict[str, BranchSpec] = {
    "static_artificial": BranchSpec(
        map_type="static_artificial",
        branch_id="static_artificial",
        branch_decimal="0.0",
        map_obstacle_type="static",
        map_obstacle_index=0,
        map_type_index=0,
        display_name="Static Artificial",
        target_type_documented="scattered_targets",
        target_type_active="scattered_targets",
        agent_numbers=STATIC_AGENT_NUMBERS,
        runtime_limit_seconds=30.0,
        counted_runs_required=5,
        path_length_graph_enabled=True,
        is_dynamic=False,
        base_rows=25,
        base_cols=25,
        static_obstacle_density=0.40,
        notes=(
            "Fresh 25x25 artificial map per run configuration. "
            "Scattered targets are used. Counted runs are the runs classified as "
            "successful or unfinished."
        ),
    ),
    "dynamic_port": BranchSpec(
        map_type="dynamic_port",
        branch_id="dynamic_port",
        branch_decimal="1.0",
        map_obstacle_type="dynamic",
        map_obstacle_index=1,
        map_type_index=0,
        display_name="Dynamic Port",
        target_type_documented="scattered_targets",
        target_type_active="scattered_targets",
        agent_numbers=DYNAMIC_AGENT_NUMBERS,
        runtime_limit_seconds=30.0,
        counted_runs_required=5,
        path_length_graph_enabled=False,
        is_dynamic=True,
        image_path=str(INPUTS_ROOT / "dynamic_port" / "port_map" / "port_map.png"),
        image_threshold=127,
        image_resize_longest_side=40,
        dynamic_target_static_obstacle_density=None,
        dynamic_target_dynamic_obstacle_density=0.005,
        dynamic_loop_sequence_length=30,
        dynamic_group_stay_durations=(3, 4, 5),
        notes=(
            "Image-based dynamic branch. The implementation preserves the source-map "
            "static density, downsizes the large port image to longest-side 40 for "
            "practical runtime, and uses a conservative dynamic density (0.005). "
            "Counted runs are the runs classified as successful or unfinished."
        ),
    ),
    "dynamic_campus_area_1": BranchSpec(
        map_type="dynamic_campus_area_1",
        branch_id="dynamic_campus_area_1",
        branch_decimal="1.1",
        map_obstacle_type="dynamic",
        map_obstacle_index=1,
        map_type_index=1,
        display_name="Dynamic Campus Area 1",
        target_type_documented="single_cell_target",
        target_type_active="scattered_targets",
        agent_numbers=DYNAMIC_AGENT_NUMBERS,
        runtime_limit_seconds=30.0,
        counted_runs_required=5,
        path_length_graph_enabled=False,
        is_dynamic=True,
        image_path=str(INPUTS_ROOT / "dynamic_campus_area_1" / "campus_area_1_x80.png"),
        image_threshold=127,
        dynamic_target_static_obstacle_density=None,
        dynamic_target_dynamic_obstacle_density=0.005,
        dynamic_loop_sequence_length=30,
        dynamic_group_stay_durations=(3, 4, 5),
        notes=(
            "The experimental design documents campus maps as single-cell target cases, "
            "but the current implementation deliberately uses scattered targets. The "
            "source-map static density is preserved and a light dynamic density (0.005) "
            "is used by default. Counted runs are the runs classified as successful or "
            "unfinished."
        ),
    ),
    "dynamic_campus_area_2": BranchSpec(
        map_type="dynamic_campus_area_2",
        branch_id="dynamic_campus_area_2",
        branch_decimal="1.2",
        map_obstacle_type="dynamic",
        map_obstacle_index=1,
        map_type_index=2,
        display_name="Dynamic Campus Area 2",
        target_type_documented="single_cell_target",
        target_type_active="scattered_targets",
        agent_numbers=DYNAMIC_AGENT_NUMBERS,
        runtime_limit_seconds=30.0,
        counted_runs_required=5,
        path_length_graph_enabled=False,
        is_dynamic=True,
        image_path=str(INPUTS_ROOT / "dynamic_campus_area_2" / "campus_area_2_x80.png"),
        image_threshold=127,
        dynamic_target_static_obstacle_density=None,
        dynamic_target_dynamic_obstacle_density=0.005,
        dynamic_loop_sequence_length=30,
        dynamic_group_stay_durations=(3, 4, 5),
        notes=(
            "The experimental design documents campus maps as single-cell target cases, "
            "but the current implementation deliberately uses scattered targets. The "
            "source-map static density is preserved and a light dynamic density (0.005) "
            "is used by default. Counted runs are the runs classified as successful or "
            "unfinished."
        ),
    ),
}


def get_branch_spec(map_type: str) -> BranchSpec:
    try:
        return BRANCH_SPECS[map_type]
    except KeyError as exc:
        raise ValueError(
            "MAP_TYPE must be one of: " + ", ".join(sorted(BRANCH_SPECS))
        ) from exc
