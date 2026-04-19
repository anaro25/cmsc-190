
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
# - "clustered": unique one-to-one positions sampled as one directly adjacent 8-neighbor-connected group
#
# zone_relationship_mode:
# - "none": starts and goals may be sampled from the same allowed pool
# - "distinct_campus_zones": starts and goals must come from different campus zones
#
# agent_number_range = (start_agent_number, max_agent_number, step_size)
# Example: (8, 40, 4) -> [8, 12, 16, 20, 24, 28, 32, 36, 40]
# num_last_runs_to_visualize controls how many successful runs receive Pillow
# frame output at the end of the branch.
#
# require_jointly_successful_mappings = True
#   Select the last n run configurations for which both classical and cyclic
#   are successful on the same paired instance.
# require_jointly_successful_mappings = False
#   Select the last n successful classical runs and the last n successful cyclic
#   runs independently, even when they come from different paired instances.
# require_individual_reachbility
#   Set this to "True" for branches whose maps are not manually generated. This 
#   verifies if the placement of each element satisfies "individual reachability".
#   That is, all targets can be reached by their respective agents.

# enhanced_CBS
#   Global solver toggle for the entire project.
#   False -> vanilla CBS on both static and dynamic branches.
#   True  -> ECBS on both static and dynamic branches.

# ECBS_suboptimality
#   Branch-level ECBS suboptimality factor used when enhanced_CBS=True.
#   Keep this at 1.0 or above. The whole project still uses one global solver
#   family at a time, but each branch stores its own editable ECBS factor.
