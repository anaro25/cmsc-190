# dev project layout

## How to run

Edit `dev/master_config.py`, set `to_generate`, and uncomment one or more exact names in `SELECTED_MAP_CONFIGS`, then run:

```bash
python -m dev.main
```

`master_config.py` is the single user-editable file for branch seeds, map size,
agent-number ranges, runtime limits, densities, thresholds, loop settings, start/goal
positioning modes, the global consecutive failed paired sampling limit, the
project-wide `enhanced_CBS` solver toggle, and each branch's `ECBS_suboptimality`.

Results are written under `dev/outputs_main/`, grouped by the selected exact map configurations.

Terminal output from the two main-experiment modes is compartmentalized under:

```text
dev/outputs_main/terminal_logs/
    <numbered_map_category>/
        <numbered_exact_map_configuration>/
            raw_data.log
            visualization.log
```

For example, the static-artificial dispersed/dispersed log is written under
`1_static_artificial/1_static_artificial_dispersed_dispersed/`. Each mode rewrites only
its own log file for that exact map configuration.

When `to_generate = "raw_data"`, the program writes an author-facing inspection file and an independent Results-ready package for each selected exact map configuration:

```text
dev/outputs_main/metrics_data_inspection/
    <numbered_map_category>/
        <numbered_exact_map_configuration>_evaluation.xml

dev/outputs_main/metrics_data/
    data_dictionary.csv
    <numbered_map_category>/
        <numbered_exact_map_configuration>/
            README.txt
            configuration_metadata.csv
            capacity_summary.csv
            capacity_comparison.csv
            capacity_search_tests.csv
            capacity_search_run_records.csv
            capacity_point_run_records.csv
            capacity_point_summary.csv
            paired_run_comparisons.csv
            results_ready_comparisons.csv
            <numbered_exact_map_configuration>_metrics_data.csv
            metrics_package.json
```

`data_dictionary.csv` is the only intentional project-level file in `metrics_data/`. The program does not create cumulative CSVs, a dataset manifest, or a root reader guide. Running or rerunning one map configuration updates only that configuration's folder; other map-configuration packages are not scanned, appended to, or rebuilt. At the start of a raw-data run, obsolete root-level cumulative files from the previous design are deleted automatically.

The exact-configuration `_metrics_data.csv` is the primary compact Results table. Its companion files provide protocol context, actual capacity agent numbers, completion counts, descriptive statistics, paired differences, seeds, statuses, and capacity-search evidence. Blank metric values mean unavailable or not applicable rather than zero, and path statistics use solved runs only.

The separate `<map_config>_raw_data.json` inspection file is no longer generated.

The main experiment no longer has a `to_generate = "graphs"` mode and does not create PNG
metric plots. The complete metrics package is produced during the same raw-data execution that
runs the solver.

When `to_generate = "raw_data"`, the program also saves only the designated successful
trajectories under `dev/outputs_main/frame_by_frame/`:

```text
frame_by_frame/
    <numbered_map_category>/
        <numbered_exact_map_configuration>/
            classical_capacity_<N>_agents/
                classical/final_selected_successful_run/
                    frame_by_frame.pkl
                    metadata.json
            cyclic_capacity_<N>_agents/
                cyclic/final_selected_successful_run/
                    frame_by_frame.pkl
                    metadata.json
            manifest.json
```

The classical package is the final retained successful classical run at classical capacity.
The cyclic package is the final retained successful cyclic run at cyclic capacity. Intermediate
capacity-search runs and cross-mapping comparative runs are not stored here. When
`to_generate = "visualization"`, Pillow output is generated directly from these packages;
the numerical metrics package is not used for visualization generation.

## Current orchestration path

The active experiment driver is the generalized study runner:

- `dev/master_config.py`
- `dev/main.py`
- `dev/experiments/generalized_study.py` (thin compatibility wrapper)
- `dev/experiments/study/`

The `study` package is split by responsibility:

- `models.py` — run/config/result dataclasses
- `preparation.py` — build static and dynamic run contexts
- `runtime.py` — solver execution, CBS/ECBS dispatch, seeds, and run record construction
- `aggregation.py` — condition-level summaries
- `io_utils.py` — structured output writing and experiment logging
- `logging_utils.py` — console/file log formatting
- `metrics_data_store.py` — Results-ready per-configuration packages, reader guides, and the project-level data dictionary
- `orchestrator.py` — capacity search, paired capacity-point evaluation, and branch execution flow

