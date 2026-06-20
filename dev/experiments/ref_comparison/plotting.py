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

    if case_spec.experiment_mode == "single_agent":
        classical_label = "Traditional A* + Classical"
        cyclic_label = "Traditional A* + Cyclic"
    else:
        classical_label = "ECBS + Classical"
        cyclic_label = "ECBS + Cyclic"

    axes.scatter([x_value], [classical_value], marker="s", s=MARKER_SIZE, color=CLASSICAL_COLOR, edgecolors="black", linewidths=0.8, label=classical_label, zorder=3)
    axes.scatter([x_value], [cyclic_value], marker="o", s=MARKER_SIZE, color=CYCLIC_COLOR, edgecolors="black", linewidths=0.8, label=cyclic_label, zorder=3)
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


def generate_single_agent_summary_table(
    *,
    case_spec: RefCaseSpec,
    aggregate: RefConditionAggregate,
    output_path: Path,
) -> None:
    """Create the single-agent A* comparison table as a graph sibling file."""
    map_size_label = f"{case_spec.map_size}×{case_spec.map_size}"

    # The user-facing table calls this row "Number of nodes". In the stored
    # reference-comparison records, this intentionally reuses the same metric
    # slot as "num_conflicts_detected_at_halt". Single-agent A* has no MAPF
    # conflicts, so missing values are displayed as 0 instead of breaking the
    # table generation.
    classical_nodes = _safe_metric(aggregate.classical_avg_conflicts_at_halt, default=0.0)
    cyclic_nodes = _safe_metric(aggregate.cyclic_avg_conflicts_at_halt, default=0.0)

    rows = [
        [
            map_size_label,
            "Running time/s",
            _display_metric(aggregate.classical_avg_time_computation_halted, time_like=True),
            _display_metric(aggregate.cyclic_avg_time_computation_halted, time_like=True),
            _reduced_proportion(
                aggregate.classical_avg_time_computation_halted,
                aggregate.cyclic_avg_time_computation_halted,
            ),
        ],
        [
            "",
            "Number of nodes",
            _display_metric(classical_nodes, integer_like=True),
            _display_metric(cyclic_nodes, integer_like=True),
            _reduced_proportion(classical_nodes, cyclic_nodes),
        ],
        [
            "",
            "Number of turns",
            _display_metric(aggregate.classical_avg_total_turns, integer_like=True),
            _display_metric(aggregate.cyclic_avg_total_turns, integer_like=True),
            _reduced_proportion(aggregate.classical_avg_total_turns, aggregate.cyclic_avg_total_turns),
        ],
        [
            "",
            "Total distance/m",
            _display_metric(aggregate.classical_avg_total_path_length),
            _display_metric(aggregate.cyclic_avg_total_path_length),
            _reduced_proportion(
                aggregate.classical_avg_total_path_length,
                aggregate.cyclic_avg_total_path_length,
            ),
        ],
    ]

    columns = [
        "Map size",
        "Path parameters",
        "Traditional\nA-star",
        "With Cyclic\nMapping",
        "Reduced\nproportion",
    ]

    figure, axes = plt.subplots(figsize=(9, 4.2))
    axes.axis("off")

    table = axes.table(
        cellText=rows,
        colLabels=columns,
        colWidths=[0.16, 0.34, 0.17, 0.17, 0.16],
        cellLoc="center",
        colLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.45)

    total_rows = len(rows)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("black")
        cell.set_linewidth(0.6)
        if row == 0:
            cell.set_text_props(weight="normal")
            cell.set_height(0.12)
            cell.visible_edges = "BT"
        elif row == total_rows:
            cell.set_height(0.09)
            cell.visible_edges = "B"
        else:
            cell.set_height(0.09)
            cell.visible_edges = ""

    # Center the map-size label across the four metric rows by placing it on
    # one middle row and leaving the other cells visually empty.
    for row in range(1, total_rows + 1):
        table[(row, 0)].get_text().set_text("")
    table[(2, 0)].get_text().set_text(map_size_label)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
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

    if case_spec.experiment_mode == "single_agent":
        table_path = graphs_dir / f"{case_spec.case_id}_astar_comparison_table.png"
        generate_single_agent_summary_table(
            case_spec=case_spec,
            aggregate=aggregate,
            output_path=table_path,
        )
        graph_paths.append(table_path)

    return graph_paths
