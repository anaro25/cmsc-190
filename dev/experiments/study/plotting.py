from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.models import ConditionAggregate


def plot_metric_graph(
    *,
    branch_spec: BranchSpec,
    aggregates: list[ConditionAggregate],
    classical_getter: Callable[[ConditionAggregate], float | None],
    cyclic_getter: Callable[[ConditionAggregate], float | None],
    output_path: Path,
    y_label: str,
    title: str,
) -> None:
    x_values = [aggregate.agent_number for aggregate in aggregates]
    classical_values = [
        math.nan if classical_getter(aggregate) is None else classical_getter(aggregate)
        for aggregate in aggregates
    ]
    cyclic_values = [
        math.nan if cyclic_getter(aggregate) is None else cyclic_getter(aggregate)
        for aggregate in aggregates
    ]

    figure = plt.figure(figsize=(10, 6))
    axes = figure.add_subplot(111)
    axes.plot(x_values, classical_values, marker="o", label="Classical")
    axes.plot(x_values, cyclic_values, marker="o", label="Cyclic")
    axes.set_xlabel("Agent number")
    axes.set_ylabel(y_label)
    axes.set_title(title)
    axes.grid(True, alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def generate_graphs(
    branch_spec: BranchSpec,
    aggregates: list[ConditionAggregate],
    graphs_dir: Path,
) -> list[Path]:
    generated_paths: list[Path] = []

    runtime_path = graphs_dir / f"{branch_spec.map_type}_runtime.png"
    plot_metric_graph(
        branch_spec=branch_spec,
        aggregates=aggregates,
        classical_getter=lambda aggregate: aggregate.classical_avg_time_computation_halted,
        cyclic_getter=lambda aggregate: aggregate.cyclic_avg_time_computation_halted,
        output_path=runtime_path,
        y_label="Average time computation halted (seconds)",
        title=f"{branch_spec.display_name}: Time Computation Halted vs Agent Number",
    )
    generated_paths.append(runtime_path)

    conflicts_path = graphs_dir / f"{branch_spec.map_type}_conflicts.png"
    plot_metric_graph(
        branch_spec=branch_spec,
        aggregates=aggregates,
        classical_getter=lambda aggregate: aggregate.classical_avg_conflicts_at_halt,
        cyclic_getter=lambda aggregate: aggregate.cyclic_avg_conflicts_at_halt,
        output_path=conflicts_path,
        y_label="Average conflicts detected at halt",
        title=f"{branch_spec.display_name}: Conflicts at Halt vs Agent Number",
    )
    generated_paths.append(conflicts_path)

    if branch_spec.path_length_graph_enabled:
        path_length_path = graphs_dir / f"{branch_spec.map_type}_path_length.png"
        plot_metric_graph(
            branch_spec=branch_spec,
            aggregates=aggregates,
            classical_getter=lambda aggregate: aggregate.classical_avg_path_length,
            cyclic_getter=lambda aggregate: aggregate.cyclic_avg_path_length,
            output_path=path_length_path,
            y_label="Average path length (successful runs only)",
            title=f"{branch_spec.display_name}: Path Length vs Agent Number",
        )
        generated_paths.append(path_length_path)

    return generated_paths
