from __future__ import annotations

import math
from pathlib import Path
from statistics import mean
from typing import Callable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dev.experiments.ref_comparison.models import RefCaseSpec, RefConditionAggregate

MARKER_SIZE = 90
LINE_WIDTH = 2.4
CONNECTOR_LINE_WIDTH = 2.4
CONNECTOR_ENDPOINT_GAP_POINTS = 7
CLASSICAL_COLOR = "#1f77b4"
CYCLIC_COLOR = "#ff7f0e"
CYCLIC_BETTER_CONNECTOR_COLOR = "#7ED957"
CYCLIC_WORSE_CONNECTOR_COLOR = "#FF6B6B"
CYCLIC_EQUAL_CONNECTOR_COLOR = "gray"
CLASSICAL_PRESENTATION_LABEL = "Traditional A* with Classical Mapping"
CYCLIC_PRESENTATION_LABEL = "With Cyclic Mapping"


MetricGetter = Callable[[RefConditionAggregate], float | None]


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


def _mean_or_nan(values: list[float]) -> float:
    finite_values = [float(value) for value in values if not math.isnan(float(value))]
    if not finite_values:
        return math.nan
    return float(mean(finite_values))


def _per_agent(value: float | None, agent_number: int) -> float | None:
    if value is None:
        return None
    return float(value) / max(1, int(agent_number))


def _display_metric(value: float | None, *, integer_like: bool = False, time_like: bool = False) -> str:
    if value is None or math.isnan(float(value)):
        return "—"
    numeric_value = float(value)
    if integer_like:
        return str(int(round(numeric_value)))
    if time_like:
        if abs(numeric_value) < 1:
            return f"{numeric_value:.6f}".rstrip("0").rstrip(".") or "0"
        return f"{numeric_value:.3f}".rstrip("0").rstrip(".")
    return f"{numeric_value:.3f}".rstrip("0").rstrip(".")


def _safe_metric(value: float | None, *, default: float | None = None) -> float | None:
    if value is None:
        return default
    return float(value)


def _percent_reduction_gain(classical_value: float | None, cyclic_value: float | None) -> str:
    """Return signed percent change from classical to cyclic.

    Negative values mean the cyclic value is lower than the classical value
    (a reduction). Positive values mean the cyclic value is higher than the
    classical value (a gain/increase).
    """
    classical_value = _safe_metric(classical_value)
    cyclic_value = _safe_metric(cyclic_value)
    if classical_value is None or cyclic_value is None:
        return "—"
    if classical_value == 0:
        return "0.0%" if cyclic_value == 0 else "—"
    percent_change = ((cyclic_value - classical_value) / classical_value) * 100.0
    return f"{percent_change:+.1f}%"


def _sorted_map_aggregates(map_aggregates: list[RefConditionAggregate]) -> list[RefConditionAggregate]:
    return sorted(
        list(map_aggregates),
        key=lambda item: (
            item.map_number if item.map_number is not None else 10_000,
            item.map_index if item.map_index is not None else 10_000,
            item.map_label,
        ),
    )


def _series_with_average(map_aggregates: list[RefConditionAggregate], getter: MetricGetter) -> list[float]:
    values = [_value_or_nan(getter(aggregate)) for aggregate in map_aggregates]
    values.append(_mean_or_nan(values))
    return values


def _x_labels_with_average(map_aggregates: list[RefConditionAggregate]) -> list[str]:
    labels: list[str] = []
    for index, aggregate in enumerate(map_aggregates, start=1):
        map_number = aggregate.map_number if aggregate.map_number is not None else index
        labels.append(f"Map {map_number}")
    labels.append("Average")
    return labels


def _annotate_point(axes: plt.Axes, x_value: int, y_value: float, offset: tuple[int, int]) -> None:
    if math.isnan(y_value):
        return
    axes.annotate(
        f"{y_value:.2f}",
        xy=(x_value, y_value),
        xytext=offset,
        textcoords="offset points",
        ha="center",
        va="center",
        fontsize=8,
    )


def _finite_values(*series: list[float]) -> list[float]:
    values: list[float] = []
    for value_series in series:
        for value in value_series:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric_value):
                values.append(numeric_value)
    return values


def _apply_compact_y_limits(axes: plt.Axes, values: list[float], *, padding_ratio: float = 0.14) -> None:
    finite_values = _finite_values(values)
    if not finite_values:
        return

    lowest_value = min(finite_values)
    highest_value = max(finite_values)
    if lowest_value == highest_value:
        baseline = abs(highest_value)
        padding = max(baseline * padding_ratio, 1e-6)
        if highest_value == 0:
            padding = 1.0
    else:
        padding = (highest_value - lowest_value) * padding_ratio

    lower_limit = lowest_value - padding
    upper_limit = highest_value + padding
    if lowest_value >= 0 and lower_limit < 0:
        lower_limit = 0.0
    if lower_limit == upper_limit:
        upper_limit = lower_limit + 1.0
    axes.set_ylim(lower_limit, upper_limit)


