from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MARKER_SIZE = 7
LINE_WIDTH = 2.6
REFERENCE_LINE_WIDTH = 2.0
BASE_FIGURE_WIDTH = 10
FIGURE_HEIGHT = 6.5
CLASSICAL_COLOR = "#1f77b4"
CYCLIC_COLOR = "#ff7f0e"
RUNTIME_LIMIT_SECONDS = 30.0


def _as_float_or_nan(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _resolve_figure_width(num_ticks: int) -> float:
    return max(BASE_FIGURE_WIDTH, min(16.0, 0.65 * max(1, num_ticks)))


def _format_weight_tick(weight: float) -> str:
    return f"{weight:.1f}"


def plot_weight_line_graph(
    *,
    aggregates: list[dict[str, Any]],
    classical_getter: Callable[[dict[str, Any]], float | None],
    cyclic_getter: Callable[[dict[str, Any]], float | None],
    output_path: Path,
    y_label: str,
    title: str,
    reference_y_value: float | None = None,
) -> None:
    ordered = sorted(aggregates, key=lambda row: float(row["suboptimality_factor"]))
    x_values = [float(row["suboptimality_factor"]) for row in ordered]
    classical_values = [_as_float_or_nan(classical_getter(row)) for row in ordered]
    cyclic_values = [_as_float_or_nan(cyclic_getter(row)) for row in ordered]

    figure = plt.figure(figsize=(_resolve_figure_width(len(x_values)), FIGURE_HEIGHT))
    axes = figure.add_subplot(111)

    axes.plot(
        x_values,
        classical_values,
        marker="s",
        markersize=MARKER_SIZE,
        linewidth=LINE_WIDTH,
        color=CLASSICAL_COLOR,
        markeredgecolor="black",
        markeredgewidth=0.8,
        label="Classical",
        zorder=3,
    )
    axes.plot(
        x_values,
        cyclic_values,
        marker="o",
        markersize=MARKER_SIZE,
        linewidth=LINE_WIDTH,
        color=CYCLIC_COLOR,
        markeredgecolor="black",
        markeredgewidth=0.8,
        label="Cyclic",
        zorder=3,
    )

    if reference_y_value is not None:
        axes.axhline(
            reference_y_value,
            color="red",
            linestyle="--",
            linewidth=REFERENCE_LINE_WIDTH,
            alpha=0.85,
            zorder=0,
        )

    axes.set_xlabel("ECBS suboptimality factor")
    axes.set_ylabel(y_label)
    axes.set_title(title)
    axes.set_xticks(x_values)
    axes.set_xticklabels([_format_weight_tick(value) for value in x_values], rotation=0)
    if x_values:
        step = 0.05 if len(x_values) == 1 else max(0.05, (max(x_values) - min(x_values)) * 0.03)
        axes.set_xlim(min(x_values) - step, max(x_values) + step)
    axes.grid(True, alpha=0.3)
    axes.margins(x=0.05, y=0.12)
    axes.legend()
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def generate_additional_experiment_graphs(
    *,
    map_type: str,
    display_name: str,
    aggregates: list[dict[str, Any]],
    graphs_dir: Path,
) -> list[Path]:
    generated: list[Path] = []

    runtime_path = graphs_dir / f"{map_type}_runtime_by_weight.png"
    plot_weight_line_graph(
        aggregates=aggregates,
        classical_getter=lambda row: row.get("classical_avg_time_computation_halted"),
        cyclic_getter=lambda row: row.get("cyclic_avg_time_computation_halted"),
        output_path=runtime_path,
        y_label="Average time computation halted (seconds)",
        title=f"{display_name}: Time Computation Halted vs ECBS Weight",
        reference_y_value=RUNTIME_LIMIT_SECONDS,
    )
    generated.append(runtime_path)

    conflicts_path = graphs_dir / f"{map_type}_conflicts_by_weight.png"
    plot_weight_line_graph(
        aggregates=aggregates,
        classical_getter=lambda row: row.get("classical_avg_conflicts_at_halt"),
        cyclic_getter=lambda row: row.get("cyclic_avg_conflicts_at_halt"),
        output_path=conflicts_path,
        y_label="Average conflicts detected at halt",
        title=f"{display_name}: Conflicts at Halt vs ECBS Weight",
    )
    generated.append(conflicts_path)

    return generated
