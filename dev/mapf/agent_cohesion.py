from __future__ import annotations

from typing import Mapping


# The campus crowd behavior is intentionally soft. It changes the order in
# which A* prefers candidate nodes, but it does not add any transition that is
# not already present in the selected mapping. This means the agents still obey
# classical/cyclic transitions and CBS constraints.
DEFAULT_COHESION_FACTOR = 0.35

# Composite-map vertices are stored two array cells apart. One movement step is
# therefore usually a raw coordinate difference of 2.
VERTEX_STEP = 2

# Only apply the stronger anti-snake rule in open places. In narrow corridors or
# bottlenecks, forcing spreading is usually impossible and only slows the search.
OPEN_AREA_FREE_NEIGHBOR_THRESHOLD = 3

# Look a little before and after the candidate timestep. A single-file crowd is
# often not literally on the same cell at the same time; it is usually one agent
# following the recent trail of another agent.
TRAIL_TIME_OFFSETS = (-2, -1, 0, 1, 2)

try:
    from dev.master_config import cohesion_factor as CONFIGURED_COHESION_FACTOR
except Exception:  # pragma: no cover - fallback for isolated imports
    CONFIGURED_COHESION_FACTOR = DEFAULT_COHESION_FACTOR


def get_configured_cohesion_factor() -> float:
    """Return the editable crowd-spreading strength from master_config.py."""
    try:
        return max(0.0, float(CONFIGURED_COHESION_FACTOR))
    except (TypeError, ValueError):
        return DEFAULT_COHESION_FACTOR


def get_path_position(path: list[tuple[int, int]], time_step: int) -> tuple[int, int] | None:
    """Return a path position under the disappearing-agent model."""
    if time_step < 0:
        return None
    if time_step < len(path):
        return path[time_step]
    return None


def vertex_distance_steps(a: tuple[int, int], b: tuple[int, int] | tuple[float, float]) -> float:
    """
    Composite-map vertices are stored two grid cells apart, so raw coordinate
    distance is divided by 2 to express the value in movement steps.
    """
    return (abs(a[0] - b[0]) + abs(a[1] - b[1])) / float(VERTEX_STEP)


def reference_positions_at_time(
    reference_paths: Mapping[int, list[tuple[int, int]]] | None,
    time_step: int,
    *,
    excluded_agent_id: int | None = None,
) -> list[tuple[int, int]]:
    """Collect the already planned crowd positions at a specific timestep."""
    if not reference_paths:
        return []

    positions = []
    for other_agent_id, path in reference_paths.items():
        if excluded_agent_id is not None and other_agent_id == excluded_agent_id:
            continue
        position = get_path_position(path, time_step)
        if position is not None:
            positions.append(position)
    return positions


def _resolve_primary_axis(
    position: tuple[int, int],
    *,
    previous_position: tuple[int, int] | None,
    goal: tuple[int, int] | None,
) -> str | None:
    """
    Estimate the current direction of travel.

    This is used only to identify whether a candidate cell is on the same line
    as an already planned trail. It never decides which moves are legal.
    """
    if previous_position is not None and previous_position != position:
        di = position[0] - previous_position[0]
        dj = position[1] - previous_position[1]
        if abs(di) > abs(dj):
            return "vertical"
        if abs(dj) > abs(di):
            return "horizontal"

    if goal is not None and goal != position:
        di = goal[0] - position[0]
        dj = goal[1] - position[1]
        if abs(di) > abs(dj):
            return "vertical"
        if abs(dj) > abs(di):
            return "horizontal"

    return None


def _is_same_travel_line(
    position: tuple[int, int],
    other_position: tuple[int, int],
    *,
    primary_axis: str | None,
) -> bool:
    """Return True when both positions lie on the same forward/backward line."""
    if primary_axis == "vertical":
        return position[1] == other_position[1]
    if primary_axis == "horizontal":
        return position[0] == other_position[0]
    return position[0] == other_position[0] or position[1] == other_position[1]


def _trail_time_weight(time_offset: int) -> float:
    """Nearby timesteps matter more than farther timesteps."""
    return 1.0 / (1.0 + abs(time_offset))


def crowd_spreading_penalty(
    position: tuple[int, int],
    time_step: int,
    *,
    reference_paths: Mapping[int, list[tuple[int, int]]] | None,
    excluded_agent_id: int | None = None,
    enabled: bool = False,
    previous_position: tuple[int, int] | None = None,
    goal: tuple[int, int] | None = None,
    local_free_neighbor_count: int = 0,
    weight: float | None = None,
) -> float:
    """
    Compute a soft A* priority penalty that discourages single-file movement.

    The previous cohesion version pulled agents toward the group center. That can
    still create a snake after a bottleneck. This version instead looks at the
    already planned paths and discourages a newly planned agent from reusing the
    same trail in open areas. If there are parallel free cells after a bottleneck,
    A* will tend to choose those cells and the crowd forms multiple lines.
    """
    if not enabled:
        return 0.0

    resolved_weight = get_configured_cohesion_factor() if weight is None else max(0.0, float(weight))
    if resolved_weight == 0.0:
        return 0.0

    if not reference_paths:
        return 0.0

    is_open_area = local_free_neighbor_count >= OPEN_AREA_FREE_NEIGHBOR_THRESHOLD
    primary_axis = _resolve_primary_axis(
        position,
        previous_position=previous_position,
        goal=goal,
    )

    penalty = 0.0

    for time_offset in TRAIL_TIME_OFFSETS:
        other_positions = reference_positions_at_time(
            reference_paths,
            time_step + time_offset,
            excluded_agent_id=excluded_agent_id,
        )
        if not other_positions:
            continue

        time_weight = _trail_time_weight(time_offset)
        for other_position in other_positions:
            distance = vertex_distance_steps(position, other_position)

            # Never make actual same-time collision handling depend on this. CBS
            # constraints are still responsible for legality. This only changes
            # which legal alternatives A* tries first.
            if distance == 0:
                penalty += 1.50 * time_weight
                continue

            if not is_open_area:
                continue

            if not _is_same_travel_line(position, other_position, primary_axis=primary_axis):
                continue

            # This is the main anti-snake rule: in open areas, do not prefer the
            # exact same lane immediately behind or ahead of already planned
            # agents. One and two movement steps are the most visible snake cases.
            if distance <= 1.0:
                penalty += 1.25 * time_weight
            elif distance <= 2.0:
                penalty += 0.75 * time_weight
            elif distance <= 3.0:
                penalty += 0.35 * time_weight

    return resolved_weight * penalty


# Backwards-compatible name used by older files in the project. The mechanism is
# no longer a center-of-mass attraction; it is an anti-trail spreading preference.
def cohesion_penalty(*args, **kwargs) -> float:
    return crowd_spreading_penalty(*args, **kwargs)
