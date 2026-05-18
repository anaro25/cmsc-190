
# A node represents one possible position of the agent.

class AStarNode:
    def __init__(self, position, time, g, h, parent):
        self.position = position
        self.time = time

        # g(n) = distance from the start node to this node
        self.g = g

        # h(n) = estimated distance from this node to the target
        self.h = h

        # f(n) = g(n) + h(n)
        self.f = g + h

        # parent is used later to trace back the final path
        self.parent = parent


# This is the heuristic used by A*.
# For grid maps, we commonly use Manhattan distance.

def manhattan_distance(current_position, target_position):
    current_x, current_y = current_position
    target_x, target_y = target_position

    horizontal_distance = abs(current_x - target_x)
    vertical_distance = abs(current_y - target_y)

    return horizontal_distance + vertical_distance


# This function returns the neighboring cells that the agent
# can move to.
# In the actual project, this depends on the graph transitions.
# For explanation, we just show the idea.

def get_neighbors(current_position):
    x, y = current_position

    neighbors = [
        (x, y - 1),  # move up
        (x, y + 1),  # move down
        (x - 1, y),  # move left
        (x + 1, y),  # move right
        (x, y),      # wait in place
    ]

    return neighbors


# This checks whether a position can be visited.
#
# In the actual project, this would check:
#   - if the cell is inside the map
#   - if the cell is not an obstacle
#   - if the transition is allowed
#   - if the move violates any CBS constraint

def is_valid_move(position, next_time, constraints):
    # This is only a placeholder for presentation.
    # We write it this way so the logic is easy to explain.

    if position in constraints:
        return False

    return True


# This is the simplified A* algorithm.

def low_level_astar(start_position, target_position, constraints):
    # OPEN contains discovered but unexplored nodes.
    OPEN = []

    # CLOSED contains nodes that were already explored.
    CLOSED = set()

    # Create the first node at the agent's starting position.
    start_h = manhattan_distance(start_position, target_position)

    start_node = AStarNode(
        position=start_position,
        time=0,
        g=0,
        h=start_h,
        parent=None
    )

    OPEN.append(start_node)

    # Keep searching while there are still nodes to explore.
    while OPEN:

        # Step 1:
        # Select the node in OPEN with the smallest f(n).

        selected_node = min(OPEN, key=lambda node: node.f)

        OPEN.remove(selected_node)

        # Step 2:
        # Check if the selected node is already the target.
        # If yes, A* is done.

        if selected_node.position == target_position:
            final_path = reconstruct_path(selected_node)
            return final_path

        # Step 3:
        # Move the selected node to CLOSED.
        # This means we are done exploring it.

        CLOSED.add((selected_node.position, selected_node.time))

        # Step 4:
        # Look at all neighboring positions.

        for neighbor_position in get_neighbors(selected_node.position):
            next_time = selected_node.time + 1

            # Skip neighbor if it is blocked or violates constraints.
            if not is_valid_move(neighbor_position, next_time, constraints):
                continue

            # Skip neighbor if it was already explored.
            if (neighbor_position, next_time) in CLOSED:
                continue

            # Step 5:
            # Compute g, h, and f for the neighbor.

            new_g = selected_node.g + 1
            new_h = manhattan_distance(neighbor_position, target_position)

            neighbor_node = AStarNode(
                position=neighbor_position,
                time=next_time,
                g=new_g,
                h=new_h,
                parent=selected_node
            )

            # Step 6:
            # Add the neighbor to OPEN.

            OPEN.append(neighbor_node)

    # If OPEN becomes empty, then there is no path.
    return None


# Once the target is found, we reconstruct the path.
# We do this by starting from the target node and repeatedly
# going back to its parent.

def reconstruct_path(target_node):
    path = []

    current_node = target_node

    while current_node is not None:
        path.append(current_node.position)
        current_node = current_node.parent

    # The path was collected from target to start,
    # so we reverse it.
    path.reverse()

    return path


# Example idea:
# start_position  = agent's current cell
# target_position = agent's goal cell
# A* searches for a path from start_position to target_position.

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
