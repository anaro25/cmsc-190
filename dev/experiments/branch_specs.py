from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dev.master_config import BRANCH_USER_CONFIGS, agent_cohesion, cohesion_factor, compact_clustering, enhanced_CBS


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
    agent_cohesion_enabled: bool = False
    cohesion_factor: float = 0.0
    filter_individual_runs_until_cyclic_faster: bool = False
    filter_individual_runs_until_cyclic_faster_max_attempts: int | None = None
    rerun_until_cyclic_faster: bool = False
    rerun_until_cyclic_faster_max_batches: int | None = None
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


def _campus_cohesion_factor() -> float:
    if not agent_cohesion:
        return 0.0
    try:
        return max(0.0, float(cohesion_factor))
    except (TypeError, ValueError):
        return 0.0


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


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)


def _infer_map_type_index(map_type: str) -> int:
    order = {
        "static_artificial": 0,
        "static_port": 1,
        "dynamic_port": 1,
        "static_campus_area_1": 2,
        "dynamic_campus_area_1": 2,
        "static_campus_area_2": 3,
        "dynamic_campus_area_2": 3,
        "static_campus_area_3": 4,
        "dynamic_campus_area_3": 4,
    }
    return order.get(map_type, 99)


def _branch_decimal(*, is_dynamic: bool, map_type_index: int) -> str:
    map_obstacle_index = 1 if is_dynamic else 0
    return f"{map_obstacle_index}.{map_type_index}"


def _is_campus_branch(map_type: str, config: dict[str, Any]) -> bool:
    return "campus" in map_type or str(config.get("map_family", "")) == "campus_crowd_simulation"


def _notes_for_branch(
    *,
    map_type: str,
    config: dict[str, Any],
    is_dynamic: bool,
    cluster_description: str,
) -> str:
    start_mode = str(config.get("start_distribution_mode", "dispersed"))
    goal_mode = str(config.get("goal_distribution_mode", "dispersed"))
    goal_description = _goal_distribution_description(goal_mode, cluster_description)
    assignment_description = _assignment_cardinality_description(goal_mode)

    if config.get("image_path") is None:
        return (
            "Fresh artificial map per run configuration. "
            f"Starts are sampled as {start_mode}, goals use {goal_description}, and {assignment_description}. "
            "Retained pairs are the run configurations for which both mappings are classified as successful or unfinished. "
            "Agent numbers are generated from agent_number_range and the branch can stop early if the stopping rules trigger."
        )

    if _is_campus_branch(map_type, config):
        dynamic_part = (
            "Dynamic obstacles are generated on all campus traversable cells, including zone colors and white walkways. "
            if is_dynamic
            else "The source-image static layout is used without dynamic obstacles. "
        )
        return (
            "Campus branch with explicit zone-color semantics. Zone colors are traversable and spawnable, white walkways "
            "are traversable but non-spawnable for agents/targets, and gray/black cells are non-traversable. "
            f"{dynamic_part}Starts are sampled as {start_mode} in one zone, targets use {goal_description} in a different zone, "
            f"and {assignment_description}. When single target mode is active, the shared target is sampled only from "
            "dark marker cells inside the selected target zone."
        )

    dynamic_part = (
        "Dynamic obstacles are generated from the port image after static-density preprocessing. "
        if is_dynamic
        else "The port image is used as a static obstacle map. "
    )
    return (
        f"Image-based port branch. {dynamic_part}Starts are sampled as {start_mode}, goals use {goal_description}, "
        f"and {assignment_description}. Retained pairs are the run configurations for which both mappings are classified "
        "as successful or unfinished. Agent numbers are generated from agent_number_range and the branch can stop early "
        "if the stopping rules trigger."
    )


