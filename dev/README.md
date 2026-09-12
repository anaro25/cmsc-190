# Dev

This is the code used for the main MAPF experiments and the supplementary reference comparison.

## Running the program

For the main experiment, edit `dev/master_config.py` first. The main things to set are:

- `to_generate`
- `SELECTED_MAP_CONFIGS`
- branch-specific experiment settings
- `enhanced_CBS`

Then run from the folder that contains `dev/`:

```bash
python -m dev.main
```

Main outputs go to:

```text
dev/outputs_main/
```

Each selected map configuration gets its own folder containing its raw metrics, inspection files, saved trajectories, logs, and visualizations.

## Main experiment modes

`to_generate = "raw_data"` runs the experiment and writes the numerical results. It also saves the selected successful trajectories used later for visualization.

`to_generate = "visualization"` creates the visualizations from those saved trajectories. Run `raw_data` first if the needed trajectory files do not exist yet.

There is no separate graph-generation mode for the main experiment.

## Main experiment setup

The current experiment has Traditional MAPF and Campus Crowd Simulation configurations. Exact configurations are selected through `SELECTED_MAP_CONFIGS` in `master_config.py`.

Capacity is searched separately for classical and cyclic mapping using binary search. A tested agent count passes when at least 3 out of 5 runs succeed within the runtime limit.

The project-wide solver switch is:

```python
enhanced_CBS = True
```

- `False` = CBS
- `True` = ECBS

ECBS suboptimality is still set per branch in `master_config.py`.

The main experiment code is mostly under:

```text
dev/experiments/study/
```

The main entry files are:

```text
dev/main.py
dev/master_config.py
dev/experiments/generalized_study.py
```

## Main output files

The most useful result file for each exact map configuration is:

```text
<map_config>_metrics_data.csv
```

The other CSV/JSON files in `metrics_data/` contain the more detailed run records, capacity-search information, paired comparisons, and metadata.

`metrics_data_inspection/` contains the text/XML inspection output, while `frame_by_frame/` contains the saved trajectories used for visualization.

## Supplementary reference comparison

The reference comparison is separate from the main experiment.

In `dev/main.py`, switch the selected experiment to:

```python
SELECTED_EXPERIMENT = "ref_comparison"
```

Its settings are in:

```text
dev/master_config_ref_comparison.py
```

It has two cases:

```python
SELECTED_PORT_EXPERIMENT = "single_agent"
# or
SELECTED_PORT_EXPERIMENT = "multi_agent"
```

Reference outputs go to:

```text
dev/outputs_ref_comparison/
```

The reference experiment uses the three port maps in:

```text
dev/inputs/reference_port_maps/
```

For the multi-agent case, the fixed agent counts are 17 for Map 1, 24 for Map 2, and 11 for Map 3.

Unlike the main experiment, the reference comparison also supports graph generation through its `to_generate` setting.
