from dev.experiments.dynamic_port.pipeline import run_dynamic_port_experiment
from dev.experiments.static_artificial.pipeline import run_static_artificial_experiment


# Edit only this line:
RUN_CONTEXT = "static_artificial"  # "static_artificial" | "dynamic_port" | "both"


def main():
    if RUN_CONTEXT == "static_artificial":
        run_static_artificial_experiment()
    elif RUN_CONTEXT == "dynamic_port":
        run_dynamic_port_experiment()
    elif RUN_CONTEXT == "both":
        run_static_artificial_experiment()
        print("\n" + "=" * 72)
        run_dynamic_port_experiment()
    else:
        raise ValueError(
            "RUN_CONTEXT must be one of: "
            "'static_artificial', 'dynamic_port', or 'both'."
        )


if __name__ == "__main__":
    main()
