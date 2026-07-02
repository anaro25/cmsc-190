from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dev.master_config import BRANCH_USER_CONFIGS, agent_cohesion, cohesion_factor, compact_clustering, enhanced_CBS


AgentNumberRange = tuple[int, int, int]

TRADITIONAL_LAYOUTS: tuple[tuple[str, str], ...] = (
    ("dispersed", "dispersed"),
    ("dispersed", "clustered"),
    ("clustered", "dispersed"),
    ("clustered", "clustered"),
)

CAMPUS_LAYOUTS: tuple[tuple[str, str], ...] = (
    ("dispersed", "dispersed"),
    ("dispersed", "single"),
    ("single", "dispersed"),
    ("single", "single"),
)

CATEGORY_ORDER: dict[str, int] = {
    "static_artificial": 1,
    "dynamic_artificial": 2,
    "static_port": 3,
    "dynamic_port": 4,
    "static_campus_area_1": 5,
    "dynamic_campus_area_1": 6,
    "static_campus_area_2": 7,
    "dynamic_campus_area_2": 8,
}


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
    capacity_attempts_per_agent_number: int
    capacity_successful_runs_required: int
    capacity_agent_upper_bound: int
    capacity_binary_search_max_downward_moves: int
    capacity_pass_criterion: str
    setup_generation_attempt_cap_per_solver_attempt: int
    prompt_before_next_map_config: bool
    num_last_runs_to_visualize_jointly_successful: int
    num_last_runs_to_visualize_independently_successful: int
    path_length_graph_enabled: bool
    is_dynamic: bool
    category_map_type: str
    category_index: int
    layout_index: int
    layout_key: str
    layout_label: str
    data_log_category_dir_name: str
    data_log_file_stem: str
    start_distribution_mode: str = "dispersed"
    goal_distribution_mode: str = "dispersed"
    clustered_start_goal_min_distance: int | None = None
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


def _is_campus_branch(map_type: str, config: dict[str, Any]) -> bool:
    return "campus" in map_type or str(config.get("map_family", "")) == "campus_crowd_simulation"


def _branch_supports_agent_cohesion(map_type: str, config: dict[str, Any]) -> bool:
    return _is_campus_branch(map_type, config) or map_type == "dynamic_port"


def _resolved_cohesion_factor() -> float:
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


def _infer_map_type_index(category_map_type: str) -> int:
    order = {
        "static_artificial": 0,
        "dynamic_artificial": 0,
        "static_port": 1,
        "dynamic_port": 1,
        "static_campus_area_1": 2,
        "dynamic_campus_area_1": 2,
        "static_campus_area_2": 3,
        "dynamic_campus_area_2": 3,
    }
    return order.get(category_map_type, 99)


def _branch_decimal(*, is_dynamic: bool, map_type_index: int, layout_index: int) -> str:
    map_obstacle_index = 1 if is_dynamic else 0
    return f"{map_obstacle_index}.{map_type_index}.{layout_index}"


def _layout_key(start_distribution_mode: str, goal_distribution_mode: str) -> str:
    return f"{start_distribution_mode}_{goal_distribution_mode}"


def _layout_label(start_distribution_mode: str, goal_distribution_mode: str) -> str:
    def label(mode: str, *, target: bool = False) -> str:
        if mode == "single":
            return "Single-cell target" if target else "Single-cell"
        return mode.title()
    return f"{label(start_distribution_mode)}-{label(goal_distribution_mode, target=True)}"


def _display_name_for_config(category_display_name: str, layout_label: str) -> str:
    return f"{category_display_name} / {layout_label}"


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

    capacity_note = (
        "Updated main experiment: this layout uses independent binary-search capacity testing from 1 to 255 for "
        "classical and cyclic mapping, with the binary-search descent limited by the configured maximum downward moves. "
        "The default paired-temp capacity criterion accepts a tested value only when the primary mapping solves and cyclic mapping beats classical mapping on the same setup in time computation halted and conflicts at halt. "
        "For the classical-side search, this means classical must solve and cyclic must still outperform it on that classical-origin setup. For the cyclic-side search, cyclic must solve and outperform classical on that cyclic-origin setup. "
        "The program still runs paired comparative tests at the discovered capacity points."
    )

    if config.get("image_path") is None:
        dynamic_part = " Dynamic obstacles are generated on the artificial map." if is_dynamic else ""
        return (
            "Artificial map branch. "
            f"Starts are sampled as {start_mode}, goals use {goal_description}, and {assignment_description}."
            f"{dynamic_part} {capacity_note}"
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
            f"dark marker cells inside the selected target zone. {capacity_note}"
        )

    if is_dynamic:
        if config.get("target_static_obstacle_density") is None or float(config.get("target_static_obstacle_density", 0.0)) >= 1.0:
            dynamic_part = "Dynamic obstacles are generated while preserving the original port static-obstacle layout. "
        else:
            dynamic_part = "Dynamic obstacles are generated from the port image after static-density preprocessing. "
    else:
        dynamic_part = "The port image is used as a static obstacle map. "
    min_distance = config.get("clustered_start_goal_min_distance")
    distance_part = (
        f" Clustered start and goal sets must be at least {min_distance} movement steps apart."
        if min_distance and start_mode == "clustered" and goal_mode == "clustered"
        else ""
    )
    return (
        f"Image-based port branch. {dynamic_part}Starts are sampled as {start_mode}, goals use {goal_description}, "
        f"and {assignment_description}.{distance_part} {capacity_note}"
    )


