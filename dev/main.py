from dev.experiments.generalized_study import run_selected_experiment
from dev.master_config import MAP_TYPE


def main() -> None:
    run_selected_experiment(MAP_TYPE)


if __name__ == "__main__":
    main()
