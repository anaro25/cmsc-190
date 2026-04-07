from dev.core.composite_elements import Special
from dev.maps.obstacle_generator import apply_artificial_vertices


def get_composite_dimensions(base_rows, base_cols):
    composite_rows = (2 * base_rows) - 1
    composite_cols = (2 * base_cols) - 1
    return composite_rows, composite_cols


def create_empty_composite_map(base_rows, base_cols):
    composite_rows, composite_cols = get_composite_dimensions(base_rows, base_cols)

    return [
        [Special.PLACEHOLDER for _ in range(composite_cols)]
        for _ in range(composite_rows)
    ]


def create_base_map(base_rows, base_cols, obstacle_ratio=0.40, rng=None):
    composite_map = create_empty_composite_map(base_rows, base_cols)
    apply_artificial_vertices(composite_map, obstacle_ratio=obstacle_ratio, rng=rng)
    return composite_map


def assemble_base_maps(map_specs, obstacle_ratio=0.40, rng=None):
    base_maps = {}

    for spec in map_specs:
        map_name = spec["name"]
        base_rows = spec["base_rows"]
        base_cols = spec["base_cols"]

        base_maps[map_name] = create_base_map(
            base_rows=base_rows,
            base_cols=base_cols,
            obstacle_ratio=obstacle_ratio,
            rng=rng,
        )

    return base_maps
