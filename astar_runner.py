import heapq


def _find_symbol(grid, symbol):
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            if value == symbol:
                return (r, c)
    return None


def _heuristic(current, goal):
    # Traversable vertices are two cells apart in the composite grid,
    # so divide the Manhattan distance by 2.
    return (abs(current[0] - goal[0]) + abs(current[1] - goal[1])) // 2


def _get_neighbors(grid, position):
    r, c = position
    n = len(grid)
    neighbors = []

    directions = [
        (-2, 0, '↑'),
        (2, 0, '↓'),
        (0, -2, '←'),
        (0, 2, '→'),
    ]

    for dr, dc, required_arrow in directions:
        nr, nc = r + dr, c + dc
        arrow_r, arrow_c = r + (dr // 2), c + (dc // 2)

        if not (0 <= nr < n and 0 <= nc < n):
            continue

        destination = grid[nr][nc]
        transition = grid[arrow_r][arrow_c]

        if transition == required_arrow and destination in {'o', 'B'}:
            neighbors.append((nr, nc))

    return neighbors


def _reconstruct_path(came_from, current):
    path = [current]

    while current in came_from:
        current = came_from[current]
        path.append(current)

    path.reverse()
    return path


def _build_frames(original_grid, path):
    astar_frames = []
    start = path[0]
    goal = path[-1]

    for position in path:
        frame = [row[:] for row in original_grid]

        # remove original A from copied frame
        frame[start[0]][start[1]] = 'o'

        # keep B visible until A reaches it
        if position != goal:
            frame[goal[0]][goal[1]] = 'B'

        frame[position[0]][position[1]] = 'A'
        astar_frames.append(frame)

    return astar_frames


def run_astar(composite_grid):
    start = _find_symbol(composite_grid, 'A')
    goal = _find_symbol(composite_grid, 'B')

    if start is None:
        raise ValueError("The composite grid must contain a start cell marked 'A'.")
    if goal is None:
        raise ValueError("The composite grid must contain a target cell marked 'B'.")

    open_heap = []
    heapq.heappush(open_heap, (_heuristic(start, goal), 0, start))

    came_from = {}
    g_score = {start: 0}
    visited = set()

    while open_heap:
        _, current_cost, current = heapq.heappop(open_heap)

        if current in visited:
            continue
        visited.add(current)

        if current == goal:
            path = _reconstruct_path(came_from, current)
            return _build_frames(composite_grid, path)

        for neighbor in _get_neighbors(composite_grid, current):
            tentative_g = current_cost + 1

            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + _heuristic(neighbor, goal)
                heapq.heappush(open_heap, (f_score, tentative_g, neighbor))

    return []