from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dev.experiments.ref_comparison.models import RefCaseSpec, RefConditionAggregate

MARKER_SIZE = 90
CONNECTOR_LINE_WIDTH = 3.8
CONNECTOR_ENDPOINT_GAP_POINTS = 9
CLASSICAL_COLOR = "#1f77b4"
CYCLIC_COLOR = "#ff7f0e"
CYCLIC_BETTER_CONNECTOR_COLOR = "#7ED957"
CYCLIC_WORSE_CONNECTOR_COLOR = "#FF6B6B"
CYCLIC_EQUAL_CONNECTOR_COLOR = "gray"


def _connector_color(classical_value: float, cyclic_value: float, *, lower_is_better: bool) -> str:
    if math.isnan(classical_value) or math.isnan(cyclic_value):
        return CYCLIC_EQUAL_CONNECTOR_COLOR
    if classical_value == cyclic_value:
        return CYCLIC_EQUAL_CONNECTOR_COLOR
    cyclic_is_better = cyclic_value < classical_value if lower_is_better else cyclic_value > classical_value
    return CYCLIC_BETTER_CONNECTOR_COLOR if cyclic_is_better else CYCLIC_WORSE_CONNECTOR_COLOR


def _connector_linestyle(classical_value: float, cyclic_value: float, *, lower_is_better: bool) -> str:
    if math.isnan(classical_value) or math.isnan(cyclic_value) or classical_value == cyclic_value:
        return "-"
    cyclic_is_better = cyclic_value < classical_value if lower_is_better else cyclic_value > classical_value
    return "-" if cyclic_is_better else "--"


def _value_or_nan(value: float | None) -> float:
    return math.nan if value is None else float(value)


def _annotate(axes: plt.Axes, x_value: int, y_value: float, offset: tuple[int, int]) -> None:
    if math.isnan(y_value):
        return
    axes.annotate(
        f"{y_value:.2f}",
        xy=(x_value, y_value),
        xytext=offset,
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize=8,
    )


def plot_reference_metric(
    *,
    case_spec: RefCaseSpec,
    aggregate: RefConditionAggregate,
    classical_getter: Callable[[RefConditionAggregate], float | None],
    cyclic_getter: Callable[[RefConditionAggregate], float | None],
    output_path: Path,
    y_label: str,
    title: str,
    lower_is_better: bool = True,
) -> None:
    x_value = int(aggregate.agent_number)
    classical_value = _value_or_nan(classical_getter(aggregate))
    cyclic_value = _value_or_nan(cyclic_getter(aggregate))

    figure = plt.figure(figsize=(8, 5.5))
    axes = figure.add_subplot(111)

    if not math.isnan(classical_value) and not math.isnan(cyclic_value):
        axes.annotate(
            "",
            xy=(x_value, cyclic_value),
            xytext=(x_value, classical_value),
            arrowprops={
                "arrowstyle": "-",
                "color": _connector_color(classical_value, cyclic_value, lower_is_better=lower_is_better),
                "linestyle": _connector_linestyle(classical_value, cyclic_value, lower_is_better=lower_is_better),
                "linewidth": CONNECTOR_LINE_WIDTH,
                "alpha": 0.95,
                "shrinkA": CONNECTOR_ENDPOINT_GAP_POINTS,
                "shrinkB": CONNECTOR_ENDPOINT_GAP_POINTS,
            },
            zorder=1,
        )

    axes.scatter([x_value], [classical_value], marker="s", s=MARKER_SIZE, color=CLASSICAL_COLOR, edgecolors="black", linewidths=0.8, label="Classical", zorder=3)
    axes.scatter([x_value], [cyclic_value], marker="o", s=MARKER_SIZE, color=CYCLIC_COLOR, edgecolors="black", linewidths=0.8, label="Cyclic", zorder=3)
    _annotate(axes, x_value, classical_value, (6, 8))
    _annotate(axes, x_value, cyclic_value, (6, -10))

    axes.set_xlabel("Agent number")
    axes.set_xticks([x_value])
    axes.set_xticklabels([str(x_value)])
    axes.set_xlim(x_value - 0.5, x_value + 0.5)
    axes.set_ylabel(y_label)
    axes.set_title(title)
    axes.grid(True, alpha=0.3)
    axes.margins(x=0.12, y=0.18)
    axes.legend()
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def generate_reference_graphs(case_spec: RefCaseSpec, aggregate: RefConditionAggregate, graphs_dir: Path) -> list[Path]:
    graph_paths: list[Path] = []

    runtime_path = graphs_dir / f"{case_spec.case_id}_runtime.png"
    plot_reference_metric(
        case_spec=case_spec,
        aggregate=aggregate,
        classical_getter=lambda item: item.classical_avg_time_computation_halted,
        cyclic_getter=lambda item: item.cyclic_avg_time_computation_halted,
        output_path=runtime_path,
        y_label="Time computation halted (seconds)",
        title=f"{case_spec.display_name}: Time Computation Halted",
        lower_is_better=True,
    )
    graph_paths.append(runtime_path)

    if case_spec.experiment_mode == "multi_agent":
        conflicts_path = graphs_dir / f"{case_spec.case_id}_conflicts.png"
        plot_reference_metric(
            case_spec=case_spec,
            aggregate=aggregate,
            classical_getter=lambda item: item.classical_avg_conflicts_at_halt,
            cyclic_getter=lambda item: item.cyclic_avg_conflicts_at_halt,
            output_path=conflicts_path,
            y_label="Conflicts detected at halt",
            title=f"{case_spec.display_name}: Conflicts Detected",
            lower_is_better=True,
        )
        graph_paths.append(conflicts_path)

    path_length_path = graphs_dir / f"{case_spec.case_id}_total_path_length.png"
    plot_reference_metric(
        case_spec=case_spec,
        aggregate=aggregate,
        classical_getter=lambda item: item.classical_avg_total_path_length,
        cyclic_getter=lambda item: item.cyclic_avg_total_path_length,
        output_path=path_length_path,
        y_label="Total path length",
        title=f"{case_spec.display_name}: Total Path Length",
        lower_is_better=True,
    )
    graph_paths.append(path_length_path)

    turns_path = graphs_dir / f"{case_spec.case_id}_total_turns.png"
    plot_reference_metric(
        case_spec=case_spec,
        aggregate=aggregate,
        classical_getter=lambda item: item.classical_avg_total_turns,
        cyclic_getter=lambda item: item.cyclic_avg_total_turns,
        output_path=turns_path,
        y_label="Total turns",
        title=f"{case_spec.display_name}: Total Turns",
        lower_is_better=True,
    )
    graph_paths.append(turns_path)

    return graph_paths
