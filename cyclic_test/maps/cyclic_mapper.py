from cyclic_test.maps.connectivity_postprocessor import (
    reduce_excess_bidirectionals_and_restore_connectivity,
)
from cyclic_test.maps.cycle_obstacle_cleanup import (
    remove_obstacle_connected_cyclic_transitions,
)
from cyclic_test.maps.cycle_pattern_mapper import overlay_cyclic_transitions


def apply_cyclic_mapping(base_maps):
    """
    Applies the full cyclic-mapping pipeline to every base map.

    Pipeline per map:
        1. overlay raw cyclic transitions
        2. remove cyclic transitions that touch obstacles and repair local cycles
        3. reduce excess bidirectionals and restore connectivity where needed
    """
    cyclic_maps = {}

    for map_name, base_map in base_maps.items():
        cyclic_grid = overlay_cyclic_transitions(base_map)
        cyclic_grid = remove_obstacle_connected_cyclic_transitions(cyclic_grid)
        cyclic_grid = reduce_excess_bidirectionals_and_restore_connectivity(cyclic_grid)
        cyclic_maps[map_name] = cyclic_grid

    return cyclic_maps