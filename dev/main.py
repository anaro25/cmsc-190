from dev.experiments.generalized_study import run_selected_experiment


# Uncomment exactly one MAP_TYPE.
MAP_TYPE = "static_artificial"
# MAP_TYPE = "dynamic_port"
# MAP_TYPE = "dynamic_campus_area_1"
# MAP_TYPE = "dynamic_campus_area_2"

# Optional deterministic seed base for reproducibility.
SEED_BASE = 1


def main():
    run_selected_experiment(MAP_TYPE, seed_base=SEED_BASE)


if __name__ == "__main__":
    main()
