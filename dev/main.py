import time


def main() -> None:
    program_start_time = time.perf_counter()

    # chosen_experiment = "main_experiment"
    chosen_experiment = "additional_experiment"

    if chosen_experiment == "main_experiment":
        from dev.experiments.generalized_study import run_selected_experiment
        from dev.master_config import MAP_TYPE

        run_selected_experiment(MAP_TYPE, program_start_time=program_start_time)
    elif chosen_experiment == "additional_experiment":
        from dev.experiments.additional_experiment import run_additional_experiment

        run_additional_experiment(program_start_time=program_start_time)
    else:
        raise ValueError(
            "chosen_experiment must be either 'main_experiment' or 'additional_experiment'."
        )

    print("\n===========================" * 25)  # not shown in log files


if __name__ == "__main__":
    main()
