from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dev.experiments.branch_specs import BranchSpec
from dev.experiments.study.models import ConditionAggregate


MARKER_SIZE = 90
CONNECTOR_LINE_WIDTH = 3.8
CONNECTOR_ENDPOINT_GAP_POINTS = 9
REFERENCE_LINE_WIDTH = 2.0
CLASSICAL_LABEL_OFFSET = (6, 6)
CYCLIC_LABEL_OFFSET = (6, -10)
BASE_FIGURE_WIDTH = 10
MAX_FIGURE_WIDTH = 40
FIGURE_HEIGHT = 6.5
TICK_FONT_SIZE_DEFAULT = 10
TICK_FONT_SIZE_DENSE = 8
TICK_FONT_SIZE_VERY_DENSE = 6
CLASSICAL_COLOR = "#1f77b4"
CYCLIC_COLOR = "#ff7f0e"
CYCLIC_BETTER_CONNECTOR_COLOR = "#7ED957"
CYCLIC_WORSE_CONNECTOR_COLOR = "#FF6B6B"
CYCLIC_EQUAL_CONNECTOR_COLOR = "gray"
RUNTIME_LIMIT_SECONDS = 30.0


def _annotate_series(
    axes: plt.Axes,
    x_values: list[int],
    y_values: list[float],
    *,
    offset: tuple[int, int],
) -> None:
    for x_value, y_value in zip(x_values, y_values):
        if math.isnan(y_value):
            continue
        axes.annotate(
            f"{y_value:.2f}",
            xy=(x_value, y_value),
            xytext=offset,
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=8,
        )


def _resolve_display_x_ticks(data_x_values: list[int]) -> list[int]:
    return sorted({int(value) for value in data_x_values})


def _resolve_figure_width(num_ticks: int) -> float:
    if num_ticks <= 0:
        return BASE_FIGURE_WIDTH
    return min(MAX_FIGURE_WIDTH, max(BASE_FIGURE_WIDTH, 0.28 * num_ticks))


def _tick_label_rotation(num_ticks: int) -> int:
    return 90 if num_ticks > 20 else 0


def _tick_font_size(num_ticks: int) -> int:
    if num_ticks > 120:
        return TICK_FONT_SIZE_VERY_DENSE
    if num_ticks > 50:
        return TICK_FONT_SIZE_DENSE
    return TICK_FONT_SIZE_DEFAULT


def _connector_color(classical_value: float, cyclic_value: float) -> str:
    if math.isnan(classical_value) or math.isnan(cyclic_value):
        return CYCLIC_EQUAL_CONNECTOR_COLOR
    if cyclic_value < classical_value:
        return CYCLIC_BETTER_CONNECTOR_COLOR
    if cyclic_value > classical_value:
        return CYCLIC_WORSE_CONNECTOR_COLOR
    return CYCLIC_EQUAL_CONNECTOR_COLOR


def _connector_linestyle(classical_value: float, cyclic_value: float) -> str:
    if math.isnan(classical_value) or math.isnan(cyclic_value):
        return "-"
    if cyclic_value > classical_value:
        return "--"
    return "-"


def plot_metric_graph(
    *,
    branch_spec: BranchSpec,
    aggregates: list[ConditionAggregate],
    classical_getter: Callable[[ConditionAggregate], float | None],
    cyclic_getter: Callable[[ConditionAggregate], float | None],
    output_path: Path,
    y_label: str,
    title: str,
    reference_y_value: float | None = None,
    reference_y_label: str | None = None,
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

    display_x_ticks = _resolve_display_x_ticks(x_values)
    figure = plt.figure(figsize=(_resolve_figure_width(len(display_x_ticks)), FIGURE_HEIGHT))
    axes = figure.add_subplot(111)
    for x_value, classical_value, cyclic_value in zip(
        x_values, classical_values, cyclic_values
    ):
        if math.isnan(classical_value) or math.isnan(cyclic_value):
            continue
        axes.annotate(
            "",
            xy=(x_value, cyclic_value),
            xytext=(x_value, classical_value),
            arrowprops={
                "arrowstyle": "-",
                "color": _connector_color(classical_value, cyclic_value),
                "linestyle": _connector_linestyle(classical_value, cyclic_value),
                "linewidth": CONNECTOR_LINE_WIDTH,
                "alpha": 0.95,
                "shrinkA": CONNECTOR_ENDPOINT_GAP_POINTS,
                "shrinkB": CONNECTOR_ENDPOINT_GAP_POINTS,
            },
            zorder=1,
        )

    axes.scatter(
        x_values,
        classical_values,
        marker="s",
        s=MARKER_SIZE,
        color=CLASSICAL_COLOR,
        edgecolors="black",
        linewidths=0.8,
        label="Classical",
        zorder=3,
    )
    axes.scatter(
        x_values,
        cyclic_values,
        marker="o",
        s=MARKER_SIZE,
        color=CYCLIC_COLOR,
        edgecolors="black",
        linewidths=0.8,
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
    _annotate_series(axes, x_values, classical_values, offset=CLASSICAL_LABEL_OFFSET)
    _annotate_series(axes, x_values, cyclic_values, offset=CYCLIC_LABEL_OFFSET)
    axes.set_xlabel("Agent number")
    axes.set_xticks(display_x_ticks)
    axes.set_xticklabels(
        [str(value) for value in display_x_ticks],
        rotation=_tick_label_rotation(len(display_x_ticks)),
        fontsize=_tick_font_size(len(display_x_ticks)),
    )
    if display_x_ticks:
        axes.set_xlim(display_x_ticks[0] - 0.5, display_x_ticks[-1] + 0.5)
    axes.set_ylabel(y_label)
    axes.set_title(title)
    axes.grid(True, alpha=0.3)
    axes.margins(x=0.05, y=0.12)
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
        reference_y_value=RUNTIME_LIMIT_SECONDS,
        reference_y_label="30-second limit",
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