## Current branches

The configured main-experiment branch set now contains 32 exact map configurations. Select exact configurations in `SELECTED_MAP_CONFIGS`; the active `to_generate` mode applies only to those selected configurations.

Traditional MAPF exact configurations are generated from Artificial/Port × Static/Dynamic × Dispersed/Clustered agents × Dispersed/Clustered targets.

Campus Crowd Simulation exact configurations are generated from Campus Area 1/2 × Static/Dynamic × Dispersed/Single-cell agents × Dispersed/Single-cell targets.

## Capacity-search protocol

The main experiment now uses limited binary-search capacity testing instead of incrementing through an agent-number range. For each layout configuration, classical and cyclic mapping are searched independently from 1 to 255 agents. A tested agent number passes when at least 1 out of up to 5 valid solver attempts finishes within the 30-second limit. The search starts at 128. If no passing agent number has been found yet, the search may continue descending to smaller left-child values below the normal depth limit. After the first pass is found, the search follows at most 3 additional downward child moves, so difficult configurations can still test values below 16 without allowing an unbounded search. Setup-failed or unsolvable initial conditions are regenerated, with a safety cap of 5 generation attempts per solver attempt.

The highest passed tested value along the limited traversal is reported as the mapping capacity for that configuration.

## Global solver toggle

`master_config.py` now contains one project-wide boolean:

```python
enhanced_CBS = True
```

- `False` uses vanilla CBS
- `True` uses ECBS

This is intentionally global rather than branch-specific, so the whole run uses one solver family consistently. The ECBS mode now reads `ECBS_suboptimality` from the currently selected branch config, so each branch can keep its own editable suboptimality value in `master_config.py`.

## Current counted-run protocol

During paired sampling, the terminal now prints progress lines such as
`Paired sampling attempt 4 ongoing...` so long jointly viable searches are visible while they run.
Startup progress is also logged during shared dynamic-map preparation, including image loading, static preprocessing, dynamic patch-bank generation, mapped-loop construction, and any fallback activation.

For each planned agent number in the selected branch:

1. The study generates one run configuration at a time.
2. Classical and cyclic are both solved on that same configuration.
3. The configuration is retained only if both mappings end in a counted result:
   - `successful`
   - `unfinished`
4. If either mapping is `unsolvable`, the configuration is discarded and a newly sampled
   configuration is tried.
5. The updated main experiment now writes text-only result logs under
   `dev/outputs_main/metrics_data_inspection/`.
6. The path metric is now total path length over all agents, not average path length.

The per-run runtime limit, 1-out-of-5 pass rule, and post-first-success binary-search downward-move limit come from `master_config.py`.

## Capacity comparison outputs

For each selected exact map configuration, the program processes that configuration directly. Each configuration receives an `_evaluation.xml` inspection log and its own Results-ready metrics package. The compact `_metrics_data.csv` reports both mappings at the classical-origin and cyclic-origin capacity points, including actual agent numbers, outcome counts, means, changes, percentage changes, and interpretation flags. Companion CSVs preserve the capacity-search steps, retained attempts, capacity-point run records, paired same-initial-condition comparisons, descriptive statistics, solver/protocol metadata, and valid path-value counts.

No project-level result file combines multiple map configurations. This keeps every configuration independent when different subsets are selected across program runs.

## Supplementary reference comparison

A separate Tang-inspired reference-comparison workflow has been added without changing the main experiment workflow. To use it, edit `dev/main.py` and select the reference experiment family:

```python
SELECTED_EXPERIMENT = "ref_comparison"
# SELECTED_EXPERIMENT = "main_experiment"
```

The reference workflow is configured in `dev/master_config_ref_comparison.py`, not in the main `master_config.py`.

The available reference selectors are:

```python
# SELECTED_PORT_EXPERIMENT = "single_agent"
SELECTED_PORT_EXPERIMENT = "multi_agent"
```

The reference-comparison cyclic map has local toggles for optional final transition-processing steps:

