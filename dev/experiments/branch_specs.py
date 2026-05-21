from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dev.master_config import BRANCH_USER_CONFIGS, compact_clustering, enhanced_CBS


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
    num_last_runs_to_visualize_jointly_successful: int
    num_last_runs_to_visualize_independently_successful: int
    path_length_graph_enabled: bool
    is_dynamic: bool
    start_distribution_mode: str = "dispersed"
    goal_distribution_mode: str = "dispersed"
    require_individual_reachability: bool = False
    zone_relationship_mode: str = "none"
    compact_clustering: bool = True
    clustering_style_name: str = "compact"
    narrow_lanes: bool | None = None
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
    solver_name: str = "CBS"
    enhanced_cbs_enabled: bool = False
    solver_suboptimality_factor: float | None = None
    true_static_shortest_path_distance: bool = False
    tight_time_horizon: bool = False
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


def _goal_type(config: dict[str, Any]) -> str:
    goal_distribution_mode = str(config.get("goal_distribution_mode", "dispersed"))
    if goal_distribution_mode == "clustered":
        return "clustered_targets"
    if goal_distribution_mode == "single":
        return "single_target"
    return "dispersed_targets"


def _resolve_ecbs_suboptimality(config: dict[str, Any]) -> float:
    value = float(config.get("ECBS_suboptimality", 1.5))
    if value < 1.0:
        raise ValueError("ECBS_suboptimality must be greater than or equal to 1.0")
    return value


def _solver_metadata(config: dict[str, Any]) -> tuple[str, bool, float | None]:
    enabled = bool(enhanced_CBS)
    return (
        "ECBS" if enabled else "CBS",
        enabled,
        _resolve_ecbs_suboptimality(config) if enabled else None,
    )


def _clustering_style_name() -> str:
    return "compact" if compact_clustering else "spaced"


def _cluster_description() -> str:
    if compact_clustering:
        return "one compact directly adjacent 8-neighbor-connected group"
    return "one spaced cluster whose members keep one empty cell of separation in all 8 directions"


def _goal_distribution_description(goal_distribution_mode: str, cluster_description: str) -> str:
    if goal_distribution_mode == "single":
        return "one literal shared target cell"
    if goal_distribution_mode == "clustered":
        return f"targets sampled as {cluster_description}"
    return "dispersed one-to-one targets"


def _assignment_cardinality_description(goal_distribution_mode: str) -> str:
    if goal_distribution_mode == "single":
        return "assignments are many-to-one"
    return "assignments remain one-to-one"


