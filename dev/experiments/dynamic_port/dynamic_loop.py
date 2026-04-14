import random
from collections import deque
from collections.abc import Callable

from dev.experiments.dynamic_port.preprocessing import get_neighbors, is_free_space_connected


def shortest_path_distance(matrix, start, goal):
    if start == goal:
        return 0

    queue = deque([(start, 0)])
    visited = {start}
    while queue:
        (r, c), dist = queue.popleft()
        for nr, nc in get_neighbors(matrix, r, c):
            if matrix[nr][nc] != 0 or (nr, nc) in visited:
                continue
            if (nr, nc) == goal:
                return dist + 1
            visited.add((nr, nc))
            queue.append(((nr, nc), dist + 1))
    return None


def frame_is_valid(base_matrix, dynamic_cells):
    frame = [row[:] for row in base_matrix]
    for r, c in dynamic_cells:
        if frame[r][c] == 0:
            frame[r][c] = 2
    traversable = [[0 if cell == 0 else 1 for cell in row] for row in frame]
    return is_free_space_connected(traversable)


def apply_dynamic_cells(base_matrix, dynamic_cells):
    frame = [row[:] for row in base_matrix]
    for r, c in dynamic_cells:
        if frame[r][c] == 0:
            frame[r][c] = 2
    return frame


def _free_cells(base_matrix):
    for r, row in enumerate(base_matrix):
        for c, value in enumerate(row):
            if value == 0:
                yield (r, c)


def _free_neighbor_count(base_matrix, cell):
    r, c = cell
    return sum(1 for nr, nc in get_neighbors(base_matrix, r, c) if base_matrix[nr][nc] == 0)


def _ordered_frontier(base_matrix, group_cells, center, blocked_cells, rng):
    frontier = []
    if not group_cells:
        frontier.append(center)
    else:
        for cell in list(group_cells):
            for neighbor in get_neighbors(base_matrix, cell[0], cell[1]):
                if base_matrix[neighbor[0]][neighbor[1]] != 0:
                    continue
                if neighbor in group_cells or neighbor in blocked_cells or neighbor in frontier:
                    continue
                frontier.append(neighbor)
    rng.shuffle(frontier)
    frontier.sort(
        key=lambda cell: (
            abs(cell[0] - center[0]) + abs(cell[1] - center[1]),
            -_free_neighbor_count(base_matrix, cell),
            rng.random(),
        )
    )
    return frontier


def _grow_group_patch(base_matrix, center, target_count, blocked_cells, rng):
    group_cells = set()
    attempts = 0
    limit = max(120, target_count * 50)
    while len(group_cells) < target_count and attempts < limit:
        attempts += 1
        frontier = _ordered_frontier(base_matrix, group_cells, center, blocked_cells, rng)
        added = False
        for cell in frontier:
            candidate = group_cells | {cell}
            if frame_is_valid(base_matrix, blocked_cells | candidate):
                group_cells.add(cell)
                added = True
                break
        if not added:
            break
    return group_cells


def _candidate_centers(base_matrix, rng):
    candidates = [cell for cell in _free_cells(base_matrix) if _free_neighbor_count(base_matrix, cell) >= 2]
    if not candidates:
        candidates = list(_free_cells(base_matrix))
    rng.shuffle(candidates)
    candidates.sort(key=lambda cell: (_free_neighbor_count(base_matrix, cell), rng.random()), reverse=True)
    return candidates


def _emit_progress(progress_callback: Callable[[str], None] | None, message: str) -> None:
    if progress_callback is not None:
        progress_callback(message)


def _build_patch_bank(base_matrix, group_sizes, seed, patches_per_group=90, progress_callback: Callable[[str], None] | None = None):
    rng = random.Random(seed)
    centers = _candidate_centers(base_matrix, rng)
    _emit_progress(
        progress_callback,
        f'Dynamic patch-bank center candidates prepared: {len(centers)} usable centers.',
    )
    patch_bank = []
    for group_index, target_size in enumerate(group_sizes):
        group_rng = random.Random(seed + 1000 + group_index * 997)
        entries = []
        attempts = 0
        _emit_progress(
            progress_callback,
            f'Building dynamic patch bank for group {group_index + 1}/{len(group_sizes)} | target_patch_size={target_size} | required_entries={patches_per_group}',
        )
        while len(entries) < patches_per_group and attempts < patches_per_group * 8:
            attempts += 1
            center = centers[group_rng.randrange(len(centers))]
            patch = _grow_group_patch(
                base_matrix=base_matrix,
                center=center,
                target_count=target_size,
                blocked_cells=set(),
                rng=random.Random(seed + 5000 + group_index * 10000 + attempts),
            )
            if len(patch) != target_size:
                if attempts == 1 or attempts % 10 == 0:
                    _emit_progress(
                        progress_callback,
                        f'  Patch bank group {group_index + 1}/{len(group_sizes)} progress | entries={len(entries)}/{patches_per_group} | center_attempts={attempts} | last_patch_size={len(patch)}/{target_size}',
                    )
                continue
            entries.append({
                'center': center,
                'cells': tuple(sorted(patch)),
            })
            if len(entries) == 1 or len(entries) % 10 == 0 or len(entries) == patches_per_group:
                _emit_progress(
                    progress_callback,
                    f'  Patch bank group {group_index + 1}/{len(group_sizes)} progress | entries={len(entries)}/{patches_per_group} | center_attempts={attempts}',
                )
        if not entries:
            raise RuntimeError('Unable to build dynamic obstacle patch bank.')
        _emit_progress(
            progress_callback,
            f'Completed dynamic patch bank for group {group_index + 1}/{len(group_sizes)} | entries={len(entries)}/{patches_per_group} | center_attempts={attempts}',
        )
        patch_bank.append(entries)
    return patch_bank


