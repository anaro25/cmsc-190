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


def _per_agent(value: float | None, agent_number: int) -> float | None:
    if value is None:
        return None
    return float(value) / max(1, int(agent_number))


def _annotate(axes: plt.Axes, x_value: int, y_value: float, offset: tuple[int, int]) -> None:
    if math.isnan(y_value):
        return
    axes.annotate(f"{y_value:.2f}", xy=(x_value, y_value), xytext=offset, textcoords="offset points", ha="left", va="center", fontsize=8)


def plot_reference_metric(*, case_spec: RefCaseSpec, aggregate: RefConditionAggregate, classical_getter: Callable[[RefConditionAggregate], float | None], cyclic_getter: Callable[[RefConditionAggregate], float | None], output_path: Path, y_label: str, title: str, lower_is_better: bool = True) -> None:
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

    if case_spec.experiment_mode == "single_agent":
        classical_label = "Traditional A* + Classical"
        cyclic_label = "Traditional A* + Cyclic"
    else:
        classical_label = "ECBS + Classical"
        cyclic_label = "ECBS + Cyclic"
    map_suffix = f" ({aggregate.map_label})" if aggregate.map_label else ""

    axes.scatter([x_value], [classical_value], marker="s", s=MARKER_SIZE, color=CLASSICAL_COLOR, edgecolors="black", linewidths=0.8, label=classical_label, zorder=3)
    axes.scatter([x_value], [cyclic_value], marker="o", s=MARKER_SIZE, color=CYCLIC_COLOR, edgecolors="black", linewidths=0.8, label=cyclic_label, zorder=3)
    _annotate(axes, x_value, classical_value, (6, 8))
    _annotate(axes, x_value, cyclic_value, (6, -10))

    axes.set_xlabel("Agent number")
    axes.set_xticks([x_value])
    axes.set_xticklabels([str(x_value)])
    axes.set_xlim(x_value - 0.5, x_value + 0.5)
    axes.set_ylabel(y_label)
    axes.set_title(title + map_suffix)
    axes.grid(True, alpha=0.3)
    axes.margins(x=0.12, y=0.18)
    axes.legend()
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


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


def _reduced_proportion(classical_value: float | None, cyclic_value: float | None) -> str:
    classical_value = _safe_metric(classical_value)
    cyclic_value = _safe_metric(cyclic_value)
    if classical_value is None or cyclic_value is None:
        return "—"
    if classical_value == 0:
        return "0.0%" if cyclic_value == 0 else "—"
    reduction = ((classical_value - cyclic_value) / classical_value) * 100.0
    return f"{reduction:.1f}%"


def _summary_rows_for_map(case_spec: RefCaseSpec, aggregate: RefConditionAggregate) -> list[list[str]]:
    map_label_value = str(aggregate.map_number if aggregate.map_number is not None else aggregate.map_label or "")
    if case_spec.experiment_mode == "single_agent":
        classical_nodes = _safe_metric(aggregate.classical_avg_search_nodes_expanded, default=0.0)
        cyclic_nodes = _safe_metric(aggregate.cyclic_avg_search_nodes_expanded, default=0.0)
        return [
            [map_label_value, "Running time/s", _display_metric(aggregate.classical_avg_time_computation_halted, time_like=True), _display_metric(aggregate.cyclic_avg_time_computation_halted, time_like=True), _reduced_proportion(aggregate.classical_avg_time_computation_halted, aggregate.cyclic_avg_time_computation_halted)],
            ["", "Number of nodes", _display_metric(classical_nodes, integer_like=True), _display_metric(cyclic_nodes, integer_like=True), _reduced_proportion(classical_nodes, cyclic_nodes)],
            ["", "Number of turns", _display_metric(aggregate.classical_avg_total_turns, integer_like=True), _display_metric(aggregate.cyclic_avg_total_turns, integer_like=True), _reduced_proportion(aggregate.classical_avg_total_turns, aggregate.cyclic_avg_total_turns)],
            ["", "Total distance/m", _display_metric(aggregate.classical_avg_total_path_length), _display_metric(aggregate.cyclic_avg_total_path_length), _reduced_proportion(aggregate.classical_avg_total_path_length, aggregate.cyclic_avg_total_path_length)],
        ]

    classical_avg_conflicts = _per_agent(aggregate.classical_avg_conflicts_at_halt, aggregate.agent_number)
    cyclic_avg_conflicts = _per_agent(aggregate.cyclic_avg_conflicts_at_halt, aggregate.agent_number)
    classical_avg_turns = _per_agent(aggregate.classical_avg_total_turns, aggregate.agent_number)
    cyclic_avg_turns = _per_agent(aggregate.cyclic_avg_total_turns, aggregate.agent_number)
    classical_avg_distance = _per_agent(aggregate.classical_avg_total_path_length, aggregate.agent_number)
    cyclic_avg_distance = _per_agent(aggregate.cyclic_avg_total_path_length, aggregate.agent_number)
    return [
        [map_label_value, "Running time/s", _display_metric(aggregate.classical_avg_time_computation_halted, time_like=True), _display_metric(aggregate.cyclic_avg_time_computation_halted, time_like=True), _reduced_proportion(aggregate.classical_avg_time_computation_halted, aggregate.cyclic_avg_time_computation_halted)],
        ["", "Average number of conflicts", _display_metric(classical_avg_conflicts), _display_metric(cyclic_avg_conflicts), _reduced_proportion(classical_avg_conflicts, cyclic_avg_conflicts)],
        ["", "Average number of turns", _display_metric(classical_avg_turns), _display_metric(cyclic_avg_turns), _reduced_proportion(classical_avg_turns, cyclic_avg_turns)],
        ["", "Average total distance/m", _display_metric(classical_avg_distance), _display_metric(cyclic_avg_distance), _reduced_proportion(classical_avg_distance, cyclic_avg_distance)],
    ]


