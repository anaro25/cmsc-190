from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dev.master_config import BRANCH_USER_CONFIGS


AgentNumberRange = tuple[int, int, int]


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
    seed_base: int
    agent_number_range: AgentNumberRange
    agent_numbers: list[int]
    runtime_limit_seconds: float
    counted_runs_required: int
    num_last_runs_to_visualize: int
    require_jointly_successful_mappings: bool
    path_length_graph_enabled: bool
    is_dynamic: bool
    single_cell_target: bool = False
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
    dynamic_generation_cell_mode: str = "all_free"
    spawnable_cell_mode: str = "all_free"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.image_path is not None:
            payload["image_path"] = str(Path(self.image_path))
        return payload


def expand_agent_number_range(agent_number_range: AgentNumberRange) -> list[int]:
    start, max_agent_number, step = agent_number_range
    if start <= 0:
        raise ValueError("agent_number_range start must be positive")
    if step <= 0:
        raise ValueError("agent_number_range step must be positive")
    if max_agent_number < start:
        raise ValueError("agent_number_range max must be greater than or equal to start")
    return list(range(start, max_agent_number + 1, step))


def _campus_target_type(config: dict[str, Any]) -> str:
    return "single_cell_target" if bool(config.get("single_cell_target", False)) else "scattered_targets"


