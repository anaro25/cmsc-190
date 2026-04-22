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

The configured branch set is now:

- `static_artificial`
- `static_campus_area_1`
- `dynamic_port`
- `dynamic_campus_area_2`

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
- All current branches remain one-to-one MAPF setups. The experiment varies spatial placement, not assignment cardinality.
- The campus branches preserve their semantic-color meanings: zone colors are traversable and spawnable, white walkways are traversable but not spawnable, and gray regions are non-traversable for the solver. During Pillow visualization generation, gray campus cells are reconstructed from the current semantic image and rendered through a temporary render-only free-space override so they appear as ordinary white open cells without changing solver behavior, while already persisted raw MAPF data remains reusable.
- `static_campus_area_1` now uses campus area 1 as the static branch, with dispersed starts in one zone and clustered goals in the other zone.
- `dynamic_port` now uses clustered starts and dispersed goals.
- `dynamic_campus_area_2` now uses campus area 2 as the dynamic campus branch, with clustered starts and clustered goals forced into different campus zones.
- The assignment sampler now treats dispersed sets and clustered sets differently: dispersed sets keep 8-neighbor separation within the set, while clustered sets follow the global `compact_clustering` switch in `master_config.py`.
- When `compact_clustering=True`, clustered sets are sampled as directly adjacent 8-neighbor-connected groups.
- When `compact_clustering=False`, clustered sets remain one cluster but keep one empty cell of separation in all 8 directions.
- Presentation outputs now keep only the latest regenerated version per output family. Logs and regenerated artifacts overwrite the prior copy instead of creating new `execution_...` folders.
- Persisted branch-local raw MAPF storage now lives under `dev/outputs/raw_mapf_files/<map_type>/`. Older branch roots from `dev/raw_mapf_data/<map_type>/` or `dev/raw_mapf_files/<map_type>/` are migrated automatically when the branch is loaded again.
- Pillow-rendered run images are generated selectively in the generalized study flow. Each branch now has both `num_last_runs_to_visualize_jointly_successful` and `num_last_runs_to_visualize_independently_successful` in `master_config.py`, and a visualization-only execution now generates both folder variants automatically under `dev/outputs/<map_type>/visualizations/`.
- Branch metadata and per-run records now also capture the active solver family (`CBS` or `ECBS`) so output files remain interpretable after solver-toggle changes.

- `static_campus_area_1` and `dynamic_campus_area_2` now each expose a branch-level `narrow_lanes` boolean in `master_config.py`, which switches their campus input between the `*_narrow_lanes.png` and `*_wide_lanes.png` variants.
