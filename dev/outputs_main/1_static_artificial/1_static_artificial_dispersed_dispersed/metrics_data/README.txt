MAIN EXPERIMENT METRICS DATA — READER GUIDE

Map configuration: static_artificial_dispersed_dispersed
Display name: Static Artificial / Dispersed-Dispersed
Schema version: 3

PURPOSE
This folder is a Results-ready data package for the main experiment. It contains the numerical evidence, protocol context, run outcomes, and paired comparisons needed to write the corresponding Results and Discussion subsection. It does not contain reference-comparison data or plot images.

RECOMMENDED READING ORDER
1. configuration_metadata.csv — identify the map, environment, arrangements, solver, runtime limit, and capacity protocol.
2. capacity_comparison.csv — report classical and cyclic protocol capacities and their difference.
3. results_ready_comparisons.csv — use this as the primary compact table for prose and manuscript tables.
4. capacity_point_summary.csv — verify sample counts, completion behavior, averages, ranges, and variability.
5. paired_run_comparisons.csv — inspect matched classical/cyclic outcomes on the same initial conditions.
6. capacity_search_tests.csv — explain how each protocol capacity was reached.
7. capacity_point_run_records.csv and capacity_search_run_records.csv — audit the individual observations.
8. metrics_package.json — complete machine-readable package containing all tables above.

INTERPRETATION RULES
- Capacities are protocol-based highest accepted tested agent numbers, not theoretical maxima.
- A capacity value of 0 means the search found no accepted tested value under the configured protocol.
- Blank metric cells mean unavailable or not applicable; they must not be interpreted as zero.
- Time and conflict summaries include counted successful and unfinished runs when present.
- Total path length is available only for solved runs. Always report its valid value count.
- Positive percentage change means cyclic is larger than classical; negative means cyclic is smaller.
- Classical and cyclic records sharing a run_config_id used the same generated initial conditions.
- Do not describe a one-record mean as evidence of low variability; consult run_record_count and standard-deviation columns.

FILES WRITTEN
- README.txt
- configuration_metadata.csv
- capacity_summary.csv
- capacity_comparison.csv
- capacity_search_tests.csv
- capacity_search_run_records.csv
- capacity_point_run_records.csv
- capacity_point_summary.csv
- paired_run_comparisons.csv
- results_ready_comparisons.csv
- 1_static_artificial_dispersed_dispersed_metrics_data.csv
- metrics_package.json
