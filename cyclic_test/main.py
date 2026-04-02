from base_map_config import MAP_SPECS
from base_map_factory import assemble_base_maps
from cyclic_mapper import apply_cyclic_mapping
from map_logger import write_cyclic_composites


def main():
    base_maps = assemble_base_maps(MAP_SPECS, obstacle_ratio=0.40)
    cyclic_maps = apply_cyclic_mapping(base_maps)
    write_cyclic_composites(cyclic_maps)


if __name__ == "__main__":
    main()
