def run_selected_experiment(*args, **kwargs):
    from dev.experiments.generalized_study import run_selected_experiment as _run_selected_experiment

    return _run_selected_experiment(*args, **kwargs)


__all__ = ["run_selected_experiment"]
