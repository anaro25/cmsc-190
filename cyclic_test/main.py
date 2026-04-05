from cyclic_test.config.base_map_config import MAP_SPECS
from cyclic_test.maps.base_map_factory import assemble_base_maps
from cyclic_test.maps.classical_mapper import apply_classical_mapping
from cyclic_test.maps.cyclic_mapper import apply_cyclic_mapping
from cyclic_test.maps.map_logger import write_classical_composites, write_cyclic_composites
from cyclic_test.mapf.mapf_runner import run_single_mapf_for_selected_map


DEFAULT_NUM_OF_AGENTS = 9
DEFAULT_MAX_SOLVER_RUNTIME_SECONDS = 20.0


def main():
    base_maps = assemble_base_maps(MAP_SPECS, obstacle_ratio=0.40)

    classical_maps = apply_classical_mapping(base_maps)
    cyclic_maps = apply_cyclic_mapping(base_maps)

    write_classical_composites({"map_1": classical_maps["map_1"]})
    write_cyclic_composites({"map_1": cyclic_maps["map_1"]})

    cyclic_result = run_single_mapf_for_selected_map(
        mapping_name="cyclic",
        mapped_grids=cyclic_maps,
        selected_map_name="map_1",
        num_agents=DEFAULT_NUM_OF_AGENTS,
        seed=None,
        max_solver_runtime_seconds=DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
    )

    if cyclic_result is None:
        return

    print()

    run_single_mapf_for_selected_map(
        mapping_name="classical",
        mapped_grids=classical_maps,
        selected_map_name="map_1",
        num_agents=DEFAULT_NUM_OF_AGENTS,
        seed=None,
        max_solver_runtime_seconds=DEFAULT_MAX_SOLVER_RUNTIME_SECONDS,
    )


if __name__ == "__main__":
    main()
