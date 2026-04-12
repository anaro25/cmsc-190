# dev project layout

## How to run

Edit `dev/main.py` and leave exactly one `MAP_TYPE` uncommented, then run:

```bash
python -m dev.main
```

Results are written under `dev/outputs/<map_type>/`.

## Current orchestration path

The active experiment driver is the generalized study runner:

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
- `orchestrator.py` — the fairness protocol and branch execution flow

## Other important packages

- `dev/experiments/branch_specs.py` — branch-level experiment definitions
- `dev/mapf/` — CBS solvers, metrics, and MAPF execution helpers
- `dev/maps/` — map construction and mapping transforms
- `dev/navigation/` — graph/navigation helpers over composite grids
- `dev/inputs/` — image-based inputs for dynamic branches
- `dev/core/` — composite-grid primitives

## Notes

- The study flow currently uses scattered targets for all branches.
- Pillow-rendered run images are not part of the generalized study flow.
- The dynamic branch sampler now requires each sampled start-goal pair to be individually reachable on the shared assignment map, which avoids large numbers of trivial no-solution cases caused by unreachable goals.
