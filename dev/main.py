import time

from dev.experiments.generalized_study import run_selected_experiment
from dev.master_config import MAP_TYPE


def main() -> None:
    program_start_time = time.perf_counter()
    run_selected_experiment(MAP_TYPE, program_start_time=program_start_time)


if __name__ == "__main__":
    main()
