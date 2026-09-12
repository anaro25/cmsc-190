

class AStarNode:
    def __init__(self, position, time, g, h, parent):
        self.position = position
        self.time = time

        self.g = g

        self.h = h

        self.f = g + h

        self.parent = parent

def manhattan_distance(current_position, target_position):
    current_x, current_y = current_position
    target_x, target_y = target_position

    horizontal_distance = abs(current_x - target_x)
    vertical_distance = abs(current_y - target_y)

    return horizontal_distance + vertical_distance

def get_neighbors(current_position):
    x, y = current_position

    neighbors = [
        (x, y - 1),
        (x, y + 1),
        (x - 1, y),
        (x + 1, y),
        (x, y),
    ]

    return neighbors

def is_valid_move(position, next_time, constraints):
    # Simplified placeholder used by this example file.
    if position in constraints:
        return False

    return True

def low_level_astar(start_position, target_position, constraints):

    OPEN = []

    CLOSED = set()

    start_h = manhattan_distance(start_position, target_position)

    start_node = AStarNode(
        position=start_position,
        time=0,
        g=0,
        h=start_h,
        parent=None
    )

    OPEN.append(start_node)

    while OPEN:

        selected_node = min(OPEN, key=lambda node: node.f)

        OPEN.remove(selected_node)

        if selected_node.position == target_position:
            final_path = reconstruct_path(selected_node)
            return final_path

        CLOSED.add((selected_node.position, selected_node.time))

        for neighbor_position in get_neighbors(selected_node.position):
            next_time = selected_node.time + 1

            if not is_valid_move(neighbor_position, next_time, constraints):
                continue

            if (neighbor_position, next_time) in CLOSED:
                continue

            new_g = selected_node.g + 1
            new_h = manhattan_distance(neighbor_position, target_position)

            neighbor_node = AStarNode(
                position=neighbor_position,
                time=next_time,
                g=new_g,
                h=new_h,
                parent=selected_node
            )

            OPEN.append(neighbor_node)

    return None

def reconstruct_path(target_node):
    path = []

    current_node = target_node

    while current_node is not None:
        path.append(current_node.position)
        current_node = current_node.parent

    path.reverse()

    return path

def example_usage():
    start_position = (0, 0)
    target_position = (2, 2)

    constraints = []

    path = low_level_astar(
        start_position=start_position,
        target_position=target_position,
        constraints=constraints
    )

    return path