def plot_reference_metric_by_map(
    *,
    map_aggregates: list[RefConditionAggregate],
    classical_getter: MetricGetter,
    cyclic_getter: MetricGetter,
    output_path: Path,
    y_label: str,
    title: str,
    lower_is_better: bool = True,
) -> None:
    sorted_aggregates = _sorted_map_aggregates(map_aggregates)
    if not sorted_aggregates:
        return

    x_labels = _x_labels_with_average(sorted_aggregates)
    x_values = list(range(1, len(x_labels) + 1))
    classical_values = _series_with_average(sorted_aggregates, classical_getter)
    cyclic_values = _series_with_average(sorted_aggregates, cyclic_getter)

    figure = plt.figure(figsize=(9.2, 5.6))
    axes = figure.add_subplot(111)

    for x_value, classical_value, cyclic_value in zip(x_values, classical_values, cyclic_values):
        if math.isnan(classical_value) or math.isnan(cyclic_value):
            continue
        axes.annotate(
            "",
            xy=(x_value, cyclic_value),
            xytext=(x_value, classical_value),
            arrowprops={
                "arrowstyle": "-",
                "color": _connector_color(classical_value, cyclic_value, lower_is_better=lower_is_better),
                "linestyle": _connector_linestyle(classical_value, cyclic_value, lower_is_better=lower_is_better),
                "linewidth": CONNECTOR_LINE_WIDTH,
                "alpha": 0.90,
                "shrinkA": CONNECTOR_ENDPOINT_GAP_POINTS,
                "shrinkB": CONNECTOR_ENDPOINT_GAP_POINTS,
            },
            zorder=1,
        )

    map_specific_x_values = x_values[:-1]
    map_specific_classical_values = classical_values[:-1]
    map_specific_cyclic_values = cyclic_values[:-1]

    # Connect only the actual map points. The Average point is plotted as a
    # standalone summary marker so it is not visually treated as a fourth map.
    axes.plot(
        map_specific_x_values,
        map_specific_classical_values,
        marker="s",
        markersize=7,
        linewidth=LINE_WIDTH,
        color=CLASSICAL_COLOR,
        markeredgecolor="black",
        markeredgewidth=0.8,
        label=CLASSICAL_PRESENTATION_LABEL,
        zorder=3,
    )
    axes.plot(
        map_specific_x_values,
        map_specific_cyclic_values,
        marker="o",
        markersize=7,
        linewidth=LINE_WIDTH,
        color=CYCLIC_COLOR,
        markeredgecolor="black",
        markeredgewidth=0.8,
        label=CYCLIC_PRESENTATION_LABEL,
        zorder=3,
    )
    if len(x_values) > len(map_specific_x_values):
        average_x_value = x_values[-1]
        axes.scatter(
            [average_x_value],
            [classical_values[-1]],
            marker="s",
            s=64,
            color=CLASSICAL_COLOR,
            edgecolors="black",
            linewidths=0.8,
            zorder=3,
        )
        axes.scatter(
            [average_x_value],
            [cyclic_values[-1]],
            marker="o",
            s=64,
            color=CYCLIC_COLOR,
            edgecolors="black",
            linewidths=0.8,
            zorder=3,
        )

    for x_value, classical_value, cyclic_value in zip(x_values, classical_values, cyclic_values):
        _annotate_point(axes, x_value, classical_value, (0, 10))
        _annotate_point(axes, x_value, cyclic_value, (0, -12))

    axes.set_xlabel("Map number")
    axes.set_xticks(x_values)
    axes.set_xticklabels(x_labels)
    axes.set_ylabel(y_label)
    axes.set_title(title)
    axes.grid(True, alpha=0.3)
    axes.margins(x=0.08)
    _apply_compact_y_limits(axes, classical_values + cyclic_values)
    axes.legend()
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def _summary_rows_for_map(case_spec: RefCaseSpec, aggregate: RefConditionAggregate) -> list[list[str]]:
    map_label_value = str(aggregate.map_number if aggregate.map_number is not None else aggregate.map_label or "")
    if case_spec.experiment_mode == "single_agent":
        classical_nodes = _safe_metric(aggregate.classical_avg_search_nodes_expanded, default=0.0)
        cyclic_nodes = _safe_metric(aggregate.cyclic_avg_search_nodes_expanded, default=0.0)
        return [
            [map_label_value, "Running time", _display_metric(aggregate.classical_avg_time_computation_halted, time_like=True), _display_metric(aggregate.cyclic_avg_time_computation_halted, time_like=True), _percent_reduction_gain(aggregate.classical_avg_time_computation_halted, aggregate.cyclic_avg_time_computation_halted)],
            ["", "Number of nodes", _display_metric(classical_nodes, integer_like=True), _display_metric(cyclic_nodes, integer_like=True), _percent_reduction_gain(classical_nodes, cyclic_nodes)],
            ["", "Number of turns", _display_metric(aggregate.classical_avg_total_turns, integer_like=True), _display_metric(aggregate.cyclic_avg_total_turns, integer_like=True), _percent_reduction_gain(aggregate.classical_avg_total_turns, aggregate.cyclic_avg_total_turns)],
            ["", "Total distance", _display_metric(aggregate.classical_avg_total_path_length), _display_metric(aggregate.cyclic_avg_total_path_length), _percent_reduction_gain(aggregate.classical_avg_total_path_length, aggregate.cyclic_avg_total_path_length)],
        ]

    classical_avg_conflicts = _per_agent(aggregate.classical_avg_conflicts_at_halt, aggregate.agent_number)
    cyclic_avg_conflicts = _per_agent(aggregate.cyclic_avg_conflicts_at_halt, aggregate.agent_number)
    classical_avg_turns = _per_agent(aggregate.classical_avg_total_turns, aggregate.agent_number)
    cyclic_avg_turns = _per_agent(aggregate.cyclic_avg_total_turns, aggregate.agent_number)
    classical_avg_distance = _per_agent(aggregate.classical_avg_total_path_length, aggregate.agent_number)
    cyclic_avg_distance = _per_agent(aggregate.cyclic_avg_total_path_length, aggregate.agent_number)
    return [
        [map_label_value, "Running time", _display_metric(aggregate.classical_avg_time_computation_halted, time_like=True), _display_metric(aggregate.cyclic_avg_time_computation_halted, time_like=True), _percent_reduction_gain(aggregate.classical_avg_time_computation_halted, aggregate.cyclic_avg_time_computation_halted)],
        ["", "Average number of conflicts", _display_metric(classical_avg_conflicts), _display_metric(cyclic_avg_conflicts), _percent_reduction_gain(classical_avg_conflicts, cyclic_avg_conflicts)],
        ["", "Average number of turns", _display_metric(classical_avg_turns), _display_metric(cyclic_avg_turns), _percent_reduction_gain(classical_avg_turns, cyclic_avg_turns)],
        ["", "Average total distance", _display_metric(classical_avg_distance), _display_metric(cyclic_avg_distance), _percent_reduction_gain(classical_avg_distance, cyclic_avg_distance)],
    ]


