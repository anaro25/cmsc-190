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

The configured main-experiment branch set now contains 8 map categories. Selecting one category runs all documented layout configurations for that category.

Traditional MAPF:

- `static_artificial` — artificial static-obstacle map
- `dynamic_artificial` — artificial map with generated dynamic obstacles
- `static_port` — static image-based port map
- `dynamic_port` — dynamic image-based port map

Campus Crowd Simulation:

- `static_campus_area_1` — static campus area 1
- `dynamic_campus_area_1` — dynamic campus area 1
- `static_campus_area_2` — static campus area 2
- `dynamic_campus_area_2` — dynamic campus area 2

## Capacity-search protocol

The main experiment now uses binary-search capacity testing instead of incrementing through an agent-number range. For each layout configuration, classical and cyclic mapping are searched independently from 1 to 255 agents. A tested agent number passes when at least 3 out of up to 5 valid solver attempts finish within the 30-second limit. Setup-failed or unsolvable initial conditions are regenerated, with a safety cap of 50 generation attempts per solver attempt.

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
5. The updated main experiment now writes text-only result logs under
   `dev/outputs_main_experiment/data_log/`.
6. The path metric is now total path length over all agents, not average path length.

The per-run runtime limit and capacity-search constants come from `master_config.py`.

## Capacity comparison outputs

For each selected map category, the program runs every documented layout configuration.
Each configuration receives its own `_evaluation.xml` text log and a matching
`_raw_data.json` file. The log contains the classical capacity point, the cyclic
capacity point, paired comparative runs at both points, and condensed evaluations
for halted time and conflicts.

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

Reference outputs are written under `dev/outputs_ref_comparison/<case_id>/`, with persisted raw data under `dev/outputs_ref_comparison/raw_mapf_files/<case_id>/`. The reference comparison now uses three separate 50x50 port maps from `dev/inputs/reference_port_maps/`: `port_map_1.png`, `port_map_2.png`, and `port_map_3.png`. Their pixel meanings are: black (`#000000`) = normal obstacle, white (`#ffffff`) = free space, and light red (`#e8787a`) = invisible obstacle. Invisible obstacles are blocked logically during planning/solving but rendered as ordinary free space in MAPF visualizations; transition rendering is unchanged. The old orientation-based variants are no longer generated. The single-agent case compares traditional A* + classical mapping versus traditional A* + cyclic mapping on all three maps, using the lower-left-most free cell as the start and the upper-right-most free cell as the goal for each map. For each map and mapping, `SINGLE_AGENT_TIMING_REPETITIONS = 5` repeats the same deterministic A* setup five times and stores the average as `time_computation_halted_seconds`; path, node, turn, and distance metrics are taken from the same unchanged setup. The multi-agent case also runs all three maps and uses `MULTI_AGENT_TIMING_REPETITIONS = 3`. Its agent counts are selected per port map in `MULTI_AGENT_REFERENCE_PORT_MAP_AGENT_NUMBERS`, for example `{1: 10, 2: 10, 3: 10}` means map 1, map 2, and map 3 each use 10 agents. Each map keeps the same deterministic release/spawn rule and stores the average ECBS runtime per mapping; conflict, turn, and distance values are taken from the representative deterministic solution. The temporary individual cyclic-faster filter is disabled for both single-agent and multi-agent reference cases. When `to_generate = "graphs"`, each selected reference case writes a matplotlib-formatted summary table beside the generated graphs. The table has three sections, one for each map number. Single-agent tables report Running time, Number of nodes, Number of turns, and Total distance. Multi-agent tables report Running time, Average number of conflicts, Average number of turns, and Average total distance. In both tables, the mapping headers are `Traditional A* with Classical Mapping` and `With Cyclic Mapping`, and the final column is `Percent Reduction/Gain`, where negative values mean the cyclic value is lower than the classical value and positive values mean the cyclic value is higher. The graph outputs are metric-level summaries across maps: each metric has one graph with x-axis points for Map 1, Map 2, Map 3, and Average. Only the three map-specific points are connected by the horizontal trend line; the Average point is plotted as a standalone summary marker. Any sibling images containing manually colored path markings remain in the input directory for record-keeping, but the reference workflow does not read or import those markings. When `to_generate = "visualization"`, the reference-comparison visualizer selects successful runs independently per map number and mapping, so one classical/cyclic visualization set is produced for each available port map rather than only the last map overall. The visualization step also logs selection, per-map rendering progress, frame-writing stages, and final frame counts. All reference-comparison and main-experiment graphs set the vertical axis from the actually plotted values with a small padding margin, making close values easier to distinguish; the 30-second runtime-limit line is shown only on runtime graphs where at least one plotted value reaches that limit.
