"""Compatibility wrapper for the generalized experiment runner.

The implementation now lives under ``dev.experiments.study`` so the orchestration,
preparation, logging, aggregation, metrics-data, and visualization concerns stay separated.
"""

from dev.experiments.study import run_selected_experiment

__all__ = ["run_selected_experiment"]