def _build_single_branch_spec(map_type: str, config: dict[str, Any]) -> BranchSpec:
    is_dynamic = bool(config.get("is_dynamic", map_type.startswith("dynamic_")))
    map_obstacle_type = "dynamic" if is_dynamic else "static"
    map_obstacle_index = 1 if is_dynamic else 0
    map_type_index = int(config.get("map_type_index", _infer_map_type_index(map_type)))
    branch_decimal = str(config.get("branch_decimal", _branch_decimal(is_dynamic=is_dynamic, map_type_index=map_type_index)))
    agent_number_range = tuple(config["agent_number_range"])
    solver_name, enhanced_cbs_enabled, solver_suboptimality_factor = _solver_metadata(config)
    clustering_style_name = _clustering_style_name()
    cluster_description = _cluster_description()
    map_size = config.get("map_size")
    campus_branch = _is_campus_branch(map_type, config)

    return BranchSpec(
        map_type=map_type,
        branch_id=map_type,
        branch_decimal=branch_decimal,
        map_obstacle_type=map_obstacle_type,
        map_obstacle_index=map_obstacle_index,
        map_type_index=map_type_index,
        display_name=str(config.get("display_name", map_type.replace("_", " ").title())),
        target_type_documented=_goal_type(config),
        target_type_active=_goal_type(config),
        seed_base=int(config["seed"]),
        agent_number_range=agent_number_range,
        agent_numbers=expand_agent_number_range(agent_number_range),
        runtime_limit_seconds=float(config["time_limit_seconds"]),
        counted_runs_required=int(config["counted_runs_required"]),
        num_last_runs_to_visualize_jointly_successful=int(
            config.get(
                "num_last_runs_to_visualize_jointly_successful",
                config.get("num_last_runs_to_visualize", 0),
            )
        ),
        num_last_runs_to_visualize_independently_successful=int(
            config.get(
                "num_last_runs_to_visualize_independently_successful",
                config.get("num_last_runs_to_visualize", 0),
            )
        ),
        path_length_graph_enabled=bool(config.get("path_length_graph_enabled", True)),
        is_dynamic=is_dynamic,
        start_distribution_mode=str(config.get("start_distribution_mode", "dispersed")),
        goal_distribution_mode=str(config.get("goal_distribution_mode", "dispersed")),
        require_individual_reachability=bool(config.get("require_individual_reachability", False)),
        zone_relationship_mode=str(config.get("zone_relationship_mode", "none")),
        compact_clustering=compact_clustering,
        clustering_style_name=clustering_style_name,
        base_rows=None if map_size is None else int(map_size[0]),
        base_cols=None if map_size is None else int(map_size[1]),
        static_obstacle_density=_float_or_none(config.get("static_obstacle_density")),
        image_path=None if config.get("image_path") is None else str(config["image_path"]),
        image_threshold=int(config.get("image_threshold", 127)),
        image_resize_longest_side=_int_or_none(config.get("image_resize_longest_side")),
        dynamic_target_static_obstacle_density=_float_or_none(config.get("target_static_obstacle_density")),
        dynamic_target_dynamic_obstacle_density=_float_or_none(config.get("target_dynamic_obstacle_density")),
        dynamic_loop_sequence_length=_int_or_none(config.get("loop_sequence_length")),
        dynamic_group_stay_durations=(
            None if config.get("group_stay_durations") is None else tuple(config["group_stay_durations"])
        ),
        dynamic_generation_cell_mode=str(config.get("dynamic_generation_cell_mode", "all_free")),
        spawnable_cell_mode=str(config.get("spawnable_cell_mode", "all_free")),
        solver_name=solver_name,
        enhanced_cbs_enabled=enhanced_cbs_enabled,
        solver_suboptimality_factor=solver_suboptimality_factor,
        true_static_shortest_path_distance=bool(config.get("true_static_shortest_path_distance", False)),
        tight_time_horizon=bool(config.get("tight_time_horizon", False)),
        agent_cohesion_enabled=bool(agent_cohesion) if campus_branch else False,
        cohesion_factor=_campus_cohesion_factor() if campus_branch else 0.0,
        filter_individual_runs_until_cyclic_faster=bool(
            config.get("filter_individual_runs_until_cyclic_faster", False)
        ),
        filter_individual_runs_until_cyclic_faster_max_attempts=_int_or_none(
            config.get("filter_individual_runs_until_cyclic_faster_max_attempts")
        ),
        rerun_until_cyclic_faster=bool(config.get("rerun_until_cyclic_faster", False)),
        rerun_until_cyclic_faster_max_batches=_int_or_none(config.get("rerun_until_cyclic_faster_max_batches")),
        notes=_notes_for_branch(
            map_type=map_type,
            config=config,
            is_dynamic=is_dynamic,
            cluster_description=cluster_description,
        ),
    )


def _build_branch_specs() -> dict[str, BranchSpec]:
    return {
        map_type: _build_single_branch_spec(map_type, config)
        for map_type, config in BRANCH_USER_CONFIGS.items()
    }


BRANCH_SPECS = _build_branch_specs()


def get_branch_spec(map_type: str) -> BranchSpec:
    if map_type not in BRANCH_SPECS:
        available = ", ".join(sorted(BRANCH_SPECS))
        raise ValueError(f"Unknown map_type '{map_type}'. Available map types: {available}")
    return BRANCH_SPECS[map_type]