def generate_map_summary_table(*, case_spec: RefCaseSpec, map_aggregates: list[RefConditionAggregate], output_path: Path) -> None:
    rows: list[list[str]] = []
    total_block_rows = 4
    sorted_aggregates = _sorted_map_aggregates(map_aggregates)
    for aggregate in sorted_aggregates:
        rows.extend(_summary_rows_for_map(case_spec, aggregate))

    columns = [
        "Map number",
        "Path parameters\n$\\it{(averages\\ are\\ across\\ all\\ agents)}$",
        "Traditional A* with\nClassical Mapping",
        "With Cyclic\nMapping",
        "Percent\nReduction/Gain",
    ]

    fig_height = max(6.2, 1.3 + (len(rows) * 0.42))
    figure, axes = plt.subplots(figsize=(11.4, fig_height))
    axes.axis("off")

    table = axes.table(cellText=rows, colLabels=columns, colWidths=[0.14, 0.33, 0.22, 0.15, 0.16], cellLoc="center", colLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10.0)
    table.scale(1, 1.48)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("black")
        cell.set_linewidth(0.6)
        if row == 0:
            cell.set_text_props(weight="normal")
            cell.set_height(0.095)
            cell.visible_edges = "BT"
        else:
            cell.set_height(0.062)
            cell.visible_edges = ""

    # Simulate merged cells for each map-number block.
    for block_index, aggregate in enumerate(sorted_aggregates):
        block_start = 1 + block_index * total_block_rows
        block_mid = block_start + 1
        for row in range(block_start, block_start + total_block_rows):
            table[(row, 0)].get_text().set_text("")
        display_value = str(aggregate.map_number if aggregate.map_number is not None else aggregate.map_label or "")
        table[(block_mid, 0)].get_text().set_text(display_value)

    # Add bottom border to the last row of each map block for separation.
    for block_index in range(len(sorted_aggregates)):
        last_row = 1 + ((block_index + 1) * total_block_rows) - 1
        for col in range(len(columns)):
            table[(last_row, col)].visible_edges = "B"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def generate_reference_graphs(case_spec: RefCaseSpec, aggregate: RefConditionAggregate, graphs_dir: Path, *, map_aggregates: list[RefConditionAggregate] | None = None) -> list[Path]:
    graph_paths: list[Path] = []
    sorted_aggregates = _sorted_map_aggregates(list(map_aggregates or []))
    if not sorted_aggregates:
        sorted_aggregates = [aggregate]

    if case_spec.experiment_mode == "single_agent":
        runtime_path = graphs_dir / f"{case_spec.case_id}_runtime_by_map.png"
        plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: a.classical_avg_time_computation_halted, cyclic_getter=lambda a: a.cyclic_avg_time_computation_halted, output_path=runtime_path, y_label="Time computation halted (seconds)", title=f"{case_spec.display_name}: Time Computation Halted", lower_is_better=True)
        graph_paths.append(runtime_path)

        nodes_path = graphs_dir / f"{case_spec.case_id}_number_of_nodes_by_map.png"
        plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: a.classical_avg_search_nodes_expanded, cyclic_getter=lambda a: a.cyclic_avg_search_nodes_expanded, output_path=nodes_path, y_label="Number of nodes", title=f"{case_spec.display_name}: Number of Nodes", lower_is_better=True)
        graph_paths.append(nodes_path)

        turns_path = graphs_dir / f"{case_spec.case_id}_number_of_turns_by_map.png"
        plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: a.classical_avg_total_turns, cyclic_getter=lambda a: a.cyclic_avg_total_turns, output_path=turns_path, y_label="Number of turns", title=f"{case_spec.display_name}: Number of Turns", lower_is_better=True)
        graph_paths.append(turns_path)

        distance_path = graphs_dir / f"{case_spec.case_id}_total_distance_by_map.png"
        plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: a.classical_avg_total_path_length, cyclic_getter=lambda a: a.cyclic_avg_total_path_length, output_path=distance_path, y_label="Total distance", title=f"{case_spec.display_name}: Total Distance", lower_is_better=True)
        graph_paths.append(distance_path)

        table_path = graphs_dir / f"{case_spec.case_id}_astar_comparison_table.png"
        generate_map_summary_table(case_spec=case_spec, map_aggregates=sorted_aggregates, output_path=table_path)
        graph_paths.append(table_path)
        return graph_paths

    runtime_path = graphs_dir / f"{case_spec.case_id}_runtime_by_map.png"
    plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: a.classical_avg_time_computation_halted, cyclic_getter=lambda a: a.cyclic_avg_time_computation_halted, output_path=runtime_path, y_label="Time computation halted (seconds)", title=f"{case_spec.display_name}: Time Computation Halted", lower_is_better=True)
    graph_paths.append(runtime_path)

    conflicts_path = graphs_dir / f"{case_spec.case_id}_average_number_of_conflicts_by_map.png"
    plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: _per_agent(a.classical_avg_conflicts_at_halt, a.agent_number), cyclic_getter=lambda a: _per_agent(a.cyclic_avg_conflicts_at_halt, a.agent_number), output_path=conflicts_path, y_label="Average number of conflicts", title=f"{case_spec.display_name}: Average Number of Conflicts", lower_is_better=True)
    graph_paths.append(conflicts_path)

    turns_path = graphs_dir / f"{case_spec.case_id}_average_number_of_turns_by_map.png"
    plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: _per_agent(a.classical_avg_total_turns, a.agent_number), cyclic_getter=lambda a: _per_agent(a.cyclic_avg_total_turns, a.agent_number), output_path=turns_path, y_label="Average number of turns", title=f"{case_spec.display_name}: Average Number of Turns", lower_is_better=True)
    graph_paths.append(turns_path)

    distance_path = graphs_dir / f"{case_spec.case_id}_average_total_distance_by_map.png"
    plot_reference_metric_by_map(map_aggregates=sorted_aggregates, classical_getter=lambda a: _per_agent(a.classical_avg_total_path_length, a.agent_number), cyclic_getter=lambda a: _per_agent(a.cyclic_avg_total_path_length, a.agent_number), output_path=distance_path, y_label="Average total distance", title=f"{case_spec.display_name}: Average Total Distance", lower_is_better=True)
    graph_paths.append(distance_path)

    table_path = graphs_dir / f"{case_spec.case_id}_ecbs_comparison_table.png"
    generate_map_summary_table(case_spec=case_spec, map_aggregates=sorted_aggregates, output_path=table_path)
    graph_paths.append(table_path)
    return graph_paths
