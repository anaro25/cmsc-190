# dev project layout

## How to run

Edit `dev/master_config.py` and leave exactly one `MAP_TYPE` uncommented, then run:

```bash
python -m dev.main
```

`master_config.py` is the single user-editable file for branch seeds, map size,
agent-number ranges, runtime limits, densities, thresholds, and loop settings.

Results are written under `dev/outputs/<map_type>/`.

## Current orchestration path

The active experiment driver is the generalized study runner:

- `dev/master_config.py`
- `dev/main.py`
- `dev/experiments/generalized_study.py` (thin compatibility wrapper)
- `dev/experiments/study/`

The `study` package is split by responsibility:

- `models.py` — run/config/result dataclasses
- `preparation.py` — build static and dynamic run contexts
- `runtime.py` — solver execution, seeds, and run record construction
- `aggregation.py` — condition-level summaries
- `plotting.py` — PNG graph generation
- `io_utils.py` — structured output writing and experiment logging
- `logging_utils.py` — console/file log formatting
- `orchestrator.py` — jointly viable paired sampling, early stopping, and branch execution flow

## Agent-number progression

Each branch now uses:

```python
agent_number_range = (start_agent_number, step_size, max_agent_number)
```

Example:

```python
(8, 4, 40) -> [8, 12, 16, 20, 24, 28, 32, 36, 40]
```

The generated list is the planned progression only. A branch may stop earlier if one
of the stopping rules triggers.

## Current counted-run protocol

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
   - `average_path_length` over successful runs only

The per-branch runtime limit and counted-run requirement both come from `master_config.py`.

## Early stopping rules

The branch stops before higher agent numbers when either rule triggers at the current
condition:

1. **Cyclic unfinished runs exceed cyclic successful runs** within the retained counted
   pairs for that condition.
   - Example trigger patterns at `n = 5`: `5 > 0`, `4 > 1`, `3 > 2`
   - The entire current condition is discarded.
2. **Five consecutive failed paired sampling attempts** occur while trying to build the
   current condition.
   - In this project, that means five consecutive sampled configurations were rejected by
     the joint viability screen because at least one mapping classified the configuration as
     `unsolvable`.
   - The entire current condition is discarded.

When a stop rule triggers, only the earlier accepted conditions remain in the reported
outputs. The stop reason is written to `metadata/branch_stop_summary.json`.

There is also an internal large safeguard on total paired sampling attempts to prevent
pathological infinite loops. It remains only a protective implementation detail.

## Other important packages

- `dev/experiments/branch_specs.py` — branch-level experiment definitions built from `master_config.py`
- `dev/mapf/` — CBS solvers, metrics, and MAPF execution helpers
- `dev/maps/` — map construction and mapping transforms
- `dev/navigation/` — graph/navigation helpers over composite grids
- `dev/inputs/` — image-based inputs for dynamic branches
- `dev/core/` — composite-grid primitives

## Notes

- The study flow currently uses scattered targets for all branches.
- Pillow-rendered run images are not part of the generalized study flow.
- The dynamic branch sampler requires each sampled start-goal pair to be individually reachable on the shared assignment map, which avoids large numbers of trivial no-solution cases caused by unreachable goals.