def _build_branch_specs() -> dict[str, BranchSpec]:
    static_cfg = BRANCH_USER_CONFIGS["static_artificial"]
    port_cfg = BRANCH_USER_CONFIGS["dynamic_port"]
    campus_1_cfg = BRANCH_USER_CONFIGS["dynamic_campus_area_1"]
    campus_2_cfg = BRANCH_USER_CONFIGS["dynamic_campus_area_2"]

    static_range = tuple(static_cfg["agent_number_range"])
    port_range = tuple(port_cfg["agent_number_range"])
    campus_1_range = tuple(campus_1_cfg["agent_number_range"])
    campus_2_range = tuple(campus_2_cfg["agent_number_range"])
    campus_1_target_type = _campus_target_type(campus_1_cfg)
    campus_2_target_type = _campus_target_type(campus_2_cfg)

    return {
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
            seed_base=int(static_cfg["seed"]),
            agent_number_range=static_range,
            agent_numbers=expand_agent_number_range(static_range),
            runtime_limit_seconds=float(static_cfg["time_limit_seconds"]),
            counted_runs_required=int(static_cfg["counted_runs_required"]),
            num_last_runs_to_visualize=int(static_cfg.get("num_last_runs_to_visualize", 0)),
            require_jointly_successful_mappings=bool(static_cfg.get("require_jointly_successful_mappings", True)),
            path_length_graph_enabled=True,
            is_dynamic=False,
            base_rows=int(static_cfg["map_size"][0]),
            base_cols=int(static_cfg["map_size"][1]),
            static_obstacle_density=float(static_cfg["static_obstacle_density"]),
            notes=(
                "Fresh artificial map per run configuration. Scattered targets are used. "
                "Retained pairs are the run configurations for which both mappings are classified as successful or unfinished. "
                "Agent numbers are generated from agent_number_range and the branch can stop early if the stopping rules trigger."
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
            seed_base=int(port_cfg["seed"]),
            agent_number_range=port_range,
            agent_numbers=expand_agent_number_range(port_range),
            runtime_limit_seconds=float(port_cfg["time_limit_seconds"]),
            counted_runs_required=int(port_cfg["counted_runs_required"]),
            num_last_runs_to_visualize=int(port_cfg.get("num_last_runs_to_visualize", 0)),
            require_jointly_successful_mappings=bool(port_cfg.get("require_jointly_successful_mappings", True)),
            path_length_graph_enabled=True,
            is_dynamic=True,
            image_path=str(port_cfg["image_path"]),
            image_threshold=int(port_cfg["image_threshold"]),
            image_resize_longest_side=(
                None if port_cfg.get("image_resize_longest_side") is None else int(port_cfg["image_resize_longest_side"])
            ),
            dynamic_target_static_obstacle_density=float(port_cfg["target_static_obstacle_density"]),
            dynamic_target_dynamic_obstacle_density=float(port_cfg["target_dynamic_obstacle_density"]),
            dynamic_loop_sequence_length=int(port_cfg["loop_sequence_length"]),
            dynamic_group_stay_durations=tuple(port_cfg["group_stay_durations"]),
            dynamic_generation_cell_mode=str(port_cfg.get("dynamic_generation_cell_mode", "all_free")),
            spawnable_cell_mode=str(port_cfg.get("spawnable_cell_mode", "all_free")),
            notes=(
                "Image-based dynamic branch with scattered targets. Retained pairs are the run "
                "configurations for which both mappings are classified as successful or unfinished. "
                "Agent numbers are generated from agent_number_range and the branch can stop early if the stopping rules trigger."
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
            target_type_documented=campus_1_target_type,
            target_type_active=campus_1_target_type,
            seed_base=int(campus_1_cfg["seed"]),
            agent_number_range=campus_1_range,
            agent_numbers=expand_agent_number_range(campus_1_range),
            runtime_limit_seconds=float(campus_1_cfg["time_limit_seconds"]),
            counted_runs_required=int(campus_1_cfg["counted_runs_required"]),
            num_last_runs_to_visualize=int(campus_1_cfg.get("num_last_runs_to_visualize", 0)),
            require_jointly_successful_mappings=bool(campus_1_cfg.get("require_jointly_successful_mappings", True)),
            path_length_graph_enabled=True,
            is_dynamic=True,
            single_cell_target=bool(campus_1_cfg.get("single_cell_target", False)),
            image_path=str(campus_1_cfg["image_path"]),
            image_threshold=int(campus_1_cfg["image_threshold"]),
            dynamic_target_static_obstacle_density=(
                None if campus_1_cfg.get("target_static_obstacle_density") is None else float(campus_1_cfg["target_static_obstacle_density"])
            ),
            dynamic_target_dynamic_obstacle_density=float(campus_1_cfg["target_dynamic_obstacle_density"]),
            dynamic_loop_sequence_length=int(campus_1_cfg["loop_sequence_length"]),
            dynamic_group_stay_durations=tuple(campus_1_cfg["group_stay_durations"]),
            dynamic_generation_cell_mode=str(campus_1_cfg.get("dynamic_generation_cell_mode", "all_free")),
            spawnable_cell_mode=str(campus_1_cfg.get("spawnable_cell_mode", "all_free")),
            notes=(
                "Campus branch with explicit zone-color semantics. Zone colors are traversable and spawnable, "
                "white walkways are traversable but non-spawnable, gray is non-traversable, and dynamic obstacles "
                "are generated only inside the zone colors. The target mode is controlled by single_cell_target."
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
            target_type_documented=campus_2_target_type,
            target_type_active=campus_2_target_type,
            seed_base=int(campus_2_cfg["seed"]),
            agent_number_range=campus_2_range,
            agent_numbers=expand_agent_number_range(campus_2_range),
            runtime_limit_seconds=float(campus_2_cfg["time_limit_seconds"]),
            counted_runs_required=int(campus_2_cfg["counted_runs_required"]),
            num_last_runs_to_visualize=int(campus_2_cfg.get("num_last_runs_to_visualize", 0)),
            require_jointly_successful_mappings=bool(campus_2_cfg.get("require_jointly_successful_mappings", True)),
            path_length_graph_enabled=True,
            is_dynamic=True,
            single_cell_target=bool(campus_2_cfg.get("single_cell_target", False)),
            image_path=str(campus_2_cfg["image_path"]),
            image_threshold=int(campus_2_cfg["image_threshold"]),
            dynamic_target_static_obstacle_density=(
                None if campus_2_cfg.get("target_static_obstacle_density") is None else float(campus_2_cfg["target_static_obstacle_density"])
            ),
            dynamic_target_dynamic_obstacle_density=float(campus_2_cfg["target_dynamic_obstacle_density"]),
            dynamic_loop_sequence_length=int(campus_2_cfg["loop_sequence_length"]),
            dynamic_group_stay_durations=tuple(campus_2_cfg["group_stay_durations"]),
            dynamic_generation_cell_mode=str(campus_2_cfg.get("dynamic_generation_cell_mode", "all_free")),
            spawnable_cell_mode=str(campus_2_cfg.get("spawnable_cell_mode", "all_free")),
            notes=(
                "Campus branch with explicit zone-color semantics. Zone colors are traversable and spawnable, "
                "white walkways are traversable but non-spawnable, gray is non-traversable, and dynamic obstacles "
                "are generated only inside the zone colors. The target mode is controlled by single_cell_target."
            ),
        ),
    }


BRANCH_SPECS = _build_branch_specs()


def get_branch_spec(map_type: str) -> BranchSpec:
    if map_type not in BRANCH_SPECS:
        available = ", ".join(sorted(BRANCH_SPECS))
        raise ValueError(f"Unknown map_type '{map_type}'. Available map types: {available}")
    return BRANCH_SPECS[map_type]