def _build_single_branch_spec(map_type: str, config: dict[str, Any]) -> BranchSpec:
    category_map_type = str(config.get("category_map_type", map_type))
    is_dynamic = bool(config.get("is_dynamic", category_map_type.startswith("dynamic_")))
    map_obstacle_type = "dynamic" if is_dynamic else "static"
    map_obstacle_index = 1 if is_dynamic else 0
    map_type_index = int(config.get("map_type_index", _infer_map_type_index(category_map_type)))
    layout_index = int(config.get("layout_index", 1))
    branch_decimal = str(config.get("branch_decimal", _branch_decimal(is_dynamic=is_dynamic, map_type_index=map_type_index, layout_index=layout_index)))
    agent_number_range = tuple(config["agent_number_range"])
    solver_name, enhanced_cbs_enabled, solver_suboptimality_factor = _solver_metadata(config)
    clustering_style_name = _clustering_style_name()
    cluster_description = _cluster_description()
    map_size = config.get("map_size")
    layout_key = str(config.get("layout_key", _layout_key(str(config.get("start_distribution_mode", "dispersed")), str(config.get("goal_distribution_mode", "dispersed")))))
    layout_label = str(config.get("layout_label", _layout_label(str(config.get("start_distribution_mode", "dispersed")), str(config.get("goal_distribution_mode", "dispersed")))))
    category_index = int(config.get("category_index", CATEGORY_ORDER.get(category_map_type, 99)))
    data_log_category_dir_name = str(config.get("data_log_category_dir_name", f"{category_index}_{category_map_type}"))
    data_log_file_stem = str(config.get("data_log_file_stem", f"{layout_index}_{category_map_type}_{layout_key}"))

    return BranchSpec(
        map_type=map_type,
        branch_id=map_type,
        branch_decimal=branch_decimal,
        map_obstacle_type=map_obstacle_type,
        map_obstacle_index=map_obstacle_index,
        map_type_index=map_type_index,
        display_name=_display_name_for_config(str(config.get("display_name", category_map_type.replace("_", " ").title())), layout_label),
        target_type_documented=_goal_type(config),
        target_type_active=_goal_type(config),
        seed_base=int(config["seed"]),
        agent_number_range=agent_number_range,
        agent_numbers=expand_agent_number_range(agent_number_range),
        runtime_limit_seconds=float(config["time_limit_seconds"]),
        counted_runs_required=int(config["counted_runs_required"]),
        capacity_attempts_per_agent_number=int(config.get("capacity_attempts_per_agent_number", 5)),
        capacity_successful_runs_required=int(config.get("capacity_successful_runs_required", 1)),
        capacity_agent_upper_bound=int(config.get("capacity_agent_upper_bound", 255)),
        capacity_binary_search_max_downward_moves=int(config.get("capacity_binary_search_max_downward_moves", 3)),
        capacity_pass_criterion=str(config.get("capacity_pass_criterion", "temp_pairwise")),
        setup_generation_attempt_cap_per_solver_attempt=int(config.get("setup_generation_attempt_cap_per_solver_attempt", 5)),
        prompt_before_next_map_config=bool(config.get("prompt_before_next_map_config", True)),
        num_last_runs_to_visualize_jointly_successful=int(config.get("num_last_runs_to_visualize_jointly_successful", 0)),
        num_last_runs_to_visualize_independently_successful=int(config.get("num_last_runs_to_visualize_independently_successful", 0)),
        path_length_graph_enabled=bool(config.get("path_length_graph_enabled", True)),
        is_dynamic=is_dynamic,
        category_map_type=category_map_type,
        category_index=category_index,
        layout_index=layout_index,
        layout_key=layout_key,
        layout_label=layout_label,
        data_log_category_dir_name=data_log_category_dir_name,
        data_log_file_stem=data_log_file_stem,
        start_distribution_mode=str(config.get("start_distribution_mode", "dispersed")),
        goal_distribution_mode=str(config.get("goal_distribution_mode", "dispersed")),
        clustered_start_goal_min_distance=_int_or_none(config.get("clustered_start_goal_min_distance")),
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
        dynamic_group_stay_durations=(None if config.get("group_stay_durations") is None else tuple(config["group_stay_durations"])),
        dynamic_generation_cell_mode=str(config.get("dynamic_generation_cell_mode", "all_free")),
        spawnable_cell_mode=str(config.get("spawnable_cell_mode", "all_free")),
        solver_name=solver_name,
        enhanced_cbs_enabled=enhanced_cbs_enabled,
        solver_suboptimality_factor=solver_suboptimality_factor,
        true_static_shortest_path_distance=bool(config.get("true_static_shortest_path_distance", False)),
        tight_time_horizon=bool(config.get("tight_time_horizon", False)),
        agent_cohesion_enabled=bool(agent_cohesion) if _branch_supports_agent_cohesion(category_map_type, config) else False,
        cohesion_factor=_resolved_cohesion_factor() if _branch_supports_agent_cohesion(category_map_type, config) else 0.0,
        notes=_notes_for_branch(
            map_type=category_map_type,
            config=config,
            is_dynamic=is_dynamic,
            cluster_description=cluster_description,
        ),
    )


