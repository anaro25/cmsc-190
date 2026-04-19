from __future__ import annotations

from collections import deque
from typing import Iterable

from dev.navigation.cyclic_grid_navigation import get_all_free_vertices, get_outgoing_neighbors


_STATIC_INCOMING_CACHE: dict[int, dict[tuple[int, int], tuple[tuple[int, int], ...]]] = {}
_STATIC_DISTANCE_CACHE: dict[tuple[int, tuple[int, int]], dict[tuple[int, int], int]] = {}
_DYNAMIC_INCOMING_CACHE: dict[int, dict[tuple[int, int], tuple[tuple[int, int], ...]]] = {}
_DYNAMIC_DISTANCE_CACHE: dict[tuple[int, tuple[int, int]], dict[tuple[int, int], int]] = {}
_DYNAMIC_STATIC_FREE_COUNT_CACHE: dict[int, int] = {}


def _build_incoming_neighbors_from_graph(
    free_vertices: Iterable[tuple[int, int]],
    neighbor_provider,
) -> dict[tuple[int, int], tuple[tuple[int, int], ...]]:
    incoming: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for vertex in free_vertices:
        incoming.setdefault(vertex, set())
        for neighbor in neighbor_provider(vertex):
            incoming.setdefault(neighbor, set()).add(vertex)
    return {vertex: tuple(sorted(parents)) for vertex, parents in incoming.items()}


def _static_incoming_neighbors(cyclic_map) -> dict[tuple[int, int], tuple[tuple[int, int], ...]]:
    cache_key = id(cyclic_map)
    cached = _STATIC_INCOMING_CACHE.get(cache_key)
    if cached is not None:
        return cached

    free_vertices = tuple(get_all_free_vertices(cyclic_map))
    incoming = _build_incoming_neighbors_from_graph(
        free_vertices,
        lambda vertex: get_outgoing_neighbors(cyclic_map, vertex),
    )
    _STATIC_INCOMING_CACHE[cache_key] = incoming
    return incoming


def _dynamic_incoming_neighbors(mapped_loop) -> dict[tuple[int, int], tuple[tuple[int, int], ...]]:
    cache_key = id(mapped_loop)
    cached = _DYNAMIC_INCOMING_CACHE.get(cache_key)
    if cached is not None:
        return cached

    outgoing_union: dict[tuple[int, int], set[tuple[int, int]]] = {}
    static_free_vertices: set[tuple[int, int]] = set()

    for frame in mapped_loop:
        frame_vertices = get_all_free_vertices(frame)
        static_free_vertices.update(frame_vertices)
        for vertex in frame_vertices:
            outgoing_union.setdefault(vertex, set()).update(get_outgoing_neighbors(frame, vertex))

    incoming = _build_incoming_neighbors_from_graph(
        static_free_vertices,
        lambda vertex: outgoing_union.get(vertex, ()),
    )
    _DYNAMIC_INCOMING_CACHE[cache_key] = incoming
    _DYNAMIC_STATIC_FREE_COUNT_CACHE[cache_key] = len(static_free_vertices)
    return incoming


def _reverse_bfs_distances(
    incoming_neighbors: dict[tuple[int, int], tuple[tuple[int, int], ...]],
    goal: tuple[int, int],
) -> dict[tuple[int, int], int]:
    if goal not in incoming_neighbors:
        return {}

    distances: dict[tuple[int, int], int] = {goal: 0}
    queue: deque[tuple[int, int]] = deque([goal])

    while queue:
        current = queue.popleft()
        current_distance = distances[current]
        for parent in incoming_neighbors.get(current, ()):  # reverse graph traversal
            if parent in distances:
                continue
            distances[parent] = current_distance + 1
            queue.append(parent)

    return distances


def get_true_static_distances_for_static_map(
    cyclic_map,
    goal: tuple[int, int],
) -> dict[tuple[int, int], int]:
    cache_key = (id(cyclic_map), goal)
    cached = _STATIC_DISTANCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    distances = _reverse_bfs_distances(_static_incoming_neighbors(cyclic_map), goal)
    _STATIC_DISTANCE_CACHE[cache_key] = distances
    return distances


def get_true_static_distances_for_dynamic_map(
    mapped_loop,
    goal: tuple[int, int],
) -> dict[tuple[int, int], int]:
    cache_key = (id(mapped_loop), goal)
    cached = _DYNAMIC_DISTANCE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    distances = _reverse_bfs_distances(_dynamic_incoming_neighbors(mapped_loop), goal)
    _DYNAMIC_DISTANCE_CACHE[cache_key] = distances
    return distances


def get_dynamic_static_free_vertex_count(mapped_loop) -> int:
    cache_key = id(mapped_loop)
    cached = _DYNAMIC_STATIC_FREE_COUNT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    _dynamic_incoming_neighbors(mapped_loop)
    return _DYNAMIC_STATIC_FREE_COUNT_CACHE.get(cache_key, 0)