def _patch_distance(base_matrix, patch_a, patch_b):
    center_a = patch_a['center']
    center_b = patch_b['center']
    distance = shortest_path_distance(base_matrix, center_a, center_b)
    if distance is None:
        return 0
    return distance


def _choose_patch_for_group(base_matrix, group_index, time_step, current_patches, patch_bank, stay_durations, rng):
    previous_patch = current_patches[group_index]
    blocked_by_others = set()
    for other_index, patch in enumerate(current_patches):
        if other_index == group_index or patch is None:
            continue
        blocked_by_others.update(patch['cells'])

    candidates = list(patch_bank[group_index])
    rng.shuffle(candidates)
    candidates.sort(
        key=lambda patch: (
            0 if previous_patch is None else -_patch_distance(base_matrix, previous_patch, patch),
            rng.random(),
        )
    )

    min_distance = max(5, min(len(base_matrix), len(base_matrix[0])) // 4)
    relaxed_candidates = []
    for patch in candidates:
        patch_cells = set(patch['cells'])
        if patch_cells & blocked_by_others:
            continue
        if previous_patch is not None and patch['cells'] == previous_patch['cells']:
            continue
        if previous_patch is not None and _patch_distance(base_matrix, previous_patch, patch) >= min_distance:
            if frame_is_valid(base_matrix, blocked_by_others | patch_cells):
                return patch
        relaxed_candidates.append(patch)

    for patch in relaxed_candidates:
        patch_cells = set(patch['cells'])
        if frame_is_valid(base_matrix, blocked_by_others | patch_cells):
            return patch

    if previous_patch is not None and frame_is_valid(base_matrix, blocked_by_others | set(previous_patch['cells'])):
        return previous_patch

    raise RuntimeError(
        f'Unable to place dynamic obstacle group {group_index + 1} at timestep {time_step}. '
        f'Stay duration={stay_durations[group_index]}.'
    )


def build_dynamic_loop(
    base_matrix,
    dynamic_density,
    loop_length,
    group_stay_durations=(3, 4, 5),
    seed=42,
    progress_callback: Callable[[str], None] | None = None,
):
    total_cells = len(base_matrix) * len(base_matrix[0])
    target_dynamic_cells = int(round(dynamic_density * total_cells))
    loop_length = max(1, loop_length)

    _emit_progress(
        progress_callback,
        f'Dynamic loop generation started | grid={len(base_matrix)}x{len(base_matrix[0]) if base_matrix else 0} | dynamic_density={dynamic_density:.2f} | target_dynamic_cells={target_dynamic_cells} | loop_length={loop_length}',
    )

    if target_dynamic_cells <= 0:
        _emit_progress(progress_callback, 'Dynamic loop generation resolved immediately because target_dynamic_cells=0.')
        return [apply_dynamic_cells(base_matrix, set()) for _ in range(loop_length)]

    if not group_stay_durations:
        raise ValueError('group_stay_durations must not be empty.')

    group_count = len(group_stay_durations)
    group_sizes = [target_dynamic_cells // group_count for _ in range(group_count)]
    for index in range(target_dynamic_cells % group_count):
        group_sizes[index] += 1

    _emit_progress(
        progress_callback,
        f'Dynamic loop group split | group_count={group_count} | group_sizes={group_sizes} | stay_durations={tuple(group_stay_durations)}',
    )

    patch_bank = _build_patch_bank(
        base_matrix=base_matrix,
        group_sizes=group_sizes,
        seed=seed,
        progress_callback=progress_callback,
    )

    current_patches = [None for _ in range(group_count)]
    frames = []

    for time_step in range(loop_length):
        for group_index, stay_duration in enumerate(group_stay_durations):
            if current_patches[group_index] is None or time_step % stay_duration == 0:
                current_patches[group_index] = _choose_patch_for_group(
                    base_matrix=base_matrix,
                    group_index=group_index,
                    time_step=time_step,
                    current_patches=current_patches,
                    patch_bank=patch_bank,
                    stay_durations=group_stay_durations,
                    rng=random.Random(seed + 30000 + group_index * 1000 + time_step),
                )

        dynamic_cells = set()
        for patch in current_patches:
            dynamic_cells.update(patch['cells'])

        if len(dynamic_cells) != target_dynamic_cells or not frame_is_valid(base_matrix, dynamic_cells):
            raise RuntimeError(
                'Dynamic loop generation produced an invalid frame. '
                f'Expected {target_dynamic_cells} dynamic cells, got {len(dynamic_cells)}.'
            )
        frames.append(apply_dynamic_cells(base_matrix, dynamic_cells))

        if time_step == 0 or (time_step + 1) % 5 == 0 or time_step + 1 == loop_length:
            _emit_progress(
                progress_callback,
                f'Dynamic loop frame progress | frame={time_step + 1}/{loop_length} | dynamic_cells={len(dynamic_cells)}',
            )

    _emit_progress(progress_callback, 'Dynamic loop generation completed successfully.')
    return frames
