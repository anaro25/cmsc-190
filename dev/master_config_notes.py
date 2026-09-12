# Notes for settings that are easy to mix up.
#
# dynamic_generation_cell_mode:
# - "all_free": all traversable cells can be used for dynamic obstacles
# - "pure_white_only": only white cells are used
# - "zone_colors_only": only campus zone cells are used; white paths stay free
#
# spawnable_cell_mode is separate from dynamic_generation_cell_mode.
#
# start_distribution_mode / goal_distribution_mode:
# - "dispersed": unique positions spread across the allowed cells
# - "clustered": one connected group
# - "single": all agents share one target cell; only use this for goals
#
# strict_dispersed_8_neighbor_clearance=True keeps all 8 neighboring cells clear.
# With False, adjacent cells can be used when there is not enough room.
#
# compact_clustering=True makes clustered positions directly adjacent.
#
# zone_relationship_mode="distinct_campus_zones" keeps starts and goals in different zones.
#
# Main capacity search tests classical and cyclic separately. A tested agent count
# passes when at least 3 of 5 runs solve within the time limit.
#
# enhanced_CBS selects CBS or ECBS for the project.
# ECBS_suboptimality is the branch-level ECBS weight and should be at least 1.0.
# tight_time_horizon switches between the older time cap and the tighter one.
#
# raw_data recomputes MAPF results, graphs rebuilds saved outputs, and
# visualization renders from saved frame-by-frame packages.
