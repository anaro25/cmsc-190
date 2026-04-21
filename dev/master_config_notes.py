# All user-defined experiment values live in this file.
# Edit the branch dictionaries below when you want to change seeds, agent-number
# ranges, time limits, densities, thresholds, loop settings, or other branch-specific settings.
#
# dynamic_generation_cell_mode controls which raster cells participate in dynamic
# obstacle generation and free-space connectivity checks:
# - "all_free": every non-black source-image cell is traversable
# - "pure_white_only": only pure-white source-image cells are traversable
# - "zone_colors_only": only designated campus zone-color cells are eligible
#   for spawning or dynamic-obstacle generation; white walkways remain traversable
#   but non-spawnable, and gray areas remain non-traversable.
#
# start_distribution_mode / goal_distribution_mode:
# - "dispersed": unique one-to-one positions sampled across the allowed set
# - "clustered": unique one-to-one positions sampled as one connected cluster
#   whose exact internal spacing is controlled globally by compact_clustering
#
# compact_clustering
# - True: clustered sets are compact directly adjacent 8-neighbor-connected groups
# - False: clustered sets are spaced groups whose members keep one empty cell of
#   separation in all 8 directions while still forming one connected cluster
#
# narrow_lanes
#   Campus image selector used by static_campus_area_1 and dynamic_campus_area_2.
#   True  -> use the *_narrow_lanes.png variant
#   False -> use the *_wide_lanes.png variant
#
# zone_relationship_mode:
# - "none": starts and goals may be sampled from the same allowed pool
# - "distinct_campus_zones": starts and goals must come from different campus zones
#
# agent_number_range = (start_agent_number, max_agent_number, step_size)
# Example: (8, 40, 4) -> [8, 12, 16, 20, 24, 28, 32, 36, 40]
# num_last_runs_to_visualize_jointly_successful controls how many of the final
# jointly successful classical-cyclic paired runs receive Pillow frame output.
# num_last_runs_to_visualize_independently_successful controls how many of the
# final successful runs of each mapping are rendered independently.
#
# When to_generate = "visualization", the renderer now creates BOTH versions:
# - jointly_successful
# - independently_successful
#
# Important: these visualization-selection controls are read from the current
# master_config.py during visualization regeneration. They do not force a new
# MAPF recomputation by themselves as long as compatible persisted raw data
# already exists for the selected branch.
# require_individual_reachbility
#   Set this to "True" for branches whose maps are not manually generated. This
#   verifies if the placement of each element satisfies "individual reachability".
#   That is, all targets can be reached by their respective agents.
#
# enhanced_CBS
#   Global solver toggle for the entire project.
#   False -> vanilla CBS on both static and dynamic branches.
#   True  -> ECBS on both static and dynamic branches.
#
# ECBS_suboptimality
#   Branch-level ECBS suboptimality factor used when enhanced_CBS=True.
#   Keep this at 1.0 or above. The whole project still uses one global solver
#   family at a time, but each branch stores its own editable ECBS factor.
#
# true_static_shortest_path_distance
#   Branch-level low-level-planner toggle.
#   False -> keep the original Manhattan-style heuristic.
#   True  -> use the exact shortest-path distance on the branch's static graph
#            as the low-level A* heuristic. Dynamic branches compute this on the
#            shared mapped loop while ignoring time-varying obstacle occupancy.
#
# tight_time_horizon
#   Branch-level low-level-planner toggle.
#   False -> keep the original, more conservative time-horizon rule.
#   True  -> use the tighter distance-aware horizon. This still preserves a slack
#            allowance, but it is much smaller than the older map-size-based cap.

# recompute_MAPF
#   Project-level raw-data persistence toggle.
#   False -> keep the currently saved raw MAPF data for the selected branch.
#   True  -> recompute raw MAPF data for the selected branch and replace it.
#
# to_generate
#   Project-level output-generation selector.
#   "graphs_and_data" -> regenerate structured outputs and graphs from saved raw MAPF data.
#   "visualization"   -> regenerate Pillow visualizations from saved raw MAPF data.
#   "nothing"         -> do not regenerate outputs in this run.
#
# Presentation outputs are latest-only. Regenerating logs, graphs/data, or
# visualizations replaces the previous copy for that same purpose instead of
# creating a new execution_xxxxxx_xxxxxx_xxxxxx folder.
#
# Raw MAPF data is stored per branch and is intentionally controlled manually.
# Each branch now keeps a split raw-data directory with a manifest, metadata, and
# per-condition files instead of one monolithic pickle. The program does not try
# to validate whether the current code or configuration matches the saved raw data;
# set recompute_MAPF=True when you want to replace it.
# Visualization-selection controls such as
# num_last_runs_to_visualize_jointly_successful and
# num_last_runs_to_visualize_independently_successful are read from the current
# master_config.py during visualization regeneration, so changing only those
# does not require a fresh MAPF recomputation as long as saved raw data already
# exists.
