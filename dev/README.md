# dev project layout

## How to run

Edit `dev/master_config.py` and leave exactly one `MAP_TYPE` uncommented, then run:

```bash
python -m dev.main
```

`master_config.py` is the single user-editable file for branch seeds, map size,
agent-number ranges, runtime limits, densities, thresholds, loop settings, start/goal
positioning modes, the global consecutive failed paired sampling limit, the
project-wide `enhanced_CBS` solver toggle, and each branch's `ECBS_suboptimality`.

Results are written under `dev/outputs/<map_type>/`, and persisted solver-stage raw data is stored under `dev/outputs/raw_mapf_files/<map_type>/`.

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
- `plotting.py` — PNG graph generation
- `io_utils.py` — structured output writing and experiment logging
- `logging_utils.py` — console/file log formatting
- `orchestrator.py` — jointly viable paired sampling, early stopping, and branch execution flow

## Current branches

The configured branch set now contains 9 map types.

Traditional MAPF:

- `static_artificial` — dispersed starts to dispersed targets
- `static_port` — dispersed starts to clustered targets
- `dynamic_port` — clustered starts to clustered targets

Campus Crowd Simulation:

- `static_campus_area_1` — dispersed starts to one shared single target
- `dynamic_campus_area_1` — clustered starts to one shared single target
- `static_campus_area_2` — dispersed starts to one shared single target
- `dynamic_campus_area_2` — clustered starts to one shared single target
- `static_campus_area_3` — dispersed starts to one shared single target
- `dynamic_campus_area_3` — clustered starts to one shared single target

## Agent-number progression

Each branch now uses:

```python
agent_number_range = (start_agent_number, max_agent_number, step_size)
```

Example:

```python
(8, 40, 4) -> [8, 12, 16, 20, 24, 28, 32, 36, 40]
```

The generated list is the planned progression only. A branch may stop earlier if one
of the stopping rules triggers.

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
5. A condition is reported only if it reaches the full counted-pair quota without hitting
   an early-stop rule.
6. Aggregates use:
   - `time_computation_halted_seconds` over retained counted pairs
   - `num_conflicts_detected_at_halt` over retained counted pairs
   - `average_path_length` over successful runs only for all branches, including the dynamic branches

The per-branch runtime limit and counted-run requirement both come from `master_config.py`.

## Early stopping rules

The branch stops before higher agent numbers when either rule triggers at the current
condition:

1. **Cyclic unfinished runs exceed cyclic successful runs** within the retained counted
   pairs for that condition.
   - Example trigger patterns at `n = 5`: `5 > 0`, `4 > 1`, `3 > 2`
   - The entire current condition is discarded.
2. **A user-defined number of consecutive failed paired sampling attempts** occur while trying to build the
   current condition.
   - The shared limit is configured by
     `CONSECUTIVE_FAILED_PAIRED_SAMPLING_ATTEMPTS_LIMIT` in `dev/master_config.py`.
   - In this project, that means consecutive sampled configurations were rejected by
     the joint viability screen because at least one mapping classified the configuration as
     `unsolvable`.
   - The entire current condition is discarded.

When a stop rule triggers, only the earlier accepted conditions remain in the reported
outputs. The stop reason is written to `metadata/branch_stop_summary.json`.

There is also an internal large safeguard on total paired sampling attempts to prevent
pathological infinite loops. It remains only a protective implementation detail.

## Other important packages

- `dev/experiments/branch_specs.py` — branch-level experiment definitions built from `master_config.py`
- `dev/mapf/` — CBS/ECBS solvers, metrics, and MAPF execution helpers
- `dev/maps/` — map construction and mapping transforms
- `dev/navigation/` — graph/navigation helpers over composite grids
- `dev/inputs/` — image-based inputs for dynamic and static campus/image branches
- `dev/core/` — composite-grid primitives

## Notes

