
# Constraint Tree Node

class ConstraintTreeNode:
    def __init__(self, constraints, paths):
        self.constraints = constraints
        self.paths = paths
        self.cost = self.compute_total_path_cost()

    def compute_total_path_cost(self):
        total_cost = 0

        for agent_path in self.paths.values():
            total_cost += len(agent_path)

        return total_cost


# Main CBS Solver

def cbs_solver(agents, starts, goals, graph):
    """
    This is the main flow of CBS.

    CBS works by creating a Constraint Tree.
    Each node in the tree stores:
        1. a set of constraints
        2. the path of each agent under those constraints
        3. the total cost of all paths
    """

    # Step 1:
    # Create the root node.
    # The root node has no constraints yet.
    # This means each agent plans independently.

    root_constraints = []

    root_paths = {}

    for agent in agents:
        path = find_path_for_one_agent(
            agent=agent,
            start=starts[agent],
            goal=goals[agent],
            graph=graph,
            constraints=root_constraints
        )

        root_paths[agent] = path

    root_node = ConstraintTreeNode(
        constraints=root_constraints,
        paths=root_paths
    )

    # OPEN contains the leaf nodes of the Constraint Tree
    # that still need to be checked.
    OPEN = [root_node]

    # Step 2:
    # Keep expanding the Constraint Tree until a conflict-free
    # solution is found.

    while OPEN:

        # Step 3:
        # Select the leaf node with the least total path cost.

        current_node = select_node_with_lowest_cost(OPEN)

        # Step 4:
        # Check if the paths in the current node have conflicts.

        conflict = find_first_conflict(current_node.paths)

        # If there is no conflict, then the current node already
        # contains the final solution.

        if conflict is None:
            return current_node.paths

        # Step 5:
        # If a conflict is found between two agents, split the
        # current node into two child nodes.

        # Child node 1 constrains agent i.
        # Child node 2 constrains agent j.

        agent_i = conflict.agent_i
        agent_j = conflict.agent_j

        child_1 = create_child_node(
            parent_node=current_node,
            constrained_agent=agent_i,
            conflict=conflict,
            agents=agents,
            starts=starts,
            goals=goals,
            graph=graph
        )

        child_2 = create_child_node(
            parent_node=current_node,
            constrained_agent=agent_j,
            conflict=conflict,
            agents=agents,
            starts=starts,
            goals=goals,
            graph=graph
        )

        # The child nodes are added back to OPEN.
        # Later, CBS will again select the leaf node with the
        # least total path cost.
        OPEN.append(child_1)
        OPEN.append(child_2)

    return None


# Creating Child Nodes

def create_child_node(
    parent_node,
    constrained_agent,
    conflict,
    agents,
    starts,
    goals,
    graph
):
    """
    A child node is almost the same as its parent node.

    The difference is that we add one new constraint.
    Then, only the constrained agent needs to replan its path.
    The other agents keep their old paths.
    """

    child_constraints = list(parent_node.constraints)

    new_constraint = make_constraint(
        agent=constrained_agent,
        conflict=conflict
    )

    child_constraints.append(new_constraint)

    child_paths = dict(parent_node.paths)

    new_path = find_path_for_one_agent(
        agent=constrained_agent,
        start=starts[constrained_agent],
        goal=goals[constrained_agent],
        graph=graph,
        constraints=child_constraints
    )

    child_paths[constrained_agent] = new_path

    child_node = ConstraintTreeNode(
        constraints=child_constraints,
        paths=child_paths
    )

    return child_node


# Conflict Checking

def find_first_conflict(paths):
    """
    This checks if any two agents conflict with each other.

    A vertex conflict happens when:
        agent i and agent j are in the same cell at the same time

    An edge conflict happens when:
        agent i moves from A to B
        while agent j moves from B to A
        at the same time
    """

    for time in all_timesteps(paths):

        for agent_i in paths:
            for agent_j in paths:

                if agent_i >= agent_j:
                    continue

                i_current = get_position(paths[agent_i], time)
                j_current = get_position(paths[agent_j], time)

                i_previous = get_position(paths[agent_i], time - 1)
                j_previous = get_position(paths[agent_j], time - 1)

                # Vertex conflict
                if i_current == j_current:
                    return Conflict(
                        kind="vertex",
                        agent_i=agent_i,
                        agent_j=agent_j,
                        time=time,
                        location=i_current
                    )

                # Edge conflict
                if i_previous == j_current and j_previous == i_current:
                    return Conflict(
                        kind="edge",
                        agent_i=agent_i,
                        agent_j=agent_j,
                        time=time,
                        location=(i_previous, i_current)
                    )

    return None


# Constraints

def make_constraint(agent, conflict):
    """
    A constraint tells one agent what it is not allowed to do.

    If the conflict is a vertex conflict:
        the agent cannot be in that cell at that time

    If the conflict is an edge conflict:
        the agent cannot move through that edge at that time
    """

    if conflict.kind == "vertex":
        return {
            "agent": agent,
            "kind": "vertex",
            "time": conflict.time,
            "blocked_cell": conflict.location
        }

    if conflict.kind == "edge":
        return {
            "agent": agent,
            "kind": "edge",
            "time": conflict.time,
            "blocked_edge": conflict.location
        }


# Helper Functions

def select_node_with_lowest_cost(OPEN):
    """
    CBS always expands the leaf node with the least total path cost.
    """

    best_node = min(OPEN, node.cost)

    OPEN.remove(best_node)

    return best_node


class Conflict:
    def __init__(self, kind, agent_i, agent_j, time, location):
        self.kind = kind
        self.agent_i = agent_i
        self.agent_j = agent_j
        self.time = time
        self.location = location