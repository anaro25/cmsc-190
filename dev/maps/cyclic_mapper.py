from dev.maps.connectivity_postprocessor import (
    add_bidirectional_transitions_between_adjacent_free_vertices,
    reduce_excess_bidirectionals_and_restore_connectivity,
    restore_connectivity_without_removing_extras,
)
from dev.maps.cycle_obstacle_cleanup import (
    remove_obstacle_connected_cyclic_transitions,
)
from dev.maps.cycle_pattern_mapper import overlay_cyclic_transitions


def apply_cyclic_mapping(
    base_maps,
    *,
    remove_extra_transitions=True,
    add_transitions_between_free_spaces=False,
):
    """
    Applies the cyclic-mapping pipeline to every base map.

    Pipeline per map:
        1. overlay raw cyclic transitions
        2. remove cyclic transitions that touch obstacles and repair local cycles
        3. optionally reduce excess bidirectionals, while always restoring
           required connectivity where needed
        4. optionally force every adjacent pair of free vertices to have a
           bidirectional transition

    Both optional controls default to the behavior used by the main experiment:
    redundant-transition reduction stays enabled and the final free-space
    transition addition stays disabled. Reference-comparison experiments may
    override either option through master_config_ref_comparison.py.
    """
    cyclic_maps = {}

    for map_name, base_map in base_maps.items():
        cyclic_grid = overlay_cyclic_transitions(base_map)
        cyclic_grid = remove_obstacle_connected_cyclic_transitions(cyclic_grid)
        if remove_extra_transitions:
            cyclic_grid = reduce_excess_bidirectionals_and_restore_connectivity(cyclic_grid)
        else:
            cyclic_grid = restore_connectivity_without_removing_extras(cyclic_grid)

        if add_transitions_between_free_spaces:
            cyclic_grid = add_bidirectional_transitions_between_adjacent_free_vertices(cyclic_grid)

        cyclic_maps[map_name] = cyclic_grid

    return cyclic_maps