- The project now uses explicit `start_distribution_mode` and `goal_distribution_mode` settings instead of the older shared-goal campus toggle.
- `goal_distribution_mode` can now be `dispersed`, `clustered`, or `single`. `single` is target-only and means all agents share one literal target cell where they disappear after arrival.
- In campus branches, `single` targets are sampled only from the dark marker cells inside the selected target zone. The dark blue, dark green, and dark red marker pixels still count as zone cells for traversal and ordinary spawn masks.
- The campus branches preserve their semantic-color meanings: zone colors are traversable and spawnable, white walkways are traversable but not spawnable, and gray regions are non-traversable for the solver. During Pillow visualization generation, gray campus cells are reconstructed from the current semantic image and rendered through a temporary render-only free-space override so they appear as ordinary white open cells without changing solver behavior, while already persisted raw MAPF data remains reusable.
- Port and campus images now support both static and dynamic map types. The static variants use the same source image without dynamic obstacles, while the dynamic variants add generated moving obstacles.
- `static_port` uses dispersed starts and clustered targets. `dynamic_port` uses clustered starts and clustered targets.
- Every static campus branch uses dispersed starts in one campus zone and one shared single target cell in a different zone. Every dynamic campus branch uses clustered starts in one campus zone and one shared single target cell in a different zone.
- The assignment sampler now treats dispersed, clustered, and single target modes differently: dispersed sets keep 8-neighbor separation within the set, clustered sets follow the global `compact_clustering` switch in `master_config.py`, and single targets use many-to-one assignment.
- When `compact_clustering=True`, clustered sets are sampled as directly adjacent 8-neighbor-connected groups.
- When `compact_clustering=False`, clustered sets remain one cluster but keep one empty cell of separation in all 8 directions.
- Presentation outputs now keep only the latest regenerated version per output family. Logs and regenerated artifacts overwrite the prior copy instead of creating new `execution_...` folders.
- Persisted branch-local raw MAPF storage now lives under `dev/outputs/raw_mapf_files/<map_type>/`. Older branch roots from `dev/raw_mapf_data/<map_type>/` or `dev/raw_mapf_files/<map_type>/` are migrated automatically when the branch is loaded again.
- Pillow-rendered run images are generated selectively in the generalized study flow. Each branch now has both `num_last_runs_to_visualize_jointly_successful` and `num_last_runs_to_visualize_independently_successful` in `master_config.py`, and a visualization-only execution now generates both folder variants automatically under `dev/outputs/<map_type>/visualizations/`.
- Branch metadata and per-run records now also capture the active solver family (`CBS` or `ECBS`) so output files remain interpretable after solver-toggle changes.

- Image inputs now use `dev/inputs/dynamic_port/port_map.png`, `dev/inputs/campus_area_1.png`, `dev/inputs/campus_area_2.png`, and `dev/inputs/campus_area_3.png`.


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

Reference outputs are written under `dev/outputs_ref_comparison/<case_id>/`, with persisted raw data under `dev/outputs_ref_comparison/raw_mapf_files/<case_id>/`. The reference comparison now uses three separate 50x50 port maps from `dev/inputs/reference_port_maps/`: `port_map_1.png`, `port_map_2.png`, and `port_map_3.png`. Their pixel meanings are: black (`#000000`) = normal obstacle, white (`#ffffff`) = free space, and light red (`#e8787a`) = invisible obstacle. Invisible obstacles are blocked logically during planning/solving but rendered as ordinary free space in MAPF visualizations; transition rendering is unchanged. The old orientation-based variants are no longer generated. The single-agent case compares traditional A* + classical mapping versus traditional A* + cyclic mapping on all three maps, using the lower-left-most free cell as the start and the upper-right-most free cell as the goal for each map. For each map and mapping, `SINGLE_AGENT_TIMING_REPETITIONS = 5` repeats the same deterministic A* setup five times and stores the average as `time_computation_halted_seconds`; path, node, turn, and distance metrics are taken from the same unchanged setup. The multi-agent case also runs all three maps and uses `MULTI_AGENT_TIMING_REPETITIONS = 3`. Its agent counts are selected per port map in `MULTI_AGENT_REFERENCE_PORT_MAP_AGENT_NUMBERS`, for example `{1: 10, 2: 10, 3: 10}` means map 1, map 2, and map 3 each use 10 agents. Each map keeps the same deterministic release/spawn rule and stores the average ECBS runtime per mapping; conflict, turn, and distance values are taken from the representative deterministic solution. The temporary individual cyclic-faster filter is disabled for both single-agent and multi-agent reference cases. When `to_generate = "graphs_and_data"`, each selected reference case writes a matplotlib-formatted summary table beside the generated graphs. The table has three sections, one for each map number. Single-agent tables report Running time, Number of nodes, Number of turns, and Total distance. Multi-agent tables report Running time, Average number of conflicts, Average number of turns, and Average total distance. In both tables, the mapping headers are `Traditional A* with Classical Mapping` and `With Cyclic Mapping`, and the final column is `Percent Reduction/Gain`, where negative values mean the cyclic value is lower than the classical value and positive values mean the cyclic value is higher. The graph outputs are metric-level summaries across maps: each metric has one graph with x-axis points for Map 1, Map 2, Map 3, and Average. Only the three map-specific points are connected by the horizontal trend line; the Average point is plotted as a standalone summary marker. Any sibling images containing manually colored path markings remain in the input directory for record-keeping, but the reference workflow does not read or import those markings. When `to_generate = "visualization"`, the reference-comparison visualizer selects successful runs independently per map number and mapping, so one classical/cyclic visualization set is produced for each available port map rather than only the last map overall. The visualization step also logs selection, per-map rendering progress, frame-writing stages, and final frame counts. All reference-comparison and main-experiment graphs set the vertical axis from the actually plotted values with a small padding margin, making close values easier to distinguish; the 30-second runtime-limit line is shown only on runtime graphs where at least one plotted value reaches that limit.