def generate_map_summary_table(*, case_spec: RefCaseSpec, map_aggregates: list[RefConditionAggregate], output_path: Path) -> None:
    rows: list[list[str]] = []
    total_block_rows = 4
    for aggregate in map_aggregates:
        rows.extend(_summary_rows_for_map(case_spec, aggregate))

    if case_spec.experiment_mode == "single_agent":
        columns = ["Map number", "Path parameters", "Traditional\nA-star", "With Cyclic\nMapping", "Reduced\nproportion"]
    else:
        columns = ["Map number", "Path parameters", "ECBS +\nClassical", "ECBS +\nCyclic", "Reduced\nproportion"]

    fig_height = max(6.2, 1.3 + (len(rows) * 0.42))
    figure, axes = plt.subplots(figsize=(9.8, fig_height))
    axes.axis("off")

    table = axes.table(cellText=rows, colLabels=columns, colWidths=[0.19, 0.34, 0.16, 0.16, 0.15], cellLoc="center", colLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    table.scale(1, 1.45)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("black")
        cell.set_linewidth(0.6)
        if row == 0:
            cell.set_text_props(weight="normal")
            cell.set_height(0.08)
            cell.visible_edges = "BT"
        else:
            cell.set_height(0.062)
            cell.visible_edges = ""

    # Simulate merged cells for each map-number block.
    for block_index, aggregate in enumerate(map_aggregates):
        block_start = 1 + block_index * total_block_rows
        block_mid = block_start + 1
        for row in range(block_start, block_start + total_block_rows):
            table[(row, 0)].get_text().set_text("")
        display_value = str(aggregate.map_number if aggregate.map_number is not None else aggregate.map_label or "")
        table[(block_mid, 0)].get_text().set_text(display_value)

    # Add bottom border to the last row of each map block for separation.
    for block_index in range(len(map_aggregates)):
        last_row = 1 + ((block_index + 1) * total_block_rows) - 1
        for col in range(len(columns)):
            table[(last_row, col)].visible_edges = "B"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def generate_reference_graphs(case_spec: RefCaseSpec, aggregate: RefConditionAggregate, graphs_dir: Path, *, map_aggregates: list[RefConditionAggregate] | None = None) -> list[Path]:
    graph_paths: list[Path] = []
    map_aggregates = sorted(list(map_aggregates or [aggregate]), key=lambda item: item.map_index if item.map_index is not None else 0)

    if case_spec.experiment_mode == "single_agent":
        for item in map_aggregates:
            suffix = f"map_{item.map_number if item.map_number is not None else ((item.map_index or 0) + 1)}"
            runtime_path = graphs_dir / f"{case_spec.case_id}_{suffix}_runtime.png"
            plot_reference_metric(case_spec=case_spec, aggregate=item, classical_getter=lambda a: a.classical_avg_time_computation_halted, cyclic_getter=lambda a: a.cyclic_avg_time_computation_halted, output_path=runtime_path, y_label="Time computation halted (seconds)", title=f"{case_spec.display_name}: Time Computation Halted", lower_is_better=True)
            graph_paths.append(runtime_path)

            path_length_path = graphs_dir / f"{case_spec.case_id}_{suffix}_total_path_length.png"
            plot_reference_metric(case_spec=case_spec, aggregate=item, classical_getter=lambda a: a.classical_avg_total_path_length, cyclic_getter=lambda a: a.cyclic_avg_total_path_length, output_path=path_length_path, y_label="Total path length", title=f"{case_spec.display_name}: Total Path Length", lower_is_better=True)
            graph_paths.append(path_length_path)

            turns_path = graphs_dir / f"{case_spec.case_id}_{suffix}_total_turns.png"
            plot_reference_metric(case_spec=case_spec, aggregate=item, classical_getter=lambda a: a.classical_avg_total_turns, cyclic_getter=lambda a: a.cyclic_avg_total_turns, output_path=turns_path, y_label="Total turns", title=f"{case_spec.display_name}: Total Turns", lower_is_better=True)
            graph_paths.append(turns_path)

        table_path = graphs_dir / f"{case_spec.case_id}_astar_comparison_table.png"
        generate_map_summary_table(case_spec=case_spec, map_aggregates=map_aggregates, output_path=table_path)
        graph_paths.append(table_path)
        return graph_paths

    for item in map_aggregates:
        suffix = f"map_{item.map_number if item.map_number is not None else ((item.map_index or 0) + 1)}"
        runtime_path = graphs_dir / f"{case_spec.case_id}_{suffix}_runtime.png"
        plot_reference_metric(case_spec=case_spec, aggregate=item, classical_getter=lambda a: a.classical_avg_time_computation_halted, cyclic_getter=lambda a: a.cyclic_avg_time_computation_halted, output_path=runtime_path, y_label="Time computation halted (seconds)", title=f"{case_spec.display_name}: Time Computation Halted", lower_is_better=True)
        graph_paths.append(runtime_path)

        conflicts_path = graphs_dir / f"{case_spec.case_id}_{suffix}_conflicts.png"
        plot_reference_metric(case_spec=case_spec, aggregate=item, classical_getter=lambda a: _per_agent(a.classical_avg_conflicts_at_halt, a.agent_number), cyclic_getter=lambda a: _per_agent(a.cyclic_avg_conflicts_at_halt, a.agent_number), output_path=conflicts_path, y_label="Average number of conflicts", title=f"{case_spec.display_name}: Conflicts Detected", lower_is_better=True)
        graph_paths.append(conflicts_path)

        path_length_path = graphs_dir / f"{case_spec.case_id}_{suffix}_average_total_distance.png"
        plot_reference_metric(case_spec=case_spec, aggregate=item, classical_getter=lambda a: _per_agent(a.classical_avg_total_path_length, a.agent_number), cyclic_getter=lambda a: _per_agent(a.cyclic_avg_total_path_length, a.agent_number), output_path=path_length_path, y_label="Average total distance per agent", title=f"{case_spec.display_name}: Average Total Distance", lower_is_better=True)
        graph_paths.append(path_length_path)

        turns_path = graphs_dir / f"{case_spec.case_id}_{suffix}_average_turns.png"
        plot_reference_metric(case_spec=case_spec, aggregate=item, classical_getter=lambda a: _per_agent(a.classical_avg_total_turns, a.agent_number), cyclic_getter=lambda a: _per_agent(a.cyclic_avg_total_turns, a.agent_number), output_path=turns_path, y_label="Average turns per agent", title=f"{case_spec.display_name}: Average Turns", lower_is_better=True)
        graph_paths.append(turns_path)

    table_path = graphs_dir / f"{case_spec.case_id}_ecbs_comparison_table.png"
    generate_map_summary_table(case_spec=case_spec, map_aggregates=map_aggregates, output_path=table_path)
    graph_paths.append(table_path)
    return graph_paths