def _build_branch_specs() -> dict[str, BranchSpec]:
    static_cfg = BRANCH_USER_CONFIGS["static_artificial"]
    static_campus_1_cfg = BRANCH_USER_CONFIGS["static_campus_area_1"]
    port_cfg = BRANCH_USER_CONFIGS["dynamic_port"]
    campus_2_cfg = BRANCH_USER_CONFIGS["dynamic_campus_area_2"]

    static_range = tuple(static_cfg["agent_number_range"])
    static_campus_1_range = tuple(static_campus_1_cfg["agent_number_range"])
    port_range = tuple(port_cfg["agent_number_range"])
    campus_2_range = tuple(campus_2_cfg["agent_number_range"])
    static_solver_name, static_enhanced_cbs_enabled, static_solver_suboptimality_factor = _solver_metadata(static_cfg)
    static_campus_1_solver_name, static_campus_1_enhanced_cbs_enabled, static_campus_1_solver_suboptimality_factor = _solver_metadata(static_campus_1_cfg)
    port_solver_name, port_enhanced_cbs_enabled, port_solver_suboptimality_factor = _solver_metadata(port_cfg)
    campus_2_solver_name, campus_2_enhanced_cbs_enabled, campus_2_solver_suboptimality_factor = _solver_metadata(campus_2_cfg)
    clustering_style_name = _clustering_style_name()
    cluster_description = _cluster_description()

    static_goal_mode = str(static_cfg.get("goal_distribution_mode", "dispersed"))
    static_campus_1_goal_mode = str(static_campus_1_cfg.get("goal_distribution_mode", "dispersed"))
    port_goal_mode = str(port_cfg.get("goal_distribution_mode", "dispersed"))
    campus_2_goal_mode = str(campus_2_cfg.get("goal_distribution_mode", "dispersed"))

    static_goal_description = _goal_distribution_description(static_goal_mode, cluster_description)
    static_campus_1_goal_description = _goal_distribution_description(static_campus_1_goal_mode, cluster_description)
    port_goal_description = _goal_distribution_description(port_goal_mode, cluster_description)
    campus_2_goal_description = _goal_distribution_description(campus_2_goal_mode, cluster_description)

    static_assignment_description = _assignment_cardinality_description(static_goal_mode)
    static_campus_1_assignment_description = _assignment_cardinality_description(static_campus_1_goal_mode)
    port_assignment_description = _assignment_cardinality_description(port_goal_mode)
    campus_2_assignment_description = _assignment_cardinality_description(campus_2_goal_mode)

    return {
        "static_artificial": BranchSpec(
            map_type="static_artificial",
            branch_id="static_artificial",
            branch_decimal="0.0",
            map_obstacle_type="static",
            map_obstacle_index=0,
            map_type_index=0,
            display_name="Static Artificial",
            target_type_documented=_goal_type(static_cfg),
            target_type_active=_goal_type(static_cfg),
            seed_base=int(static_cfg["seed"]),
            agent_number_range=static_range,
            agent_numbers=expand_agent_number_range(static_range),
            runtime_limit_seconds=float(static_cfg["time_limit_seconds"]),
            counted_runs_required=int(static_cfg["counted_runs_required"]),
            num_last_runs_to_visualize_jointly_successful=int(
                static_cfg.get(
                    "num_last_runs_to_visualize_jointly_successful",
                    static_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            num_last_runs_to_visualize_independently_successful=int(
                static_cfg.get(
                    "num_last_runs_to_visualize_independently_successful",
                    static_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            path_length_graph_enabled=True,
            is_dynamic=False,
            compact_clustering=compact_clustering,
            clustering_style_name=clustering_style_name,
            solver_name=static_solver_name,
            enhanced_cbs_enabled=static_enhanced_cbs_enabled,
            solver_suboptimality_factor=static_solver_suboptimality_factor,
            true_static_shortest_path_distance=bool(static_cfg.get("true_static_shortest_path_distance", False)),
            tight_time_horizon=bool(static_cfg.get("tight_time_horizon", False)),
            start_distribution_mode=str(static_cfg.get("start_distribution_mode", "dispersed")),
            goal_distribution_mode=str(static_cfg.get("goal_distribution_mode", "dispersed")),
            require_individual_reachability=bool(static_cfg.get("require_individual_reachability", False)),
            zone_relationship_mode=str(static_cfg.get("zone_relationship_mode", "none")),
            base_rows=int(static_cfg["map_size"][0]),
            base_cols=int(static_cfg["map_size"][1]),
            static_obstacle_density=float(static_cfg["static_obstacle_density"]),
            notes=(
                f"Fresh artificial map per run configuration. Starts are sampled as a dispersed set, goals use {static_goal_description}, "
                f"and {static_assignment_description}. "
                "Retained pairs are the run configurations for which both mappings are classified as successful or unfinished. "
                "Agent numbers are generated from agent_number_range and the branch can stop early if the stopping rules trigger."
            ),
        ),
        "static_campus_area_1": BranchSpec(
            map_type="static_campus_area_1",
            branch_id="static_campus_area_1",
            branch_decimal="0.1",
            map_obstacle_type="static",
            map_obstacle_index=0,
            map_type_index=1,
            display_name="Static Campus Area 1",
            target_type_documented=_goal_type(static_campus_1_cfg),
            target_type_active=_goal_type(static_campus_1_cfg),
            seed_base=int(static_campus_1_cfg["seed"]),
            agent_number_range=static_campus_1_range,
            agent_numbers=expand_agent_number_range(static_campus_1_range),
            runtime_limit_seconds=float(static_campus_1_cfg["time_limit_seconds"]),
            counted_runs_required=int(static_campus_1_cfg["counted_runs_required"]),
            num_last_runs_to_visualize_jointly_successful=int(
                static_campus_1_cfg.get(
                    "num_last_runs_to_visualize_jointly_successful",
                    static_campus_1_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            num_last_runs_to_visualize_independently_successful=int(
                static_campus_1_cfg.get(
                    "num_last_runs_to_visualize_independently_successful",
                    static_campus_1_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            path_length_graph_enabled=True,
            is_dynamic=False,
            compact_clustering=compact_clustering,
            clustering_style_name=clustering_style_name,
            narrow_lanes=bool(static_campus_1_cfg.get("narrow_lanes", False)),
            solver_name=static_campus_1_solver_name,
            enhanced_cbs_enabled=static_campus_1_enhanced_cbs_enabled,
            solver_suboptimality_factor=static_campus_1_solver_suboptimality_factor,
            true_static_shortest_path_distance=bool(static_campus_1_cfg.get("true_static_shortest_path_distance", False)),
            tight_time_horizon=bool(static_campus_1_cfg.get("tight_time_horizon", False)),
            start_distribution_mode=str(static_campus_1_cfg.get("start_distribution_mode", "dispersed")),
            goal_distribution_mode=str(static_campus_1_cfg.get("goal_distribution_mode", "dispersed")),
            require_individual_reachability=bool(static_campus_1_cfg.get("require_individual_reachability", False)),
            zone_relationship_mode=str(static_campus_1_cfg.get("zone_relationship_mode", "none")),
            image_path=str(static_campus_1_cfg["image_path"]),
            image_threshold=int(static_campus_1_cfg["image_threshold"]),
            dynamic_generation_cell_mode=str(static_campus_1_cfg.get("dynamic_generation_cell_mode", "zone_colors_only")),
            spawnable_cell_mode=str(static_campus_1_cfg.get("spawnable_cell_mode", "zone_colors_only")),
            notes=(
                "Static image-based campus branch with explicit zone-color semantics. Starts are dispersed in one zone, "
                f"targets use {static_campus_1_goal_description} in a different zone, and {static_campus_1_assignment_description}. "
                "Zone colors are traversable and spawnable, white walkways are traversable but non-spawnable, and gray is non-traversable. "
                f"The currently selected campus image variant is {'narrow lanes' if bool(static_campus_1_cfg.get('narrow_lanes', False)) else 'wide lanes'}."
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
            target_type_documented=_goal_type(port_cfg),
            target_type_active=_goal_type(port_cfg),
            seed_base=int(port_cfg["seed"]),
            agent_number_range=port_range,
            agent_numbers=expand_agent_number_range(port_range),
            runtime_limit_seconds=float(port_cfg["time_limit_seconds"]),
            counted_runs_required=int(port_cfg["counted_runs_required"]),
            num_last_runs_to_visualize_jointly_successful=int(
                port_cfg.get(
                    "num_last_runs_to_visualize_jointly_successful",
                    port_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            num_last_runs_to_visualize_independently_successful=int(
                port_cfg.get(
                    "num_last_runs_to_visualize_independently_successful",
                    port_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            path_length_graph_enabled=True,
            is_dynamic=True,
            compact_clustering=compact_clustering,
            clustering_style_name=clustering_style_name,
            solver_name=port_solver_name,
            enhanced_cbs_enabled=port_enhanced_cbs_enabled,
            solver_suboptimality_factor=port_solver_suboptimality_factor,
            true_static_shortest_path_distance=bool(port_cfg.get("true_static_shortest_path_distance", False)),
            tight_time_horizon=bool(port_cfg.get("tight_time_horizon", False)),
            start_distribution_mode=str(port_cfg.get("start_distribution_mode", "dispersed")),
            goal_distribution_mode=str(port_cfg.get("goal_distribution_mode", "dispersed")),
            require_individual_reachability=bool(port_cfg.get("require_individual_reachability", True)),
            zone_relationship_mode=str(port_cfg.get("zone_relationship_mode", "none")),
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
                f"Image-based dynamic branch with clustered starts sampled as {cluster_description}; goals use {port_goal_description}, "
                f"and {port_assignment_description}. "
                "Retained pairs are the run configurations for which both mappings are classified as successful or unfinished. "
                "Agent numbers are generated from agent_number_range and the branch can stop early if the stopping rules trigger."
            ),
        ),
        "dynamic_campus_area_2": BranchSpec(
            map_type="dynamic_campus_area_2",
            branch_id="dynamic_campus_area_2",
            branch_decimal="1.1",
            map_obstacle_type="dynamic",
            map_obstacle_index=1,
            map_type_index=2,
            display_name="Dynamic Campus Area 2",
            target_type_documented=_goal_type(campus_2_cfg),
            target_type_active=_goal_type(campus_2_cfg),
            seed_base=int(campus_2_cfg["seed"]),
            agent_number_range=campus_2_range,
            agent_numbers=expand_agent_number_range(campus_2_range),
            runtime_limit_seconds=float(campus_2_cfg["time_limit_seconds"]),
            counted_runs_required=int(campus_2_cfg["counted_runs_required"]),
            num_last_runs_to_visualize_jointly_successful=int(
                campus_2_cfg.get(
                    "num_last_runs_to_visualize_jointly_successful",
                    campus_2_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            num_last_runs_to_visualize_independently_successful=int(
                campus_2_cfg.get(
                    "num_last_runs_to_visualize_independently_successful",
                    campus_2_cfg.get("num_last_runs_to_visualize", 0),
                )
            ),
            path_length_graph_enabled=True,
            is_dynamic=True,
            compact_clustering=compact_clustering,
            clustering_style_name=clustering_style_name,
            narrow_lanes=bool(campus_2_cfg.get("narrow_lanes", False)),
            solver_name=campus_2_solver_name,
            enhanced_cbs_enabled=campus_2_enhanced_cbs_enabled,
            solver_suboptimality_factor=campus_2_solver_suboptimality_factor,
            true_static_shortest_path_distance=bool(campus_2_cfg.get("true_static_shortest_path_distance", False)),
            tight_time_horizon=bool(campus_2_cfg.get("tight_time_horizon", False)),
            start_distribution_mode=str(campus_2_cfg.get("start_distribution_mode", "dispersed")),
            goal_distribution_mode=str(campus_2_cfg.get("goal_distribution_mode", "dispersed")),
            require_individual_reachability=bool(campus_2_cfg.get("require_individual_reachability", True)),
            zone_relationship_mode=str(campus_2_cfg.get("zone_relationship_mode", "none")),
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
                "Campus branch with explicit zone-color semantics. Zone colors are traversable and spawnable, white walkways "
                "are traversable but non-spawnable, gray is non-traversable, and dynamic obstacles are generated only inside the "
                f"zone colors. Starts are sampled as {cluster_description}, targets use {campus_2_goal_description}, "
                f"{campus_2_assignment_description}, and the start and target selections must come from different campus zones. "
                f"The currently selected campus image variant is {'narrow lanes' if bool(campus_2_cfg.get('narrow_lanes', False)) else 'wide lanes'}."
            ),
        ),
    }


BRANCH_SPECS = _build_branch_specs()


def get_branch_spec(map_type: str) -> BranchSpec:
    if map_type not in BRANCH_SPECS:
        available = ", ".join(sorted(BRANCH_SPECS))
        raise ValueError(f"Unknown map_type '{map_type}'. Available map types: {available}")
    return BRANCH_SPECS[map_type]
