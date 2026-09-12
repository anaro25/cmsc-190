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

Results are written under `dev/outputs_main/`, with each exact map configuration owning all of its artifact folders:

```text
dev/outputs_main/
    <numbered_map_category>/
        <numbered_exact_map_configuration>/
            frame_by_frame/
            metrics_data/
            metrics_data_inspection/
            terminal_logs/
            visualization/
    project_level_files/
        data_dictionary.csv
        readme.txt
```

The program generates `data_dictionary.csv` during a raw-data run. It does not generate or rewrite `readme.txt`; that file is reserved for manual project-level notes. At startup, the program automatically migrates the previous artifact-first layout into this map-config-first structure. The migration is idempotent and refuses to overwrite different files when both layouts contain conflicting copies.

Terminal output from the two main-experiment modes is written inside the selected exact configuration:

```text
dev/outputs_main/
    <numbered_map_category>/
        <numbered_exact_map_configuration>/
            terminal_logs/
                raw_data.log
                visualization.log
```

Each mode rewrites only its own log file for that exact map configuration.

When `to_generate = "raw_data"`, the program writes an author-facing inspection file and an independent Results-ready package inside the same exact configuration:

```text
dev/outputs_main/
    <numbered_map_category>/
        <numbered_exact_map_configuration>/
            metrics_data_inspection/
                <numbered_exact_map_configuration>_evaluation.xml
            metrics_data/
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

The exact-configuration `_metrics_data.csv` is the primary compact Results table. Its companion files provide protocol context, actual capacity agent numbers, completion counts, descriptive statistics, paired differences, seeds, statuses, and capacity-search evidence. Blank metric values mean unavailable or not applicable rather than zero, and path statistics use solved runs only.

The separate `<map_config>_raw_data.json` inspection file is no longer generated.

The main experiment no longer has a `to_generate = "graphs"` mode and does not create PNG metric plots. The complete metrics package is produced during the same raw-data execution that runs the solver.

When `to_generate = "raw_data"`, the program also saves only the designated successful trajectories inside the exact configuration's `frame_by_frame/` folder:

```text
dev/outputs_main/
    <numbered_map_category>/
        <numbered_exact_map_configuration>/
            frame_by_frame/
                shared_context/
                    shared_context.pkl
                    metadata.json
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

The classical package is the final retained successful classical run at classical capacity. The cyclic package is the final retained successful cyclic run at cyclic capacity. Intermediate capacity-search runs and cross-mapping comparative runs are not stored here. When `to_generate = "visualization"`, Pillow output is generated directly from these packages; the numerical metrics package is not used for visualization generation. The rendered files are written beside the other artifacts under the same exact configuration's `visualization/` folder.

Before a selected configuration begins a new `raw_data` run, the program deletes that configuration's existing `visualization/` folder and stale `terminal_logs/visualization.log`. This prevents older visualizations from being mistaken for output based on the newly regenerated raw data. Unselected configurations are not affected.

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

The main experiment uses limited binary-search capacity testing instead of incrementing through an agent-number range. For each layout configuration, classical and cyclic mapping are searched independently over `1..F`, where `F` is the number of traversable cells in the final binary base map. Every tested agent number uses five run slots and passes only when at least three of the five runs solve within the 30-second limit. Setup-generation failures remain failed run slots rather than evidence of solver success.

The highest passed tested value along the traversal is reported as that mapping's capacity. Classical capacity depends only on classical success, and cyclic capacity depends only on cyclic success; cyclic superiority is not part of the capacity criterion.

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
   the selected exact configuration's `metrics_data_inspection/` folder.
6. The path metric is now total path length over all agents, not average path length.

The per-run runtime limit, 3-out-of-5 pass rule, and post-first-success binary-search downward-move limit come from `master_config.py`.

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

The reference comparison uses the same cyclic-map post-processing variant as the main experiment:

```python
REMOVE_EXTRA_TRANSITIONS = True
ADD_TRANSITIONS_BETWEEN_FREE_SPACES = False
```

The reference workflow therefore reduces redundant bidirectional transitions before restoring required connectivity, just like the main experiment. No reference-only post-processing variant is used.

