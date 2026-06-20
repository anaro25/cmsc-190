from __future__ import annotations

import time


# Select exactly one experiment family.
SELECTED_EXPERIMENT = "ref_comparison"
# SELECTED_EXPERIMENT = "main_experiment"


def main() -> None:
    program_start_time = time.perf_counter()

    if SELECTED_EXPERIMENT == "main_experiment":
        from dev.experiments.generalized_study import run_selected_experiment
        from dev.master_config import MAP_TYPE

        run_selected_experiment(MAP_TYPE, program_start_time=program_start_time)
    elif SELECTED_EXPERIMENT == "ref_comparison":
        from dev.experiments.ref_comparison.orchestrator import run_selected_ref_comparison

        run_selected_ref_comparison(program_start_time=program_start_time)
    else:
        raise ValueError(
            "SELECTED_EXPERIMENT must be either 'main_experiment' or 'ref_comparison'."
        )

    print("===========================\n" * 25)  # not shown in log files


if __name__ == "__main__":
    main()
