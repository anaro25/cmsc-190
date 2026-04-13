# dev project layout

## How to run

Edit `dev/master_config.py` and leave exactly one `MAP_TYPE` uncommented, then run:

```bash
python -m dev.main
```

`master_config.py` is the single user-editable file for branch seeds, map size,
agent lists, runtime limits, densities, thresholds, and loop settings.

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
- `orchestrator.py` — counted-run protocol and branch execution flow

## Current counted-run protocol

For each agent number in the selected branch:

1. Classical mapping samples run configurations until it gathers `n` counted runs.
2. A counted run is any run whose result category is either:
   - `successful`
   - `unfinished`
3. A run classified as `unsolvable` is recorded, but it does not count toward `n`.
4. Cyclic mapping replays the exact counted classical run configurations.
5. Aggregates use:
   - `time_computation_halted_seconds` over counted runs
   - `num_conflicts_detected_at_halt` over counted runs
   - `average_path_length` over successful runs only

The per-branch runtime limit and counted-run requirement both come from `master_config.py`.

There is also an internal large safeguard on total classical attempts to prevent pathological infinite loops. It is only a protective implementation detail.

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
