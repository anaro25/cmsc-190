from dev.experiments.generalized_study import run_selected_experiment


# Uncomment exactly one MAP_TYPE.
MAP_TYPE = "static_artificial"
# MAP_TYPE = "dynamic_port"
# MAP_TYPE = "dynamic_campus_area_1"
# MAP_TYPE = "dynamic_campus_area_2"

# Branch-specific deterministic seeds.
# Re-running the same branch with the same seed reproduces the same experiment setup.
BRANCH_SEEDS = {
    "static_artificial": 101,
    "dynamic_port": 201,
    "dynamic_campus_area_1": 301,
    "dynamic_campus_area_2": 401,
}


def main():
    run_selected_experiment(MAP_TYPE, seed_base=BRANCH_SEEDS[MAP_TYPE])


if __name__ == "__main__":
    main()
