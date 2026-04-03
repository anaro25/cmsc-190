from connectivity_postprocessor import reduce_excess_bidirectionals_and_restore_connectivity
from cycle_obstacle_cleanup import remove_obstacle_connected_cyclic_transitions
from cycle_pattern_mapper import overlay_cyclic_transitions


def apply_cyclic_mapping(base_maps):
    cyclic_maps = {}

    for map_name, base_map in base_maps.items():
        cyclic_grid = overlay_cyclic_transitions(base_map)
        cyclic_grid = remove_obstacle_connected_cyclic_transitions(cyclic_grid)
        cyclic_grid = reduce_excess_bidirectionals_and_restore_connectivity(cyclic_grid)
        cyclic_maps[map_name] = cyclic_grid

    return cyclic_maps