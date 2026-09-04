"""Deterministic force-directed layout for the world map view."""
from __future__ import annotations

import math
from typing import Dict, List, Tuple, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..systems.world import World


def compute_layout(world: "World", iterations: int = 150) -> Dict[str, Tuple[float, float]]:
    """Return country_id -> (x, y) in arbitrary world units.

    The initial placement is seeded from each country id's hash so the same
    world produces the same picture across repeated map views in a session.
    """
    ids = list(world.countries.keys())
    n = len(ids)
    if n == 0:
        return {}
    if n == 1:
        return {ids[0]: (0.0, 0.0)}

    index = {cid: i for i, cid in enumerate(ids)}
    positions = np.zeros((n, 2))
    for cid, i in index.items():
        seed = (hash(cid) & 0xFFFFFFFF) / 0xFFFFFFFF
        angle = seed * 2 * math.pi
        radius = 4.0 + (i % 3)
        positions[i] = [radius * math.cos(angle), radius * math.sin(angle)]

    edges: List[Tuple[int, int]] = []
    seen = set()
    for cid, country in world.countries.items():
        for nid in country.neighbor_ids:
            if nid in index:
                key = (min(index[cid], index[nid]), max(index[cid], index[nid]))
                if key not in seen:
                    seen.add(key)
                    edges.append(key)
    for (a_id, b_id) in world._relations.keys():
        if a_id in index and b_id in index:
            key = (min(index[a_id], index[b_id]), max(index[a_id], index[b_id]))
            if key not in seen:
                seen.add(key)
                edges.append(key)

    for _ in range(iterations):
        delta = positions[:, None, :] - positions[None, :, :]
        dist_sq = np.sum(delta ** 2, axis=-1) + 1e-4
        np.fill_diagonal(dist_sq, np.inf)
        repulsion = np.sum(delta * (6.0 / dist_sq[..., None]), axis=1)
        positions += repulsion * 0.02

        for a, b in edges:
            vec = positions[b] - positions[a]
            dist = max(1e-4, float(np.linalg.norm(vec)))
            force = (dist - 3.5) * 0.01
            direction = vec / dist
            positions[a] += direction * force
            positions[b] -= direction * force

        positions -= positions.mean(axis=0) * 0.01

    _resolve_overlaps(positions, n)

    return {cid: (float(positions[i][0]), float(positions[i][1])) for cid, i in index.items()}


def _resolve_overlaps(positions: np.ndarray, n: int, min_dist: float = 1.6, iterations: int = 60) -> None:
    """Final pass that pushes apart any nodes closer than min_dist, in-place."""
    for _ in range(iterations):
        moved = False
        for i in range(n):
            for j in range(i + 1, n):
                vec = positions[j] - positions[i]
                dist = float(np.linalg.norm(vec))
                if dist < min_dist:
                    moved = True
                    if dist < 1e-6:
                        vec = np.array([0.01 * (i + 1), 0.01 * (j + 1)])
                        dist = float(np.linalg.norm(vec))
                    direction = vec / dist
                    push = (min_dist - dist) / 2.0
                    positions[i] -= direction * push
                    positions[j] += direction * push
        if not moved:
            break
