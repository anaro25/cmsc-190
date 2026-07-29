# All user-defined experiment values live in this file.
# Edit the branch dictionaries below when you want to change seeds, agent-number
# ranges, time limits, densities, thresholds, loop settings, or other branch-specific settings.
#
# dynamic_generation_cell_mode controls which raster cells participate in dynamic
# obstacle generation and free-space connectivity checks:
# - "all_free": every traversable source-image cell is eligible. For campus maps,
#   this means both campus zone colors and white walkways; gray/black cells remain
#   non-traversable.
# - "pure_white_only": only pure-white source-image cells are traversable
# - "zone_colors_only": only designated campus zone-color cells are eligible for
#   dynamic-obstacle generation; white walkways remain traversable but are not used
#   for dynamic obstacles in this mode.
#
# Note: spawnable_cell_mode is separate. Campus agents/targets can still be
# restricted to zone colors even when dynamic obstacles use "all_free".
#
# start_distribution_mode / goal_distribution_mode:
# - "dispersed": unique one-to-one positions sampled across the allowed set
# - "clustered": unique one-to-one positions sampled as one connected cluster
#   whose exact internal spacing is controlled globally by compact_clustering
# - "single": target-only mode where all agents share one literal target cell
#   and disappear there after arrival. Do not use "single" for start_distribution_mode.
#   In campus branches, this shared target is sampled only from the darker
#   single-target marker cells in the selected target zone.
#
# strict_dispersed_8_neighbor_clearance (set independently in each map config)
# - True: every dispersed set must keep all eight neighboring cells clear.
#   Setup generation fails when the requested number cannot satisfy this rule.
# - False: dispersed sampling first places as many mutually separated elements
#   as possible, then uses remaining unique cells, including adjacent cells, only
#   to fill a shortage. This is the default for all eight main map types.
#
# compact_clustering
# - True: clustered sets are compact directly adjacent 8-neighbor-connected groups
# - False: clustered sets are spaced groups whose members keep one empty cell of
#   separation in all 8 directions while still forming one connected cluster
#
# Image inputs
#   static_port and dynamic_port both use dev/inputs/dynamic_port/port_map.png.
#   static_campus_area_1 and dynamic_campus_area_1 both use dev/inputs/campus_area_1.png.
#   static_campus_area_2 and dynamic_campus_area_2 both use dev/inputs/campus_area_2.png.
#   Dark blue, dark green, and dark red pixels are treated as target-only marker
#   cells for campus single-target mode while still belonging to their zones.
#
# zone_relationship_mode:
# - "none": starts and goals may be sampled from the same allowed pool
# - "distinct_campus_zones": starts and goals must come from different campus zones
#
# The main experiment now uses limited binary-search capacity testing over 1..255 agents.
# A tested number passes when at least 1 out of 5 valid solver attempts finishes within 30 seconds.
# The search starts at 128 and descends at most CAPACITY_BINARY_SEARCH_MAX_DOWNWARD_MOVES child links.
# setup_failed and unsolvable initial conditions are regenerated, with a cap of 5 generation attempts per solver attempt.
# Frame-by-frame persistence and visualization:
# - to_generate = "raw_data" records numerical results and saves only two selected
#   trajectories per exact main-experiment configuration: the final retained
#   classical success at classical capacity and the final retained cyclic success
#   at cyclic capacity.
# - These packages are heavily compartmentalized under
#   outputs_main/<map_category>/<exact_map_config>/frame_by_frame/.
# - to_generate = "visualization" performs no MAPF solving and does not read the
#   numerical metrics package. It reads the selected frame_by_frame.pkl packages and
#   generates the Pillow frames from them.
#
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

# to_generate
#   Project-level program-mode selector. Exactly one mode is active per run.
#   "raw_data"      -> recompute raw MAPF data for the selected branch and replace it.
#   "graphs"        -> regenerate structured outputs and graphs from saved raw MAPF data.
#   "visualization" -> regenerate Pillow visualizations from saved frame-by-frame packages.
#
# Presentation outputs are latest-only. Regenerating logs, graphs/data, or
# visualizations replaces the previous copy for that same purpose instead of
# creating a new execution_xxxxxx_xxxxxx_xxxxxx folder.
#
# Numerical raw data and frame-by-frame data are stored separately. Regenerating
# raw data for one exact map configuration replaces only that configuration's
# frame-by-frame subtree and preserves other configurations.
