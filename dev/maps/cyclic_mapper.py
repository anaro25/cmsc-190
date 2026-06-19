from dev.maps.connectivity_postprocessor import (
    reduce_excess_bidirectionals_and_restore_connectivity,
    restore_connectivity_without_removing_extras,
)
from dev.maps.cycle_obstacle_cleanup import (
    remove_obstacle_connected_cyclic_transitions,
)
from dev.maps.cycle_pattern_mapper import overlay_cyclic_transitions


def apply_cyclic_mapping(base_maps, *, remove_extra_transitions=True):
    """
    Applies the full cyclic-mapping pipeline to every base map.

    Pipeline per map:
        1. overlay raw cyclic transitions
        2. remove cyclic transitions that touch obstacles and repair local cycles
        3. optionally reduce excess bidirectionals, while always restoring
           required connectivity where needed

    The optional transition-reduction step is kept enabled by default so the
    main experiment preserves its existing behavior. Reference-comparison
    experiments may disable it through master_config_ref_comparison.py when a
    less radically reduced cyclic map is desired. Required connectivity repair
    is still applied when that reduction step is disabled so that the map does
    not become accidentally disconnected.
    """
    cyclic_maps = {}

    for map_name, base_map in base_maps.items():
        cyclic_grid = overlay_cyclic_transitions(base_map)
        cyclic_grid = remove_obstacle_connected_cyclic_transitions(cyclic_grid)
        if remove_extra_transitions:
            cyclic_grid = reduce_excess_bidirectionals_and_restore_connectivity(cyclic_grid)
        else:
            cyclic_grid = restore_connectivity_without_removing_extras(cyclic_grid)
        cyclic_maps[map_name] = cyclic_grid

    return cyclic_maps