Reference outputs are written under `dev/outputs_ref_comparison/<case_id>/`, with persisted numerical raw data under `dev/outputs_ref_comparison/raw_mapf_files/<case_id>/`. Selected trajectories are stored separately under `dev/outputs_ref_comparison/frame_by_frame/single_agent_pf/` and `dev/outputs_ref_comparison/frame_by_frame/multi_agent_pf/`. For each of the three maps, the single-agent case stores the first successful timing repetition for classical and cyclic. The multi-agent case stores one final successful trajectory for classical at the discovered classical capacity and one for cyclic at the discovered cyclic capacity. Capacity-search trials are not stored as frame-by-frame runs. `to_generate = "visualization"` reads these trajectory packages directly.

The reference comparison uses three separate 50x50 port maps from `dev/inputs/reference_port_maps/`: `port_map_1.png`, `port_map_2.png`, and `port_map_3.png`. The bundled assets are normalized to ordinary black (`#000000`) obstacle pixels and white (`#ffffff`) free-space pixels only. The former light-red invisible-obstacle cells have been converted to ordinary white/free cells, and the special invisible-obstacle pathfinding/visualization rule has been removed. Internally, the reference binary matrix follows the manuscript convention: `1 = traversable/free` and `0 = blocked/obstacle`.

The single-agent case compares traditional A* + classical mapping versus traditional A* + cyclic mapping on all three maps, using the lower-left-most free cell as the start and the upper-right-most free cell as the goal for each map. For each map and mapping, `SINGLE_AGENT_TIMING_REPETITIONS = 5` repeats the same deterministic A* setup five times and stores the average as `time_computation_halted_seconds`; path, node, turn, and distance metrics are taken from the same unchanged setup. The reference solver uses Manhattan guidance (`SHARED_TRUE_STATIC_SHORTEST_PATH_DISTANCE = False`), and crowd-spreading/cohesion guidance is not part of the reference experiment.

For the multi-agent case, each map gets two independent capacity searches: one for classical mapping and one for cyclic mapping. The candidate interval is `1..F`, where `F` is the number of traversable cells in that normalized map. Every tested agent number is evaluated in exactly five run slots and passes only when at least three runs return valid solutions within the 60-second limit. Capacity depends only on the tested mapping's own success; cyclic superiority in runtime or conflicts is not part of the rule. The binary search continues until the numerical interval is resolved, with no reference-only post-success move limit. Afterward, classical is measured at the discovered classical capacity and cyclic at the discovered cyclic capacity. Each final mapping result uses `MULTI_AGENT_TIMING_REPETITIONS = 3`; the stored runtime is the average of those three executions, while conflict, turn, and distance values come from the representative deterministic solution. The outward comparison still produces the same metric set and the same number of map-level classical/cyclic result entries as before.

When `to_generate = "graphs"`, each selected reference case writes a matplotlib-formatted summary table beside the generated graphs. The table has three sections, one for each map number. Single-agent tables report Running time, Number of nodes, Number of turns, and Total distance. Multi-agent tables report Running time, Average number of conflicts, Average number of turns, and Average total distance. In the multi-agent case, per-agent quantities use the corresponding mapping's own discovered capacity as the divisor. In both tables, the mapping headers are `Traditional A* with Classical Mapping` and `With Cyclic Mapping`, and the final column is `Percent Reduction/Gain`, where negative values mean the cyclic value is lower than the classical value and positive values mean the cyclic value is higher. The graph outputs are metric-level summaries across maps: each metric has one graph with x-axis points for Map 1, Map 2, Map 3, and Average. Only the three map-specific points are connected by the horizontal trend line; the Average point is plotted as a standalone summary marker. Any sibling images containing manually colored path markings remain in the input directory for record-keeping, but the reference workflow does not read or import those markings. When `to_generate = "visualization"`, the reference-comparison visualizer selects successful runs independently per map number and mapping, so one classical/cyclic visualization set is produced for each available port map rather than only the last map overall. The visualization step also logs selection, per-map rendering progress, frame-writing stages, and final frame counts.