def _layouts_for_category(category_map_type: str, config: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return CAMPUS_LAYOUTS if _is_campus_branch(category_map_type, config) else TRADITIONAL_LAYOUTS


def _variant_seed(base_seed: int, layout_index: int) -> int:
    return int(base_seed) + (layout_index * 1000)


def _build_variant_specs_for_category(category_map_type: str) -> list[BranchSpec]:
    if category_map_type not in BRANCH_USER_CONFIGS:
        available = ", ".join(sorted(BRANCH_USER_CONFIGS))
        raise ValueError(f"Unknown map_type '{category_map_type}'. Available map categories: {available}")
    base_config = dict(BRANCH_USER_CONFIGS[category_map_type])
    category_index = int(base_config.get("category_index", CATEGORY_ORDER.get(category_map_type, 99)))
    specs: list[BranchSpec] = []
    for layout_index, (start_mode, goal_mode) in enumerate(_layouts_for_category(category_map_type, base_config), start=1):
        variant_config = dict(base_config)
        layout_key = _layout_key(start_mode, goal_mode)
        variant_config.update(
            {
                "category_map_type": category_map_type,
                "category_index": category_index,
                "layout_index": layout_index,
                "layout_key": layout_key,
                "layout_label": _layout_label(start_mode, goal_mode),
                "start_distribution_mode": start_mode,
                "goal_distribution_mode": goal_mode,
                "seed": _variant_seed(int(base_config["seed"]), layout_index),
                "data_log_category_dir_name": f"{category_index}_{category_map_type}",
                "data_log_file_stem": f"{layout_index}_{category_map_type}_{layout_key}",
            }
        )
        if not (start_mode == "clustered" and goal_mode == "clustered"):
            variant_config["clustered_start_goal_min_distance"] = None
        variant_map_type = f"{category_map_type}_{layout_key}"
        specs.append(_build_single_branch_spec(variant_map_type, variant_config))
    return specs


def get_branch_specs_for_selected_map_type(map_type: str) -> list[BranchSpec]:
    """Compatibility helper: expand one legacy map category into its exact configs."""
    return _build_variant_specs_for_category(map_type)


def _build_branch_specs() -> dict[str, BranchSpec]:
    specs: dict[str, BranchSpec] = {}
    for category_map_type in BRANCH_USER_CONFIGS:
        for spec in _build_variant_specs_for_category(category_map_type):
            specs[spec.map_type] = spec
    return specs


BRANCH_SPECS = _build_branch_specs()


def get_branch_spec(map_type: str) -> BranchSpec:
    if map_type in BRANCH_SPECS:
        return BRANCH_SPECS[map_type]
    available = ", ".join(sorted(BRANCH_SPECS))
    raise ValueError(f"Unknown map configuration '{map_type}'. Available map configurations: {available}")


def get_branch_specs_for_selected_map_configs(selected_map_configs: list[str] | tuple[str, ...] | str) -> list[BranchSpec]:
    if isinstance(selected_map_configs, str):
        selected_map_configs = [selected_map_configs]

    normalized = [str(map_config).strip() for map_config in selected_map_configs if str(map_config).strip()]
    if not normalized:
        available = "\n".join(f"    # {name!r}," for name in sorted(BRANCH_SPECS))
        raise ValueError(
            "SELECTED_MAP_CONFIGS is empty. Uncomment at least one exact map configuration in master_config.py.\n"
            "Available map configurations are:\n"
            f"{available}"
        )

    specs: list[BranchSpec] = []
    unknown: list[str] = []
    for map_config in normalized:
        if map_config in BRANCH_SPECS:
            specs.append(BRANCH_SPECS[map_config])
        else:
            unknown.append(map_config)

    if unknown:
        available = "\n".join(f"    # {name!r}," for name in sorted(BRANCH_SPECS))
        raise ValueError(
            "Unknown map configuration(s) in SELECTED_MAP_CONFIGS: "
            + ", ".join(repr(name) for name in unknown)
            + "\nAvailable map configurations are:\n"
            + available
        )
    return specs