```python
REMOVE_EXTRA_TRANSITIONS = False
ADD_TRANSITIONS_BETWEEN_FREE_SPACES = False
```

Set `REMOVE_EXTRA_TRANSITIONS` to `False` to skip only the redundant-transition elimination step while still preserving required connectivity restoration. Set `ADD_TRANSITIONS_BETWEEN_FREE_SPACES` to `True` to add a bidirectional transition between every adjacent pair of free cells after the cyclic-mapping cleanup steps. These toggles are only used by the reference-comparison workflow; the main experiment keeps its existing cyclic-mapping behavior.

Reference outputs are written under `dev/outputs_ref_comparison/<case_id>/`, with persisted numerical raw data under `dev/outputs_ref_comparison/raw_mapf_files/<case_id>/`. Selected trajectories are stored separately under `dev/outputs_ref_comparison/frame_by_frame/single_agent_pf/` and `dev/outputs_ref_comparison/frame_by_frame/multi_agent_pf/`. For each of the three maps, the single-agent case stores the first successful timing repetition for classical and cyclic. The multi-agent case stores the first successful timing repetition for both mappings from the final comparison at the discovered classical capacity. Capacity-search trials are not stored as frame-by-frame runs. `to_generate = "visualization"` reads these trajectory packages directly. The reference comparison now uses three separate 50x50 port maps from `dev/inputs/reference_port_maps/`: `port_map_1.png`, `port_map_2.png`, and `port_map_3.png`. Their pixel meanings are: black (`#000000`) = normal obstacle, white (`#ffffff`) = free space, and light red (`#e8787a`) = invisible obstacle. Invisible obstacles are blocked logically during planning/solving but rendered as ordinary free space in MAPF visualizations; transition rendering is unchanged. The old orientation-based variants are no longer generated. The single-agent case compares traditional A* + classical mapping versus traditional A* + cyclic mapping on all three maps, using the lower-left-most free cell as the start and the upper-right-most free cell as the goal for each map. For each map and mapping, `SINGLE_AGENT_TIMING_REPETITIONS = 5` repeats the same deterministic A* setup five times and stores the average as `time_computation_halted_seconds`; path, node, turn, and distance metrics are taken from the same unchanged setup. The multi-agent case also runs all three maps, but it no longer uses fixed per-map agent numbers. For each map, it performs a limited binary search over 1 to 255 agents and searches only the temporary pairwise classical capacity. A candidate is tested once and passes only when classical solves and cyclic also solves with both lower halted time and fewer conflicts on the exact same deterministic release schedule. The search starts at 128, continues downward until a first pass is found, and then allows at most three additional binary-search child moves. At the discovered classical capacity, both mappings are run with `MULTI_AGENT_TIMING_REPETITIONS = 3`; the stored runtime is the average of those three executions, while conflict, turn, and distance values come from the representative deterministic solution. No separate cyclic-capacity search is performed. When `to_generate = "graphs"`, each selected reference case writes a matplotlib-formatted summary table beside the generated graphs. The table has three sections, one for each map number. Single-agent tables report Running time, Number of nodes, Number of turns, and Total distance. Multi-agent tables report Running time, Average number of conflicts, Average number of turns, and Average total distance. In both tables, the mapping headers are `Traditional A* with Classical Mapping` and `With Cyclic Mapping`, and the final column is `Percent Reduction/Gain`, where negative values mean the cyclic value is lower than the classical value and positive values mean the cyclic value is higher. The graph outputs are metric-level summaries across maps: each metric has one graph with x-axis points for Map 1, Map 2, Map 3, and Average. Only the three map-specific points are connected by the horizontal trend line; the Average point is plotted as a standalone summary marker. Any sibling images containing manually colored path markings remain in the input directory for record-keeping, but the reference workflow does not read or import those markings. When `to_generate = "visualization"`, the reference-comparison visualizer selects successful runs independently per map number and mapping, so one classical/cyclic visualization set is produced for each available port map rather than only the last map overall. The visualization step also logs selection, per-map rendering progress, frame-writing stages, and final frame counts. All reference-comparison graphs set the vertical axis from the actually plotted values with a small padding margin, making close values easier to distinguish; the 30-second runtime-limit line is shown only on runtime graphs where at least one plotted value reaches that limit.
