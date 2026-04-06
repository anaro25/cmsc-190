from dev.maps.cycle_pattern_mapper import overlay_classical_transitions


def apply_classical_mapping(base_maps):
    """
    Applies classical mapping to every base map.

    Classical mapping means every transition slot between adjacent vertices
    is made bidirectional.
    """
    classical_maps = {}

    for map_name, base_map in base_maps.items():
        classical_maps[map_name] = overlay_classical_transitions(base_map)

    return classical_maps
